from datetime import timedelta

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

    @action(detail=True, methods=["post"])
    def record_delay(self, request, pk=None):
        cycle_task = self.get_object()
        delay_days = int(request.data.get("delay_days", 0))
        if delay_days < 0:
            return Response(
                {"delay_days": ["Delay days must be zero or greater."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cycle_task.calculated_start_date += timedelta(days=delay_days)
        cycle_task.calculated_end_date += timedelta(days=delay_days)
        if delay_days > 0:
            cycle_task.status = "delayed"
        cycle_task.save(
            update_fields=["calculated_start_date", "calculated_end_date", "status"]
        )
        return Response(self.get_serializer(cycle_task).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def recalculate_dependencies(self, request, pk=None):
        cycle_task = self.get_object()
        dependencies = TaskDependency.objects.filter(task=cycle_task.template_task)
        latest_end_date = None

        for dependency in dependencies.select_related("depends_on_task"):
            dependency_cycle_task = CycleTask.objects.filter(
                cycle=cycle_task.cycle,
                template_task=dependency.depends_on_task,
            ).first()
            if dependency_cycle_task is None:
                continue
            if latest_end_date is None or dependency_cycle_task.calculated_end_date > latest_end_date:
                latest_end_date = dependency_cycle_task.calculated_end_date

        if latest_end_date is not None and latest_end_date > cycle_task.calculated_start_date:
            cycle_task.calculated_start_date = latest_end_date
            if cycle_task.calculated_end_date < latest_end_date:
                cycle_task.calculated_end_date = latest_end_date
            cycle_task.save(
                update_fields=["calculated_start_date", "calculated_end_date"]
            )

        return Response(self.get_serializer(cycle_task).data, status=status.HTTP_200_OK)


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
        serializer.save()

    def perform_update(self, serializer):
        task = serializer.validated_data.get("task", serializer.instance.task)
        depends_on_task = serializer.validated_data.get(
            "depends_on_task",
            serializer.instance.depends_on_task,
        )
        self._validate_editable_dependency_tasks(task, depends_on_task)
        serializer.save()

    def _validate_editable_dependency_tasks(self, task, depends_on_task):
        if task.template_id != depends_on_task.template_id:
            return

        if not user_can_edit_template(self.request.user, task.template):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You do not have permission to modify this template.")
