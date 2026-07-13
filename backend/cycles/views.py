from datetime import date

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
    user_can_edit_template,
)

from templates_mgmt.models import Template, TemplateTask
from .models import CycleActivity, CycleInstance, CycleTask, TaskDependency
from .services import generate_cycle_runtime_records, validate_activity_bounds
from .dependency_engine import (
    DependencyConflict,
    apply_task_shift,
    collect_dependency_violations,
    preview_task_shift,
)

from .task_status_engine import (
    ALLOWED_TRANSITIONS,
    CycleNotRunning,
    InvalidStatusTransition,
    apply_prerequisite_resolution,
    assert_cycle_is_running,
    find_unresolved_prerequisites,
    maybe_complete_cycle,
    validate_status_transition,
)
from .serializers import (
    CycleActivitySerializer,
    CycleInstanceSerializer,
    CycleTaskSerializer,
    TaskDependencySerializer,
)


class CycleFrozen(APIException):
    """A completed or shut down cycle rejects every edit with 422, see
    assert_cycle_is_running. Raised from the domain level CycleNotRunning
    exception, this is only the HTTP translation of it.
    """
    status_code = 422
    default_code = "cycle_not_running"

    def __init__(self, message):
        super().__init__(detail=message)


class PrerequisitesUnresolved(APIException):
    """A task is being marked completed while a task it directly depends
    on is still open. The frontend needs to ask the user to resolve each
    one as completed or skipped, then resend the same request with
    resolve_prerequisites filled in, see CycleTaskViewSet.perform_update.
    """
    status_code = 409
    default_code = "prerequisites_unresolved"

    def __init__(self, unresolved_tasks):
        super().__init__(detail=self.default_code)
        # Set directly rather than passed through __init__, DRF's
        # APIException recursively stringifies every leaf value in a
        # dict detail (even integers) the moment it's constructed, which
        # would silently turn cycle_task_id into a string in the actual
        # JSON response. Assigning self.detail afterward skips that, so
        # this stays numeric, consistent with DependencyConflict's own
        # payload shape used everywhere else in this file.
        self.detail = {
            "error": "prerequisites_unresolved",
            "message": (
                "This task depends on tasks that are not finished yet. "
                "Resolve each one as completed or skipped before completing this task."
            ),
            "unresolved_prerequisites": [
                {
                    "cycle_task_id": task.cycle_task_id,
                    "task_name": task.task_name,
                    "status": task.status,
                }
                for task in unresolved_tasks
            ],
        }


class CycleInstanceViewSet(viewsets.ModelViewSet):
    serializer_class = CycleInstanceSerializer
    permission_classes = [permissions.IsAuthenticated, IsCycleOwner]
    filter_backends = [SearchFilter]
    search_fields = ["cycle_name", "status"]

    def get_queryset(self):
        return CycleInstance.objects.filter(owned_cycles_q(self.request.user)).distinct()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        response_data = dict(serializer.data)
        if self._last_schedule_warnings:
            response_data["schedule_warnings"] = self._last_schedule_warnings

        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        # FR-4: creating a cycle instance must also generate runtime copies of
        # every task and activity on the chosen template, with absolute dates
        # calculated from the cycle's start date and resolved through the
        # template's dependency graph (7.1, 7.2, 7.3, 7.4). Wrapped in a
        # transaction so a partial failure never leaves an orphaned cycle
        # with no runtime records.
        with transaction.atomic():
            cycle = serializer.save(user=self.request.user)
            result = generate_cycle_runtime_records(cycle)
        self._last_schedule_warnings = result.get("schedule_warnings")

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

        with transaction.atomic():
            if new_status == "completed" and new_status != cycle_task.status:
                self._resolve_prerequisites_before_completion(cycle_task)

            updated = serializer.save()

            if updated.status in ("completed", "skipped"):
                maybe_complete_cycle(updated.cycle)

    def _resolve_prerequisites_before_completion(self, cycle_task):
        # A task is being marked completed while something it directly
        # depends on is still open. Rather than silently leaving that
        # prerequisite stuck, the frontend must ask the user to close it
        # out first, as either completed or skipped, and resend the
        # same request with resolve_prerequisites filled in.
        unresolved = find_unresolved_prerequisites(cycle_task)
        if not unresolved:
            return

        resolutions = self.request.data.get("resolve_prerequisites") or {}
        resolutions_by_id = {str(k): v for k, v in resolutions.items()}

        still_unresolved = [
            task for task in unresolved
            if str(task.cycle_task_id) not in resolutions_by_id
        ]
        if still_unresolved:
            raise PrerequisitesUnresolved(unresolved)

        from rest_framework.exceptions import ValidationError

        for task in unresolved:
            chosen = resolutions_by_id[str(task.cycle_task_id)]
            if chosen not in ("completed", "skipped"):
                raise ValidationError({
                    "resolve_prerequisites": [
                        f"Task '{task.task_name}' must be resolved as "
                        "'completed' or 'skipped'."
                    ]
                })

        for task in unresolved:
            apply_prerequisite_resolution(
                task, resolutions_by_id[str(task.cycle_task_id)]
            )

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

        try:
            parsed = {
                "delay_days": int(delay_days) if delay_days is not None else None,
                "new_start_date": date.fromisoformat(new_start_date) if new_start_date else None,
                "new_end_date": date.fromisoformat(new_end_date) if new_end_date else None,
            }
        except (TypeError, ValueError):
            return None, Response(
                {"non_field_errors": ["delay_days must be an integer, dates must be YYYY-MM-DD."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return parsed, None

    @action(detail=True, methods=["post"])
    def shift_preview(self, request, pk=None):
        cycle_task = self.get_object()

        try:
            assert_cycle_is_running(cycle_task.cycle)
        except CycleNotRunning as exc:
            raise CycleFrozen(exc.message)

        parsed, error_response = self._parse_shift_input(request)
        if error_response is not None:
            return error_response

        preview = preview_task_shift(
            cycle_task,
            delay_days=parsed["delay_days"],
            new_start_date=parsed["new_start_date"],
            new_end_date=parsed["new_end_date"],
        )
        return Response(preview, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def shift(self, request, pk=None):
        cycle_task = self.get_object()

        try:
            assert_cycle_is_running(cycle_task.cycle)
        except CycleNotRunning as exc:
            raise CycleFrozen(exc.message)

        parsed, error_response = self._parse_shift_input(request)
        if error_response is not None:
            return error_response

        scope = request.data.get("scope", "single")
        if scope not in ("single", "cascade"):
            return Response(
                {"scope": ["Must be 'single' or 'cascade'."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        override_fixed = bool(request.data.get("override_fixed", False))

        try:
            result = apply_task_shift(
                cycle_task,
                scope,
                delay_days=parsed["delay_days"],
                new_start_date=parsed["new_start_date"],
                new_end_date=parsed["new_end_date"],
                override_fixed=override_fixed,
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

    @action(detail=True, methods=["post", "delete"])
    def note(self, request, pk=None):
        # Dedicated endpoint for adding, updating, or removing a task's
        # note. note_text stays locked out of the generic PATCH on
        # purpose (see CycleTaskSerializer.update), so this is the only
        # way to touch it, keeping status changes and note edits from
        # ever being mixed into the same request.
        cycle_task = self.get_object()

        try:
            assert_cycle_is_running(cycle_task.cycle)
        except CycleNotRunning as exc:
            raise CycleFrozen(exc.message)

        if request.method == "DELETE":
            cycle_task.note_text = None
            cycle_task.save(update_fields=["note_text"])
            return Response(self.get_serializer(cycle_task).data, status=status.HTTP_200_OK)

        note_text = request.data.get("note_text")
        if not note_text or not str(note_text).strip():
            return Response(
                {"note_text": ["This field is required to add or update a note."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cycle_task.note_text = note_text
        cycle_task.save(update_fields=["note_text"])
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
        queryset = CycleActivity.objects.filter(cycle_id__in=owned_cycle_ids).distinct()

        cycle_id = self.request.query_params.get("cycle")
        if cycle_id:
            queryset = queryset.filter(cycle_id=cycle_id)

        return queryset

    def perform_update(self, serializer):
        # Only calculated_start_date/calculated_end_date can actually
        # change here, everything else is protected in
        # CycleActivitySerializer.update. An activity can be shrunk,
        # widened, or moved freely as long as every task anchored to it
        # still fits inside the new range, tasks are never moved to
        # make room, the resize is rejected instead.
        activity = serializer.instance

        try:
            assert_cycle_is_running(activity.cycle)
        except CycleNotRunning as exc:
            raise CycleFrozen(exc.message)

        new_start = serializer.validated_data.get(
            "calculated_start_date", activity.calculated_start_date
        )
        new_end = serializer.validated_data.get(
            "calculated_end_date", activity.calculated_end_date
        )

        from rest_framework.exceptions import ValidationError

        if new_start > new_end:
            raise ValidationError({
                "calculated_end_date": ["An activity cannot end before it starts."]
            })

        if new_start != activity.calculated_start_date or new_end != activity.calculated_end_date:
            child_ranges = activity.cycle_tasks.values_list(
                "calculated_start_date", "calculated_end_date"
            )
            violations = validate_activity_bounds(new_start, new_end, child_ranges)
            if violations:
                raise ValidationError({
                    "calculated_start_date": [
                        "This activity has tasks that would fall outside the new "
                        "date range. Move or resize the activity so every task "
                        "stays within it, task dates are not changed automatically."
                    ]
                })

        serializer.save()

    @action(detail=True, methods=["post", "delete"])
    def note(self, request, pk=None):
        # Same pattern as CycleTaskViewSet.note, note_text is locked out
        # of the generic PATCH here too (see CycleActivitySerializer.update).
        activity = self.get_object()

        try:
            assert_cycle_is_running(activity.cycle)
        except CycleNotRunning as exc:
            raise CycleFrozen(exc.message)

        if request.method == "DELETE":
            activity.note_text = None
            activity.save(update_fields=["note_text"])
            return Response(self.get_serializer(activity).data, status=status.HTTP_200_OK)

        note_text = request.data.get("note_text")
        if not note_text or not str(note_text).strip():
            return Response(
                {"note_text": ["This field is required to add or update a note."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        activity.note_text = note_text
        activity.save(update_fields=["note_text"])
        return Response(self.get_serializer(activity).data, status=status.HTTP_200_OK)


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
        self._reject_if_invalid(task, depends_on_task)
        serializer.save()

    def perform_update(self, serializer):
        task = serializer.validated_data.get("task", serializer.instance.task)
        depends_on_task = serializer.validated_data.get(
            "depends_on_task",
            serializer.instance.depends_on_task,
        )
        self._validate_editable_dependency_tasks(task, depends_on_task)
        self._reject_if_invalid(
            task, depends_on_task, exclude_dependency_id=serializer.instance.pk
        )
        serializer.save()

    def _validate_editable_dependency_tasks(self, task, depends_on_task):
        if task.template_id != depends_on_task.template_id:
            return

        if not user_can_edit_template(self.request.user, task.template):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You do not have permission to modify this template.")

    def _reject_if_invalid(self, task, depends_on_task, exclude_dependency_id=None):
        # Runs every rule this edge has to pass, circular chain, offset
        # conflict, fan-out capacity, and reports all of them together
        # if more than one is broken, instead of the user fixing one and
        # resubmitting into the next.
        violations = collect_dependency_violations(
            task, depends_on_task, exclude_dependency_id=exclude_dependency_id
        )
        if violations:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"depends_on_task": violations})

    @action(detail=False, methods=["post"])
    def validate(self, request):
        # Dry run for one proposed dependency edge, nothing is written.
        # Lets the frontend check each dependency the moment the user
        # picks it, showing every problem with that specific pair right
        # away, instead of only finding out something was wrong after
        # the user has already gone through every step and submitted.
        # Same checks perform_create/perform_update run.
        task_id = request.data.get("task")
        depends_on_task_id = request.data.get("depends_on_task")

        if not task_id or not depends_on_task_id:
            return Response(
                {"non_field_errors": ["Both task and depends_on_task are required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            task = TemplateTask.objects.select_related("template").get(pk=task_id)
            depends_on_task = TemplateTask.objects.select_related("template").get(
                pk=depends_on_task_id
            )
        except TemplateTask.DoesNotExist:
            return Response(
                {"non_field_errors": ["One or both tasks were not found."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        if task.template_id != depends_on_task.template_id:
            return Response(
                {
                    "valid": False,
                    "issues": [{
                        "error": "cross_template",
                        "message": "Task dependencies must stay within the same template.",
                    }],
                },
                status=status.HTTP_200_OK,
            )

        self._validate_editable_dependency_tasks(task, depends_on_task)

        violations = collect_dependency_violations(
            task,
            depends_on_task,
            exclude_dependency_id=request.data.get("exclude_dependency_id"),
        )

        return Response({"valid": not violations, "issues": violations}, status=status.HTTP_200_OK)