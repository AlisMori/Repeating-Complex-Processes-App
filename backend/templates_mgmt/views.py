from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpResponse
from django.utils.dateparse import parse_date
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

from core.permissions import (
    IsOwner,
    IsTemplateOwnerOrSharedAccess,
    accessible_templates_q,
    user_can_access_template,
    user_can_edit_template,
)
from cycles.dependency_engine import (
    DependencyConflict,
    revalidate_task_offsets,
)
from cycles.services import generate_cycle_runtime_records, validate_activity_bounds
from cycles.models import CycleInstance, TaskDependency
from .scheduling import resolve_effective_offsets
from .services import (
    deep_copy_template_contents,
    expand_activity_to_include_task,
    fork_new_version,
    get_editable_template,
    maybe_shrink_activity,
    new_version_payload,
)
from .bulk_structure import validate_structure_payload, apply_structure_payload
from .export import (
    SUPPORTED_FORMATS,
    WRITERS,
    template_to_intermediate,
)
from .models import (
    Template,
    TemplateCategory,
    TemplateTask,
    TemplateActivity,
    Tag,
    UserTemplate,
    TemplateTaskTag,
    TemplateActivityTag,
)

from .serializers import (
    TemplateSerializer,
    TemplateCategorySerializer,
    TemplateTaskSerializer,
    TemplateActivitySerializer,
    TagSerializer,
    TemplateTaskTagSerializer,
    TemplateActivityTagSerializer,
)


User = get_user_model()


class TemplateViewSet(viewsets.ModelViewSet):
    serializer_class = TemplateSerializer
    permission_classes = [permissions.IsAuthenticated, IsTemplateOwnerOrSharedAccess]
    filter_backends = [SearchFilter]
    search_fields = ["template_name", "description"]

    def get_queryset(self):
        # A list/search should only ever show the current tip of each
        # template's version lineage — every edit forks a new Template
        # row, so without this filter every past version (10+ for a
        # template edited 10 times) would show up as its own separate
        # entry in the picker/library. retrieve/update/destroy/actions
        # are untouched: a running cycle still needs to reach the
        # exact frozen version it was created from by id.
        queryset = Template.objects.filter(
            accessible_templates_q(self.request.user)
        ).distinct()
        if self.action == "list":
            queryset = queryset.filter(is_current_version=True)
        return queryset

    def perform_create(self, serializer):
        template = serializer.save(
            user=self.request.user,
            created_by_type="user",
        )
        UserTemplate.objects.get_or_create(
            user=self.request.user,
            template=template,
            defaults={"access_type": "owner"},
        )

    def update(self, request, *args, **kwargs):
        original_template = self.get_object()
        if not user_can_edit_template(request.user, original_template):
            raise PermissionDenied("You do not have permission to modify this template.")

        with transaction.atomic():
            new_template, _, _, forked = get_editable_template(original_template, request.user)

            for field in ("template_name", "description", "is_public"):
                if field in request.data:
                    setattr(new_template, field, request.data[field])

            if "category" in request.data:
                category_value = request.data["category"]
                if category_value in (None, "", "null"):
                    new_template.category = None
                else:
                    try:
                        new_template.category = TemplateCategory.objects.get(
                            pk=category_value, user=request.user
                        )
                    except TemplateCategory.DoesNotExist:
                        raise ValidationError(
                            {"category": ["Category not found, or it belongs to another user."]}
                        )

            new_template.save()

        return Response(
            {
                "message": (
                    "New template version created successfully." if forked
                    else "Template updated successfully."
                ),
                "template": TemplateSerializer(new_template).data,
            },
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        # Cycles already created from this template must survive the
        # delete, they're a snapshot of what the template looked like
        # at create_cycle time, not a live view of it, deleting the
        # template later shouldn't erase someone's history of a cycle
        # they actually ran. CycleInstance.template (and CycleTask.
        # template_task / CycleActivity.template_activity) are
        # SET_NULL on delete for exactly this reason: the rows stay,
        # only the now-meaningless link back to the deleted template
        # is cleared. Anything still running is shut down first so
        # nothing keeps ticking against a template that no longer
        # exists to validate its own dependency rules against.
        template = self.get_object()
        if not user_can_edit_template(request.user, template):
            raise PermissionDenied("You do not have permission to delete this template.")

        with transaction.atomic():
            template.cycle_instances.filter(status="running").update(status="shut_down")
            self.perform_destroy(template)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        # "Copy template" in the frontend: a plain version fork, a new
        # version in the SAME lineage (Vx+1), an exact copy with
        # nothing edited, the original is frozen exactly like any
        # other version fork (see fork_new_version). This action's
        # permission class already requires edit rights to reach it
        # at all (POST is not a safe method), so there's no separate
        # "read-only" caller case to handle here.
        original_template = self.get_object()
        if not user_can_edit_template(request.user, original_template):
            raise PermissionDenied("You do not have permission to duplicate this template.")

        with transaction.atomic():
            new_template, _, _ = fork_new_version(original_template, request.user)
            if request.data.get("template_name"):
                new_template.template_name = request.data["template_name"]
                new_template.save(update_fields=["template_name"])

        return Response(
            {
                "message": "Template copied as a new version successfully.",
                "template": TemplateSerializer(new_template).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def create_cycle(self, request, pk=None):
        template = self.get_object()
        if not user_can_access_template(request.user, template):
            raise PermissionDenied("You do not have permission to create a cycle from this template.")

        start_date = request.data.get("start_date")
        cycle_name = request.data.get("cycle_name") or template.template_name
        if not start_date:
            return Response(
                {"start_date": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        parsed_start_date = parse_date(start_date)
        if parsed_start_date is None:
            return Response(
                {"start_date": ["Date has wrong format. Use YYYY-MM-DD."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            cycle = CycleInstance.objects.create(
                user=request.user,
                template=template,
                cycle_name=cycle_name,
                start_date=parsed_start_date,
            )
            result = generate_cycle_runtime_records(cycle)

        from cycles.serializers import CycleInstanceSerializer

        response_data = CycleInstanceSerializer(cycle, context=self.get_serializer_context()).data
        if result.get("schedule_warnings"):
            response_data["schedule_warnings"] = result["schedule_warnings"]

        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def timeline_preview(self, request, pk=None):
        """
        Returns the dependency-resolved timeline for this template:
        every task/activity's effective start/end day once dependency
        chains are accounted for. This is the same resolution
        create_cycle uses, so a template's preview always matches
        what a cycle created from it will actually look like.
        """
        template = self.get_object()
        if not user_can_access_template(request.user, template):
            raise PermissionDenied("You do not have permission to view this template.")

        template_tasks = list(template.template_tasks.all())
        template_activities = list(template.template_activities.all())

        nodes = {
            t.template_task_id: {
                "offset": t.day_offset,
                "duration": t.duration_days or 1,
                "fixed": t.is_fixed_date,
            }
            for t in template_tasks
        }
        edges = {}
        dep_name_by_task_id = {}
        for dep in TaskDependency.objects.filter(task__template=template).select_related("depends_on_task"):
            edges.setdefault(dep.task_id, []).append(dep.depends_on_task_id)
            dep_name_by_task_id[dep.task_id] = dep.depends_on_task.task_name

        effective, circular, conflicts = resolve_effective_offsets(nodes, edges)

        task_bars = []
        for t in template_tasks:
            start, end = effective.get(
                t.template_task_id,
                (t.day_offset, t.day_offset + (t.duration_days or 1)),
            )
            task_bars.append({
                "template_task_id": t.template_task_id,
                "name": t.task_name,
                "start": start,
                "end": end,
                "is_mandatory": t.is_mandatory,
                "is_fixed_date": t.is_fixed_date,
                "dep_name": dep_name_by_task_id.get(t.template_task_id),
                "has_circular_dependency": t.template_task_id in circular,
                "has_fixed_date_conflict": t.template_task_id in conflicts,
            })

        activity_bars = [
            {
                "template_activity_id": a.template_activity_id,
                "name": a.activity_name,
                "start": a.start_offset_days,
                "end": a.end_offset_days,
            }
            for a in template_activities
        ]

        all_ends = [b["end"] for b in task_bars] + [b["end"] for b in activity_bars]
        max_day = max(all_ends) if all_ends else 1

        return Response({
            "task_bars": task_bars,
            "activity_bars": activity_bars,
            "max_day": max_day,
        })

    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        template = self.get_object()
        payload = self.get_serializer(template).data
        payload["template_tasks"] = TemplateTaskSerializer(
            template.template_tasks.all(),
            many=True,
            context=self.get_serializer_context(),
        ).data
        payload["template_activities"] = TemplateActivitySerializer(
            template.template_activities.all(),
            many=True,
            context=self.get_serializer_context(),
        ).data
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        # A real downloadable file (json, csv, or xlsx), for taking a
        # template out of the app entirely, backup, sharing outside the
        # system, or reimporting later, either here or somewhere else.
        # Different from export above, which returns the same data as
        # a plain API response for in-app use.
        template = self.get_object()
        if not user_can_access_template(request.user, template):
            raise PermissionDenied("You do not have permission to export this template.")

        file_format = (request.query_params.get("file_format") or "json").lower()
        if file_format not in SUPPORTED_FORMATS:
            return Response(
                {"file_format": [f"Must be one of: {', '.join(SUPPORTED_FORMATS)}."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = template_to_intermediate(template)
        file_bytes = WRITERS[file_format](data)

        content_types = {
            "json": "application/json",
            "csv": "text/csv",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        safe_name = "".join(
            c if c.isalnum() or c in (" ", "-", "_") else "_" for c in template.template_name
        ).strip() or "template"
        filename = f"{safe_name}_v{template.template_version}.{file_format}"

        response = HttpResponse(file_bytes, content_type=content_types[file_format])
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @action(detail=True, methods=["get"])
    def versions(self, request, pk=None):
        template = self.get_object()

        root_template = template.parent_template or template

        version_list = Template.objects.filter(
            parent_template=root_template
        ) | Template.objects.filter(
            template_id=root_template.template_id
        )

        version_list = version_list.order_by("template_version")

        return Response(
            TemplateSerializer(version_list, many=True).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def share(self, request, pk=None):
        # Share a template by creating an independent deep copy for another user.
        original_template = self.get_object()
        username = request.data.get("username")

        if not username:
            return Response(
                {"username": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            target_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        with transaction.atomic():
            shared_template = Template.objects.create(
                user=target_user,
                template_version=1,
                parent_template=None,
                is_current_version=True,
                template_name=f"{original_template.template_name} Shared Copy",
                description=original_template.description,
                is_public=False,
                created_by_type="shared",
                # category is deliberately NOT carried over — it's a
                # per-user classification, and the recipient wouldn't
                # own the original's category. They can set their own.
            )

            UserTemplate.objects.create(
                user=target_user,
                template=shared_template,
                access_type="shared",
            )

            deep_copy_template_contents(original_template, shared_template)

        return Response(
            {
                "message": "Template shared successfully.",
                "template": TemplateSerializer(shared_template).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def save_structure(self, request, pk=None):
        """Replaces this template's ENTIRE tasks/activities/dependencies
        structure in one atomic write — one new version, created once,
        complete and correct from the moment it exists. See
        bulk_structure.py for why this replaced the old one-API-call-
        per-field approach.

        Body: { activities: [...], tasks: [...], dependencies: [...] }
        — see bulk_structure.py's docstring for the exact shape.
        """
        template = self.get_object()
        errors = validate_structure_payload(request.data, request.user)
        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        new_template, activity_by_local_id, task_by_local_id = apply_structure_payload(
            template, request.data, request.user
        )

        return Response(
            {
                "new_template_version": new_version_payload(new_template),
                "activities": {
                    local_id: TemplateActivitySerializer(activity).data
                    for local_id, activity in activity_by_local_id.items()
                },
                "tasks": {
                    local_id: TemplateTaskSerializer(task).data
                    for local_id, task in task_by_local_id.items()
                },
            },
            status=status.HTTP_201_CREATED,
        )


class TemplateTaskViewSet(viewsets.ModelViewSet):
    serializer_class = TemplateTaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsTemplateOwnerOrSharedAccess]
    filter_backends = [SearchFilter]
    search_fields = ["task_name", "description", "note_text"]

    def get_queryset(self):
        queryset = TemplateTask.objects.filter(
            template_id__in=Template.objects.filter(
                accessible_templates_q(self.request.user)
            ).values("pk")
        ).distinct()

        template_id = self.request.query_params.get("template")
        if template_id:
            queryset = queryset.filter(template_id=template_id)

        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        template = serializer.validated_data["template"]
        if not user_can_edit_template(request.user, template):
            raise PermissionDenied("You do not have permission to modify this template.")

        with transaction.atomic():
            new_template, activity_map, _, forked = get_editable_template(template, request.user)

            incoming_activity = serializer.validated_data.get("template_activity")
            new_activity = (
                activity_map.get(incoming_activity.template_activity_id)
                if incoming_activity is not None
                else None
            )

            new_task = TemplateTask.objects.create(
                template=new_template,
                template_activity=new_activity,
                task_name=serializer.validated_data["task_name"],
                description=serializer.validated_data.get("description"),
                day_offset=serializer.validated_data["day_offset"],
                duration_days=serializer.validated_data.get("duration_days"),
                is_mandatory=serializer.validated_data.get("is_mandatory", True),
                is_fixed_date=serializer.validated_data.get("is_fixed_date", False),
                reminder_lead_days=serializer.validated_data.get("reminder_lead_days"),
                note_text=serializer.validated_data.get("note_text"),
            )
            expand_activity_to_include_task(new_task)

        response_data = TemplateTaskSerializer(new_task, context=self.get_serializer_context()).data
        if forked:
            response_data["new_template_version"] = new_version_payload(new_template)
        return Response(response_data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        template = instance.template
        if not user_can_edit_template(request.user, template):
            raise PermissionDenied("You do not have permission to modify this template.")

        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.get("partial", False)
        )
        serializer.is_valid(raise_exception=True)

        old_start = instance.day_offset
        old_end = instance.day_offset + (instance.duration_days or 0)
        old_activity_id = instance.template_activity_id

        with transaction.atomic():
            new_template, activity_map, task_id_map, forked = get_editable_template(template, request.user)
            copied_task = task_id_map[instance.template_task_id]
            old_activity_copy = activity_map.get(old_activity_id)

            for field, value in serializer.validated_data.items():
                if field in ("template", "note_text"):
                    # template can't be moved between templates through this
                    # endpoint, note_text goes through the dedicated note
                    # action instead, see TemplateTaskViewSet.note.
                    continue
                if field == "template_activity":
                    value = activity_map.get(value.template_activity_id) if value is not None else None
                setattr(copied_task, field, value)
            copied_task.save()

            try:
                revalidate_task_offsets(copied_task)
            except DependencyConflict as exc:
                raise ValidationError({"day_offset": [exc.message]})

            expand_activity_to_include_task(copied_task)
            if old_activity_copy is not None and old_activity_copy.pk != (
                copied_task.template_activity_id
            ):
                # The task moved to a different activity (or was unlinked),
                # the old activity may no longer need the room this task
                # used to take up.
                maybe_shrink_activity(old_activity_copy, old_start, old_end)
            elif copied_task.template_activity_id is not None:
                maybe_shrink_activity(copied_task.template_activity, old_start, old_end)

        response_data = TemplateTaskSerializer(copied_task, context=self.get_serializer_context()).data
        if forked:
            response_data["new_template_version"] = new_version_payload(new_template)
        return Response(response_data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        template = instance.template
        if not user_can_edit_template(request.user, template):
            raise PermissionDenied("You do not have permission to modify this template.")

        old_start = instance.day_offset
        old_end = instance.day_offset + (instance.duration_days or 0)
        old_activity_id = instance.template_activity_id

        with transaction.atomic():
            new_template, activity_map, task_id_map, forked = get_editable_template(template, request.user)
            copied_task = task_id_map.get(instance.template_task_id)
            copied_activity = activity_map.get(old_activity_id)
            if copied_task is not None:
                copied_task.delete()
            maybe_shrink_activity(copied_activity, old_start, old_end)

        response = {
            "message": (
                "Task removed, a new template version was created." if forked
                else "Task removed."
            ),
        }
        if forked:
            response["new_template_version"] = new_version_payload(new_template)
        return Response(response, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post", "delete"])
    def note(self, request, pk=None):
        # Adding, updating, or removing a note never creates a new
        # version, this mutates note_text on the current version's row
        # directly (the one exception to "any change forks a version").
        task = self.get_object()
        if not user_can_edit_template(request.user, task.template):
            raise PermissionDenied("You do not have permission to modify this template.")

        if request.method == "DELETE":
            task.note_text = None
            task.save(update_fields=["note_text"])
            return Response(self.get_serializer(task).data, status=status.HTTP_200_OK)

        note_text = request.data.get("note_text")
        if not note_text or not str(note_text).strip():
            return Response(
                {"note_text": ["This field is required to add or update a note."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task.note_text = note_text
        task.save(update_fields=["note_text"])
        return Response(self.get_serializer(task).data, status=status.HTTP_200_OK)


class TemplateActivityViewSet(viewsets.ModelViewSet):
    serializer_class = TemplateActivitySerializer
    permission_classes = [permissions.IsAuthenticated, IsTemplateOwnerOrSharedAccess]
    filter_backends = [SearchFilter]
    search_fields = ["activity_name", "description", "note_text"]

    def get_queryset(self):
        queryset = TemplateActivity.objects.filter(
            template_id__in=Template.objects.filter(
                accessible_templates_q(self.request.user)
            ).values("pk")
        ).distinct()

        template_id = self.request.query_params.get("template")
        if template_id:
            queryset = queryset.filter(template_id=template_id)

        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        template = serializer.validated_data["template"]
        if not user_can_edit_template(request.user, template):
            raise PermissionDenied("You do not have permission to modify this template.")

        with transaction.atomic():
            new_template, _, _, forked = get_editable_template(template, request.user)
            new_activity = TemplateActivity.objects.create(
                template=new_template,
                activity_name=serializer.validated_data["activity_name"],
                description=serializer.validated_data.get("description"),
                start_offset_days=serializer.validated_data["start_offset_days"],
                end_offset_days=serializer.validated_data["end_offset_days"],
                note_text=serializer.validated_data.get("note_text"),
            )

        response_data = TemplateActivitySerializer(
            new_activity, context=self.get_serializer_context()
        ).data
        if forked:
            response_data["new_template_version"] = new_version_payload(new_template)
        return Response(response_data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        # An activity can be shrunk, widened, or moved as long as every
        # task anchored to it stays inside the new range, tasks are
        # never adjusted to make room, the resize is rejected instead
        # (same rule as CycleActivityViewSet.perform_update).
        instance = self.get_object()
        template = instance.template
        if not user_can_edit_template(request.user, template):
            raise PermissionDenied("You do not have permission to modify this template.")

        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.get("partial", False)
        )
        serializer.is_valid(raise_exception=True)

        new_start = serializer.validated_data.get("start_offset_days", instance.start_offset_days)
        new_end = serializer.validated_data.get("end_offset_days", instance.end_offset_days)

        if new_start > new_end:
            raise ValidationError({
                "end_offset_days": ["An activity cannot end before it starts."]
            })

        if new_start != instance.start_offset_days or new_end != instance.end_offset_days:
            child_ranges = [
                (t.day_offset, t.day_offset + (t.duration_days or 0))
                for t in instance.template_tasks.all()
            ]
            violations = validate_activity_bounds(new_start, new_end, child_ranges)
            if violations:
                raise ValidationError({
                    "start_offset_days": [
                        "This activity has tasks that would fall outside the new "
                        "offset range. Move or resize the activity so every task "
                        "stays within it, task offsets are not changed automatically."
                    ]
                })

        with transaction.atomic():
            new_template, activity_map, _, forked = get_editable_template(template, request.user)
            copied_activity = activity_map[instance.template_activity_id]

            for field in ("activity_name", "description", "start_offset_days", "end_offset_days"):
                if field in serializer.validated_data:
                    setattr(copied_activity, field, serializer.validated_data[field])
            copied_activity.save()

        response_data = TemplateActivitySerializer(
            copied_activity, context=self.get_serializer_context()
        ).data
        if forked:
            response_data["new_template_version"] = new_version_payload(new_template)
        return Response(response_data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        # Deleting an activity deletes every task still linked to it too
        # (frontend is expected to confirm this with the user first).
        instance = self.get_object()
        template = instance.template
        if not user_can_edit_template(request.user, template):
            raise PermissionDenied("You do not have permission to modify this template.")

        with transaction.atomic():
            new_template, activity_map, _, forked = get_editable_template(template, request.user)
            copied_activity = activity_map.get(instance.template_activity_id)
            if copied_activity is not None:
                copied_activity.template_tasks.all().delete()
                copied_activity.delete()

        response = {
            "message": (
                "Activity and its tasks removed, a new template version was created." if forked
                else "Activity and its tasks removed."
            ),
        }
        if forked:
            response["new_template_version"] = new_version_payload(new_template)
        return Response(response, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post", "delete"])
    def note(self, request, pk=None):
        # Same pattern as TemplateTaskViewSet.note, never forks a version.
        activity = self.get_object()
        if not user_can_edit_template(request.user, activity.template):
            raise PermissionDenied("You do not have permission to modify this template.")

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


class TagViewSet(viewsets.ModelViewSet):
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    filter_backends = [SearchFilter]
    search_fields = ["tag_name"]

    def get_queryset(self):
        # Users only see their own tags.
        return Tag.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # The logged-in user automatically becomes the owner of the tag.
        serializer.save(user=self.request.user)

    def update(self, request, *args, **kwargs):
        # A tag is never renamed in place. Every task/activity already
        # tagged with it must keep meaning exactly what it did when
        # tagged, so "editing" a tag creates a brand new tag with the
        # new name instead, and leaves the original (and everything
        # assigned to it) completely untouched. The new tag starts
        # with zero assignments — attaching it to tasks/activities is
        # a separate, later step, same as any newly created tag.
        instance = self.get_object()
        serializer = self.get_serializer(data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        new_tag_name = serializer.validated_data.get("tag_name", instance.tag_name)

        new_tag = Tag.objects.create(user=request.user, tag_name=new_tag_name)

        return Response(
            {
                "message": (
                    "A new tag was created with this name. The previous tag "
                    "and everything already tagged with it are unchanged."
                ),
                "tag": TagSerializer(new_tag).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        assigned_tasks = TemplateTaskTag.objects.filter(tag=instance).exists()
        assigned_activities = TemplateActivityTag.objects.filter(tag=instance).exists()
        if assigned_tasks or assigned_activities:
            raise ValidationError(
                "This tag is still assigned to at least one task or activity. "
                "Remove it from everything using it before deleting the tag."
            )
        return super().destroy(request, *args, **kwargs)


class TemplateCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = TemplateCategorySerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    filter_backends = [SearchFilter]
    search_fields = ["category_name"]

    def get_queryset(self):
        return TemplateCategory.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def update(self, request, *args, **kwargs):
        # Unlike Tag, a category IS renamed in place — a template's
        # link to it is just a name lookup (category_name shown via
        # TemplateSerializer), nothing needs to stay frozen against a
        # rename the way a tag's existing task/activity assignments do.
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.templates.exists():
            raise ValidationError(
                "This category is still assigned to at least one template "
                "(including past versions). Move every template using it to "
                "another category first, or rename this one instead of "
                "deleting it."
            )
        return super().destroy(request, *args, **kwargs)


class TemplateTaskTagViewSet(viewsets.ModelViewSet):
    serializer_class = TemplateTaskTagSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return TemplateTaskTag.objects.filter(
            template_task__template__user=self.request.user
        )


class TemplateActivityTagViewSet(viewsets.ModelViewSet):
    serializer_class = TemplateActivityTagSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return TemplateActivityTag.objects.filter(
            template_activity__template__user=self.request.user
        )