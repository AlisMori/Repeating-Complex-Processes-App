from django.contrib.auth import get_user_model
from datetime import timedelta
from django.db import transaction
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
    copy_dependencies,
    revalidate_task_offsets,
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

def expand_activity_to_include_task(task):
    activity = task.template_activity

    if activity is None:
        return

    task_start = task.day_offset
    task_end = task.day_offset + (task.duration_days or 0)

    updated_fields = []

    if task_start < activity.start_offset_days:
        activity.start_offset_days = task_start
        updated_fields.append("start_offset_days")

    if task_end > activity.end_offset_days:
        activity.end_offset_days = task_end
        updated_fields.append("end_offset_days")

    if updated_fields:
        activity.save(update_fields=updated_fields)


class TemplateViewSet(viewsets.ModelViewSet):
    serializer_class = TemplateSerializer
    permission_classes = [permissions.IsAuthenticated, IsTemplateOwnerOrSharedAccess]
    filter_backends = [SearchFilter]
    search_fields = ["template_name", "description"]

    def get_queryset(self):
        queryset = Template.objects.filter(
            accessible_templates_q(self.request.user)
        ).distinct()
        if self.action == "list" and self.request.query_params.get("all_versions") != "true":
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
            activity_map = {}

            for template_activity in template.template_activities.all():
                cycle_activity = CycleActivity.objects.create(
                    cycle=cycle,
                    template_activity=template_activity,
                    activity_name=template_activity.activity_name,
                    calculated_start_date=cycle.start_date + timedelta(days=template_activity.start_offset_days),
                    calculated_end_date=cycle.start_date + timedelta(days=template_activity.end_offset_days),
                    note_text=template_activity.note_text,
                )

                activity_map[template_activity.template_activity_id] = cycle_activity

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
                    cycle_activity=activity_map.get(template_task.template_activity_id),
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
                "template_activity_id": t.template_activity_id,
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

            return Response(
                {
                    "message": "New template version created successfully.",
                    "template": TemplateSerializer(new_template).data,
                },
                status=status.HTTP_200_OK,
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
    def make_current(self, request, pk=None):
        """
        Marks this specific version as the current one for its
        template family, un-marking whichever version was previously
        current. Every version still exists afterward — this only
        changes which one is treated as "current" (e.g. the one used
        when creating a new cycle, and the one shown by default in
        the template library).
        """
        target_version = self.get_object()

        if not user_can_edit_template(request.user, target_version):
            raise PermissionDenied("You do not have permission to modify this template.")

        root_template = target_version.parent_template or target_version

        with transaction.atomic():
            family = Template.objects.filter(
                parent_template=root_template
            ) | Template.objects.filter(template_id=root_template.template_id)

            family.exclude(template_id=target_version.template_id).update(is_current_version=False)

            target_version.is_current_version = True
            target_version.save(update_fields=["is_current_version"])

        return Response(
            TemplateSerializer(target_version).data,
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
        expand_activity_to_include_task(task)

    def perform_update(self, serializer):
        template = serializer.validated_data.get("template", serializer.instance.template)
        if not user_can_edit_template(self.request.user, template):
            raise PermissionDenied("You do not have permission to modify this template.")

        with transaction.atomic():
            task = serializer.save()

            try:
                revalidate_task_offsets(task)
            except DependencyConflict as exc:
                raise ValidationError({"day_offset": [exc.message]})

            expand_activity_to_include_task(task)

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

    def perform_destroy(self, instance):
        if not user_can_edit_template(self.request.user, instance.template):
            raise PermissionDenied("You do not have permission to modify this template.")

        instance.template_tasks.all().delete()
        instance.delete()

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
