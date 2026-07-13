from datetime import date, timedelta

from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
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
from templates_mgmt.scheduling import resolve_effective_offsets
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
from .task_status_engine import (
    ALLOWED_TRANSITIONS,
    CycleNotRunning,
    InvalidStatusTransition,
    assert_cycle_is_running,
    maybe_complete_cycle,
    validate_status_transition,
)
from .serializers import (
    CycleActivitySerializer,
    CycleInstanceSerializer,
    CycleTaskSerializer,
    TaskDependencySerializer,
)


def recompute_cycle_schedule(cycle):
    """
    Rebuilds every non-completed task's calculated dates for this
    cycle, respecting the full dependency chain (however many hops
    deep), using each task's CURRENT calculated_start_date /
    calculated_end_date as its own baseline. This means a delay
    already applied, or a manual edit, is preserved rather than
    re-derived from the template — but the dependency chain always
    wins if it requires a later start.

    Completed tasks are never moved: their own dates are frozen, but
    everything downstream still sees their real end date as a
    constraint. Fixed-end-date tasks behave the same way (per the
    Requirements doc), except a conflict is reported rather than the
    task being silently shifted.

    Returns (updated_cycle_task_ids, circular_task_names, conflict_task_names).
    """
    cycle_tasks = list(
        CycleTask.objects.filter(cycle=cycle).select_related("template_task")
    )
    by_id = {ct.cycle_task_id: ct for ct in cycle_tasks}
    template_task_to_cycle_task_id = {ct.template_task_id: ct.cycle_task_id for ct in cycle_tasks}

    nodes = {}
    for ct in cycle_tasks:
        duration = max((ct.calculated_end_date - ct.calculated_start_date).days, 0)
        nodes[ct.cycle_task_id] = {
            "offset": ct.calculated_start_date.toordinal(),
            "duration": duration,
            "fixed": ct.is_fixed_date or ct.status == "completed",
        }

    edges = {}
    template_task_ids = list(template_task_to_cycle_task_id.keys())
    deps = TaskDependency.objects.filter(task_id__in=template_task_ids)
    for dep in deps:
        dependent_id = template_task_to_cycle_task_id.get(dep.task_id)
        dependency_id = template_task_to_cycle_task_id.get(dep.depends_on_task_id)
        if dependent_id is None or dependency_id is None:
            continue
        edges.setdefault(dependent_id, []).append(dependency_id)

    effective, circular, conflicts = resolve_effective_offsets(nodes, edges)

    updated_ids = []
    for cycle_task_id, (start_ord, end_ord) in effective.items():
        ct = by_id[cycle_task_id]
        if ct.status == "completed":
            continue
        new_start = date.fromordinal(start_ord)
        new_end = date.fromordinal(end_ord)
        if new_start != ct.calculated_start_date or new_end != ct.calculated_end_date:
            ct.calculated_start_date = new_start
            ct.calculated_end_date = new_end
            ct.save(update_fields=["calculated_start_date", "calculated_end_date"])
            updated_ids.append(cycle_task_id)

    id_to_name = {ct.cycle_task_id: ct.task_name for ct in cycle_tasks}
    circular_names = [id_to_name.get(i, str(i)) for i in circular]
    conflict_names = [id_to_name.get(i, str(i)) for i in conflicts]
    return updated_ids, circular_names, conflict_names


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
        if cycle.status == "shut_down":
            return Response(self.get_serializer(cycle).data, status=status.HTTP_200_OK)
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
        queryset = CycleTask.objects.filter(cycle_id__in=owned_cycle_ids).distinct()

        cycle_id = self.request.query_params.get("cycle")
        if cycle_id:
            queryset = queryset.filter(cycle_id=cycle_id)

        return queryset

    def perform_create(self, serializer):
        from rest_framework.exceptions import PermissionDenied

        cycle = serializer.validated_data["cycle"]

        if cycle.user_id != self.request.user.id:
            raise PermissionDenied(
                "You do not have permission to attach a task to this cycle."
            )

        serializer.save()

    def perform_update(self, serializer):
        # Module 9, FR-6.1/FR-6.4. Status is the only field this
        # serializer allows through, everything else is read-only, so
        # this only ever needs to check the transition itself.
        cycle_task = serializer.instance
        new_status = serializer.validated_data.get("status", cycle_task.status)

        try:
            assert_cycle_is_running(cycle_task.cycle)
        except CycleNotRunning as exc:
            raise CycleFrozen(exc.message)

        try:
            validate_status_transition(cycle_task, new_status)
        except InvalidStatusTransition as exc:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"status": [exc.message]})

        updated = serializer.save()

        if updated.status in ("completed", "skipped"):
            maybe_complete_cycle(updated.cycle)
    
    @action(detail=True, methods=["get"])
    def available_statuses(self, request, pk=None):
        # Lets the frontend show exactly the right buttons for a task's
        # current state without hardcoding the transition map client-side.
        cycle_task = self.get_object()
        return Response(
            {
                "current_status": cycle_task.status,
                "available_statuses": sorted(ALLOWED_TRANSITIONS.get(cycle_task.status, set())),
            },
            status=status.HTTP_200_OK,
        )

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

        if delay_days > 0:
            cycle_task.calculated_start_date += timedelta(days=delay_days)
            cycle_task.calculated_end_date += timedelta(days=delay_days)
            cycle_task.save(
                update_fields=["calculated_start_date", "calculated_end_date"]
            )

        # The delay must propagate through the whole dependency chain,
        # not just this one task — recompute the entire cycle's
        # schedule in one pass.
        _, circular_names, conflict_names = recompute_cycle_schedule(cycle_task.cycle)

        cycle_task.refresh_from_db()
        response_data = self.get_serializer(cycle_task).data
        if circular_names or conflict_names:
            response_data["schedule_warnings"] = {
                "circular_dependency_tasks": circular_names,
                "fixed_date_conflicts": conflict_names,
            }
        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def shift(self, request, pk=None):
        cycle_task = self.get_object()
        _, circular_names, conflict_names = recompute_cycle_schedule(cycle_task.cycle)

        cycle_task.refresh_from_db()
        response_data = self.get_serializer(cycle_task).data
        if circular_names or conflict_names:
            response_data["schedule_warnings"] = {
                "circular_dependency_tasks": circular_names,
                "fixed_date_conflicts": conflict_names,
            }
        return Response(response_data, status=status.HTTP_200_OK)

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
        queryset = CycleActivity.objects.filter(cycle_id__in=owned_cycle_ids).distinct()

        cycle_id = self.request.query_params.get("cycle")
        if cycle_id:
            queryset = queryset.filter(cycle_id=cycle_id)

        return queryset


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
