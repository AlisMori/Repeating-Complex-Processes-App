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
from cycles.dependency_engine import (
    DependencyConflict,
    assert_dependent_capacity,
    check_offset_conflict,
    copy_dependencies,
    revalidate_task_offsets,
    would_create_cycle,
)

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

            for template_task in template.template_tasks.all():
                start = cycle.start_date + timedelta(days=template_task.day_offset)
                duration = template_task.duration_days or 0
                cycle_task = CycleTask.objects.create(
                    cycle=cycle,
                    template_task=template_task,
                    task_name=template_task.task_name,
                    calculated_start_date=start,
                    calculated_end_date=start + timedelta(days=duration),
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

        return Response(
            CycleInstanceSerializer(cycle, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

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

        # Optional per-task overrides, keyed by the task's id on the
        # version being edited. Any task not mentioned here just carries
        # over unchanged, including its dependencies. New tasks (no
        # template_task_id) are not handled here, that stays on
        # template-tasks/ after the version exists.
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
                template_name=request.data.get("template_name", original_template.template_name),
                description=request.data.get("description", original_template.description),
                is_public=request.data.get("is_public", original_template.is_public),
                created_by_type=original_template.created_by_type,
                is_current_version=True,
            )

            UserTemplate.objects.create(
                user=request.user,
                template=new_template,
                access_type="owner",
            )

            # old TemplateTask.pk -> new TemplateTask instance, needed
            # below to rebuild TaskDependency edges onto the new version.
            task_id_map = {}

            for task in original_template.template_tasks.all():
                override = task_overrides.get(task.template_task_id, {})
                new_task = TemplateTask.objects.create(
                    template=new_template,
                    task_name=override.get("task_name", task.task_name),
                    description=override.get("description", task.description),
                    day_offset=override.get("day_offset", task.day_offset),
                    duration_days=override.get("duration_days", task.duration_days),
                    is_mandatory=override.get("is_mandatory", task.is_mandatory),
                    is_fixed_date=override.get("is_fixed_date", task.is_fixed_date),
                    reminder_lead_days=override.get("reminder_lead_days", task.reminder_lead_days),
                    note_text=override.get("note_text", task.note_text),
                )
                task_id_map[task.template_task_id] = new_task

            for activity in original_template.template_activities.all():
                TemplateActivity.objects.create(
                    template=new_template,
                    activity_name=activity.activity_name,
                    description=activity.description,
                    start_offset_days=activity.start_offset_days,
                    end_offset_days=activity.end_offset_days,
                    note_text=activity.note_text,
                )

            # A tasks[] item can optionally include "depends_on", a list of
            # OLD template_task_id values (prerequisites, on this same
            # version being edited). If present, it replaces that task's
            # dependencies entirely, this is how a task's upstream can be
            # set or changed as part of the edit, not just its offset. Any
            # task without an explicit "depends_on" just keeps its old
            # edges, copied via copy_dependencies below.
            explicit_dependency_task_ids = {
                old_id for old_id, item in task_overrides.items() if "depends_on" in item
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
                            {"tasks": [f"depends_on references unknown template_task_id {prerequisite_old_id}."]}
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
                    TaskDependency.objects.create(task=new_task, depends_on_task=new_depends_on)

        return Response(
            {
                "message": "New template version created successfully.",
                "template": TemplateSerializer(new_template).data,
            },
            status=status.HTTP_200_OK,
        )
    
    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        # Create a deep copy of an existing template, including its tasks,
        # activities, and tag relationships.
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

            task_map = {}

            for task in original_template.template_tasks.all():
                copied_task = TemplateTask.objects.create(
                    template=copied_template,
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

            for activity in original_template.template_activities.all():
                copied_activity = TemplateActivity.objects.create(
                    template=copied_template,
                    activity_name=activity.activity_name,
                    description=activity.description,
                    start_offset_days=activity.start_offset_days,
                    end_offset_days=activity.end_offset_days,
                    note_text=activity.note_text,
                )

                for activity_tag in TemplateActivityTag.objects.filter(
                    template_activity=activity
                ):
                    TemplateActivityTag.objects.create(
                        template_activity=copied_activity,
                        tag=activity_tag.tag,
                    )
            
            # Straight copy, offsets never change here, so no need to
            # re-validate them, just carry every edge across.
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
        # Share a template by creating an independent deep copy for another user.
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

            task_map = {}

            for task in original_template.template_tasks.all():
                copied_task = TemplateTask.objects.create(
                    template=shared_template,
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

            for activity in original_template.template_activities.all():
                TemplateActivity.objects.create(
                    template=shared_template,
                    activity_name=activity.activity_name,
                    description=activity.description,
                    start_offset_days=activity.start_offset_days,
                    end_offset_days=activity.end_offset_days,
                    note_text=activity.note_text,
                )

            # Straight copy, same as duplicate(), no offset changes here.
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
        return TemplateTask.objects.filter(
            template_id__in=Template.objects.filter(
                accessible_templates_q(self.request.user)
            ).values("pk")
        ).distinct()

    def perform_create(self, serializer):
        template = serializer.validated_data["template"]
        if not user_can_edit_template(self.request.user, template):
            raise PermissionDenied("You do not have permission to modify this template.")
        serializer.save()

    def perform_update(self, serializer):
        template = serializer.validated_data.get("template", serializer.instance.template)
        if not user_can_edit_template(self.request.user, template):
            raise PermissionDenied("You do not have permission to modify this template.")
        task = serializer.save()
        try:
            revalidate_task_offsets(task)
        except DependencyConflict as exc:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"day_offset": [exc.message]})


class TemplateActivityViewSet(viewsets.ModelViewSet):
    serializer_class = TemplateActivitySerializer
    permission_classes = [permissions.IsAuthenticated, IsTemplateOwnerOrSharedAccess]
    filter_backends = [SearchFilter]
    search_fields = ["activity_name", "description", "note_text"]

    def get_queryset(self):
        return TemplateActivity.objects.filter(
            template_id__in=Template.objects.filter(
                accessible_templates_q(self.request.user)
            ).values("pk")
        ).distinct()

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


