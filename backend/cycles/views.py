from datetime import date

from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

from core.permissions import (
    IsCycleOwner,
    IsParentCycleOwner,
    IsTemplateOwnerOrSharedAccess,
    accessible_templates_q,
    owned_cycles_q,
    user_can_access_template,
    user_can_edit_template,
)
from templates_mgmt.models import Template
from .models import CycleActivity, CycleInstance, CycleTask, TaskDependency
from .services import generate_cycle_runtime_records

from .dependency_engine import (
    DependencyConflict,
    apply_task_shift,
    assert_dependent_capacity,
    check_offset_conflict,
    preview_task_shift,
    would_create_cycle,
)

from .serializers import (
    CycleActivitySerializer,
    CycleInstanceSerializer,
    CycleTaskSerializer,
    TaskDependencySerializer,
)

class CycleInstanceViewSet(viewsets.ModelViewSet):
    serializer_class = CycleInstanceSerializer
    permission_classes = [permissions.IsAuthenticated, IsCycleOwner]
    filter_backends = [SearchFilter]
    search_fields = ["cycle_name", "status"]

    def get_queryset(self):
        return CycleInstance.objects.filter(owned_cycles_q(self.request.user)).distinct()

    def perform_create(self, serializer):
        # FR-4: creating a cycle instance must also generate runtime copies of
        # every task and activity on the chosen template, with absolute dates
        # calculated from the cycle's start date (7.1, 7.2, 7.3, 7.4). Wrapped
        # in a transaction so a partial failure never leaves an orphaned cycle
        # with no runtime records.
        with transaction.atomic():
            cycle = serializer.save(user=self.request.user)
            generate_cycle_runtime_records(cycle)

    @action(detail=True, methods=["post"])
    def shut_down(self, request, pk=None):
        cycle = self.get_object()
        cycle.status = "shut_down"
        cycle.save(update_fields=["status"])
        return Response(self.get_serializer(cycle).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        cycle = self.get_object()
        payload = self.get_serializer(cycle).data
        payload["cycle_tasks"] = CycleTaskSerializer(
            cycle.cycle_tasks.all(),
            many=True,
            context=self.get_serializer_context(),
        ).data
        payload["cycle_activities"] = CycleActivitySerializer(
            cycle.cycle_activities.all(),
            many=True,
            context=self.get_serializer_context(),
        ).data
        return Response(payload, status=status.HTTP_200_OK)


class CycleTaskViewSet(viewsets.ModelViewSet):
    serializer_class = CycleTaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsParentCycleOwner]
    filter_backends = [SearchFilter]
    search_fields = ["task_name", "status", "note_text"]

    def get_queryset(self):
        owned_cycle_ids = CycleInstance.objects.filter(
            owned_cycles_q(self.request.user)
        ).values("pk")
        return CycleTask.objects.filter(cycle_id__in=owned_cycle_ids).distinct()

    def _parse_shift_input(self, request):
        data = request.data
        delay_days = data.get("delay_days")
        new_start_date = data.get("new_start_date")
        new_end_date = data.get("new_end_date")
        if sum(v is not None for v in (delay_days, new_start_date, new_end_date)) != 1:
            return None, Response(
                {"non_field_errors": ["Provide exactly one of delay_days, new_start_date, new_end_date."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        parsed = {
            "delay_days": int(delay_days) if delay_days is not None else None,
            "new_start_date": date.fromisoformat(new_start_date) if new_start_date else None,
            "new_end_date": date.fromisoformat(new_end_date) if new_end_date else None,
        }
        return parsed, None

    @action(detail=True, methods=["post"])
    def shift_preview(self, request, pk=None):
        cycle_task = self.get_object()
        parsed, error_response = self._parse_shift_input(request)
        if error_response:
            return error_response
        result = preview_task_shift(cycle_task, **parsed)
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def shift(self, request, pk=None):
        cycle_task = self.get_object()
        parsed, error_response = self._parse_shift_input(request)
        if error_response:
            return error_response

        scope = request.data.get("scope", "single")
        if scope not in ("single", "cascade"):
            return Response(
                {"scope": ["Must be 'single' or 'cascade'."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        override_fixed = bool(request.data.get("override_fixed", False))

        try:
            with transaction.atomic():
                result = apply_task_shift(
                    cycle_task, scope, override_fixed=override_fixed, **parsed
                )
        except DependencyConflict as exc:
            return Response(exc.as_response_payload(), status=status.HTTP_409_CONFLICT)

        return Response(
            {
                "cycle_task_id": cycle_task.pk,
                "scope": scope,
                "shifted_tasks": result["shifted"],
                "warnings": result["warnings"],
            },
            status=status.HTTP_200_OK,
        )

class CycleActivityViewSet(viewsets.ModelViewSet):
    serializer_class = CycleActivitySerializer
    permission_classes = [permissions.IsAuthenticated, IsParentCycleOwner]
    filter_backends = [SearchFilter]
    search_fields = ["activity_name", "note_text"]

    def get_queryset(self):
        owned_cycle_ids = CycleInstance.objects.filter(
            owned_cycles_q(self.request.user)
        ).values("pk")
        return CycleActivity.objects.filter(cycle_id__in=owned_cycle_ids).distinct()


class TaskDependencyViewSet(viewsets.ModelViewSet):
    serializer_class = TaskDependencySerializer
    permission_classes = [permissions.IsAuthenticated, IsTemplateOwnerOrSharedAccess]
    filter_backends = [SearchFilter]
    search_fields = [
        "task__task_name",
        "depends_on_task__task_name",
    ]

    def get_queryset(self):
        accessible_template_ids = Template.objects.filter(
            accessible_templates_q(self.request.user)
        ).values("pk")
        return TaskDependency.objects.filter(
            task__template_id__in=accessible_template_ids,
            depends_on_task__template_id__in=accessible_template_ids,
        ).distinct()

    def perform_create(self, serializer):
        task = serializer.validated_data["task"]
        depends_on_task = serializer.validated_data["depends_on_task"]
        self._validate_editable_dependency_tasks(task, depends_on_task)
        self._validate_dependency_graph(task, depends_on_task)
        serializer.save()

    def perform_update(self, serializer):
        task = serializer.validated_data.get("task", serializer.instance.task)
        depends_on_task = serializer.validated_data.get(
            "depends_on_task",
            serializer.instance.depends_on_task,
        )
        self._validate_editable_dependency_tasks(task, depends_on_task)
        self._validate_dependency_graph(
            task, depends_on_task, exclude_dependency_id=serializer.instance.pk
        )
        serializer.save()

    def _validate_editable_dependency_tasks(self, task, depends_on_task):
        if task.template_id != depends_on_task.template_id:
            return

        if not user_can_edit_template(self.request.user, task.template):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You do not have permission to modify this template.")

    def _validate_dependency_graph(self, task, depends_on_task, exclude_dependency_id=None):
        from rest_framework.exceptions import ValidationError

        if would_create_cycle(task, depends_on_task):
            raise ValidationError(
                {"depends_on_task": ["This dependency would create a circular chain."]}
            )
        try:
            check_offset_conflict(task, depends_on_task)
            assert_dependent_capacity(depends_on_task, exclude_dependency_id=exclude_dependency_id)
        except DependencyConflict as exc:
            raise ValidationError({"depends_on_task": [exc.message]})