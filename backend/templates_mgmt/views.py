from django.contrib.auth import get_user_model
from datetime import timedelta
from django.db import transaction
from django.utils.dateparse import parse_date
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

from core.permissions import (
    IsOwner,
    IsTemplateOwnerOrSharedAccess,
    accessible_templates_q,
    user_can_access_template,
    user_can_edit_template,
)
from cycles.models import CycleActivity, CycleInstance, CycleTask, TaskDependency
from .scheduling import resolve_effective_offsets
from .models import (
    Template,
    TemplateTask,
    TemplateActivity,
    Tag,
    UserTemplate,
    TemplateTaskTag,
    TemplateActivityTag,
)

from .serializers import (
    TemplateSerializer,
    TemplateTaskSerializer,
    TemplateActivitySerializer,
    TagSerializer,
    TemplateTaskTagSerializer,
    TemplateActivityTagSerializer,
)


User = get_user_model()

def recalculate_activity_offsets(activity):
    linked_tasks = activity.template_tasks.all()

    if not linked_tasks.exists():
        return

    start_offset = min(task.day_offset for task in linked_tasks)
    end_offset = max(
        task.day_offset + (task.duration_days or 0)
        for task in linked_tasks
    )

    activity.start_offset_days = start_offset
    activity.end_offset_days = end_offset
    activity.save(update_fields=["start_offset_days", "end_offset_days"])

class TemplateViewSet(viewsets.ModelViewSet):
    serializer_class = TemplateSerializer
    permission_classes = [permissions.IsAuthenticated, IsTemplateOwnerOrSharedAccess]
    filter_backends = [SearchFilter]
    search_fields = ["template_name", "description"]

    def get_queryset(self):
        return Template.objects.filter(
            accessible_templates_q(self.request.user)
        ).distinct()

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


    @action(detail=True, methods=["post"])
    def create_cycle(self, request, pk=None):
        template = self.get_object()

        if not user_can_access_template(request.user, template):
            raise PermissionDenied(
                "You do not have permission to create a cycle from this template."
            )

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

        from cycles.serializers import CycleInstanceSerializer
        from cycles.services import generate_cycle_runtime_records

        with transaction.atomic():
            cycle = CycleInstance.objects.create(
                user=request.user,
                template=template,
                cycle_name=cycle_name,
                start_date=parsed_start_date,
            )

            template_tasks = list(template.template_tasks.all())
            nodes = {
                t.template_task_id: {
                    "offset": t.day_offset,
                    "duration": t.duration_days or 1,
                    "fixed": t.is_fixed_date,
                }
                for t in template_tasks
            }
            edges = {}
            for dep in TaskDependency.objects.filter(task__template=template):
                edges.setdefault(dep.task_id, []).append(dep.depends_on_task_id)

            effective, circular, conflicts = resolve_effective_offsets(nodes, edges)

            for template_task in template_tasks:
                eff_start, eff_end = effective.get(
                    template_task.template_task_id,
                    (template_task.day_offset, template_task.day_offset + (template_task.duration_days or 1)),
                )
                start = cycle.start_date + timedelta(days=eff_start)
                end = cycle.start_date + timedelta(days=eff_end)
                CycleTask.objects.create(
                    cycle=cycle,
                    template_task=template_task,
                    task_name=template_task.task_name,
                    calculated_start_date=start,
                    calculated_end_date=end,
                    is_mandatory=template_task.is_mandatory,
                    is_fixed_date=template_task.is_fixed_date,
                    reminder_lead_days=template_task.reminder_lead_days,
                    note_text=template_task.note_text,
                )

            for template_activity in template.template_activities.all():
                CycleActivity.objects.create(
                    cycle=cycle,
                    template_activity=template_activity,
                    activity_name=template_activity.activity_name,
                    calculated_start_date=cycle.start_date + timedelta(days=template_activity.start_offset_days),
                    calculated_end_date=cycle.start_date + timedelta(days=template_activity.end_offset_days),
                    note_text=template_activity.note_text,
                )

        from cycles.serializers import CycleInstanceSerializer

        response_data = CycleInstanceSerializer(cycle, context=self.get_serializer_context()).data
        if circular or conflicts:
            id_to_name = {t.template_task_id: t.task_name for t in template_tasks}
            response_data["schedule_warnings"] = {
                "circular_dependency_tasks": [id_to_name.get(tid, tid) for tid in circular],
                "fixed_date_conflicts": [id_to_name.get(tid, tid) for tid in conflicts],
            }

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


    def update(self, request, *args, **kwargs):
        original_template = self.get_object()

        task_overrides = {
            item["template_task_id"]: item
            for item in request.data.get("tasks", [])
            if item.get("template_task_id")
        }

        with transaction.atomic():
            original_template.is_current_version = False
            original_template.save()

            new_template = Template.objects.create(
                user=request.user,
                parent_template=original_template.parent_template or original_template,
                template_version=original_template.template_version + 1,
                template_name=request.data.get(
                    "template_name",
                    original_template.template_name,
                ),
                description=request.data.get(
                    "description",
                    original_template.description,
                ),
                is_public=request.data.get(
                    "is_public",
                    original_template.is_public,
                ),
                created_by_type=original_template.created_by_type,
                is_current_version=True,
            )

            UserTemplate.objects.create(
                user=request.user,
                template=new_template,
                access_type="owner",
            )

            activity_map = {}

            for activity in original_template.template_activities.all():
                new_activity = TemplateActivity.objects.create(
                    template=new_template,
                    activity_name=activity.activity_name,
                    description=activity.description,
                    start_offset_days=activity.start_offset_days,
                    end_offset_days=activity.end_offset_days,
                    note_text=activity.note_text,
                )

                activity_map[activity.template_activity_id] = new_activity

            task_id_map = {}

            for task in original_template.template_tasks.all():
                override = task_overrides.get(task.template_task_id, {})

                old_activity_id = override.get(
                    "template_activity",
                    task.template_activity_id,
                )

                new_task = TemplateTask.objects.create(
                    template=new_template,
                    template_activity=activity_map.get(old_activity_id),
                    task_name=override.get("task_name", task.task_name),
                    description=override.get("description", task.description),
                    day_offset=override.get("day_offset", task.day_offset),
                    duration_days=override.get("duration_days", task.duration_days),
                    is_mandatory=override.get("is_mandatory", task.is_mandatory),
                    is_fixed_date=override.get("is_fixed_date", task.is_fixed_date),
                    reminder_lead_days=override.get(
                        "reminder_lead_days",
                        task.reminder_lead_days,
                    ),
                    note_text=override.get("note_text", task.note_text),
                )

                task_id_map[task.template_task_id] = new_task

            explicit_dependency_task_ids = {
                old_id
                for old_id, item in task_overrides.items()
                if "depends_on" in item
            }

            copy_dependencies(
                original_template,
                task_id_map,
                validate_offsets=True,
                skip_task_ids=explicit_dependency_task_ids,
            )

            for old_id in explicit_dependency_task_ids:
                new_task = task_id_map[old_id]

                for prerequisite_old_id in task_overrides[old_id]["depends_on"]:
                    if prerequisite_old_id not in task_id_map:
                        from rest_framework.exceptions import ValidationError

                        raise ValidationError(
                            {
                                "tasks": [
                                    f"depends_on references unknown template_task_id {prerequisite_old_id}."
                                ]
                            }
                        )

                    new_depends_on = task_id_map[prerequisite_old_id]

                    try:
                        if would_create_cycle(new_task, new_depends_on):
                            raise DependencyConflict(
                                error="circular_dependency",
                                message=(
                                    f"Task '{new_task.task_name}' cannot depend on "
                                    f"'{new_depends_on.task_name}', it would create a circular chain."
                                ),
                            )

                        check_offset_conflict(new_task, new_depends_on)
                        assert_dependent_capacity(new_depends_on)

                    except DependencyConflict as exc:
                        from rest_framework.exceptions import ValidationError

                        raise ValidationError({"tasks": [exc.message]})

                    TaskDependency.objects.create(
                        task=new_task,
                        depends_on_task=new_depends_on,
                    )

        return Response(
            {
                "message": "New template version created successfully.",
                "template": TemplateSerializer(new_template).data,
            },
            status=status.HTTP_200_OK,
        )
    
    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        original_template = self.get_object()

        with transaction.atomic():
            copied_template = Template.objects.create(
                user=request.user,
                template_version=1,
                template_name=f"{original_template.template_name} Copy",
                description=original_template.description,
                is_public=False,
                created_by_type="user",
            )

            UserTemplate.objects.create(
                user=request.user,
                template=copied_template,
                access_type="owner",
            )

            activity_map = {}

            for activity in original_template.template_activities.all():
                copied_activity = TemplateActivity.objects.create(
                    template=copied_template,
                    activity_name=activity.activity_name,
                    description=activity.description,
                    start_offset_days=activity.start_offset_days,
                    end_offset_days=activity.end_offset_days,
                    note_text=activity.note_text,
                )

                activity_map[activity.template_activity_id] = copied_activity

                for activity_tag in TemplateActivityTag.objects.filter(
                    template_activity=activity
                ):
                    TemplateActivityTag.objects.create(
                        template_activity=copied_activity,
                        tag=activity_tag.tag,
                    )

            task_map = {}

            for task in original_template.template_tasks.all():
                copied_task = TemplateTask.objects.create(
                    template=copied_template,
                    template_activity=activity_map.get(task.template_activity_id),
                    task_name=task.task_name,
                    description=task.description,
                    day_offset=task.day_offset,
                    duration_days=task.duration_days,
                    is_mandatory=task.is_mandatory,
                    is_fixed_date=task.is_fixed_date,
                    reminder_lead_days=task.reminder_lead_days,
                    note_text=task.note_text,
                )

                task_map[task.template_task_id] = copied_task

                for task_tag in TemplateTaskTag.objects.filter(template_task=task):
                    TemplateTaskTag.objects.create(
                        template_task=copied_task,
                        tag=task_tag.tag,
                    )

            copy_dependencies(original_template, task_map)

        return Response(
            {
                "message": "Template duplicated successfully.",
                "template": TemplateSerializer(copied_template).data,
            },
            status=status.HTTP_201_CREATED,
        )
    
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
        original_template = self.get_object()
        username = request.data.get("username")

        if not username:
            return Response(
                {"username": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.contrib.auth import get_user_model

        User = get_user_model()

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
                template_name=f"{original_template.template_name} Shared Copy",
                description=original_template.description,
                is_public=False,
                created_by_type="shared",
            )

            UserTemplate.objects.create(
                user=target_user,
                template=shared_template,
                access_type="shared",
            )

            activity_map = {}

            for activity in original_template.template_activities.all():
                copied_activity = TemplateActivity.objects.create(
                    template=shared_template,
                    activity_name=activity.activity_name,
                    description=activity.description,
                    start_offset_days=activity.start_offset_days,
                    end_offset_days=activity.end_offset_days,
                    note_text=activity.note_text,
                )

                activity_map[activity.template_activity_id] = copied_activity

            task_map = {}

            for task in original_template.template_tasks.all():
                copied_task = TemplateTask.objects.create(
                    template=shared_template,
                    template_activity=activity_map.get(task.template_activity_id),
                    task_name=task.task_name,
                    description=task.description,
                    day_offset=task.day_offset,
                    duration_days=task.duration_days,
                    is_mandatory=task.is_mandatory,
                    is_fixed_date=task.is_fixed_date,
                    reminder_lead_days=task.reminder_lead_days,
                    note_text=task.note_text,
                )

                task_map[task.template_task_id] = copied_task

            copy_dependencies(original_template, task_map)

        return Response(
            {
                "message": "Template shared successfully.",
                "template": TemplateSerializer(shared_template).data,
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

    def perform_create(self, serializer):
        template = serializer.validated_data["template"]

        if not user_can_edit_template(self.request.user, template):
            raise PermissionDenied("You do not have permission to modify this template.")

        task = serializer.save()

        if task.template_activity:
            recalculate_activity_offsets(task.template_activity)

    def perform_update(self, serializer):
        template = serializer.validated_data.get(
            "template",
            serializer.instance.template,
        )

        if not user_can_edit_template(self.request.user, template):
            raise PermissionDenied("You do not have permission to modify this template.")

        old_activity = serializer.instance.template_activity

        task = serializer.save()

        try:
            revalidate_task_offsets(task)
        except DependencyConflict as exc:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"day_offset": [exc.message]})

        if old_activity:
            recalculate_activity_offsets(old_activity)

        if task.template_activity and task.template_activity != old_activity:
            recalculate_activity_offsets(task.template_activity)

    def perform_destroy(self, instance):
        activity = instance.template_activity
        instance.delete()

        if activity:
            recalculate_activity_offsets(activity)

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

    def perform_create(self, serializer):
        template = serializer.validated_data["template"]
        if not user_can_edit_template(self.request.user, template):
            raise PermissionDenied("You do not have permission to modify this template.")
        serializer.save()

    def perform_update(self, serializer):
        template = serializer.validated_data.get("template", serializer.instance.template)
        if not user_can_edit_template(self.request.user, template):
            raise PermissionDenied("You do not have permission to modify this template.")
        serializer.save()


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
