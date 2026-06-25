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
from cycles.models import CycleActivity, CycleInstance, CycleTask
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
    def share(self, request, pk=None):
        template = self.get_object()
        if not user_can_edit_template(request.user, template):
            raise PermissionDenied("You do not have permission to share this template.")

        target_user_id = request.data.get("user_id")
        if not target_user_id:
            return Response(
                {"user_id": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            target_user = User.objects.get(pk=target_user_id)
        except User.DoesNotExist:
            return Response(
                {"user_id": ["User not found."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        relation, _ = UserTemplate.objects.update_or_create(
            user=target_user,
            template=template,
            defaults={"access_type": "shared"},
        )
        return Response(
            {
                "message": "Template shared successfully.",
                "user_template_id": relation.user_template_id,
            },
            status=status.HTTP_200_OK,
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

        return Response(
            {
                "message": "Template duplicated successfully.",
                "template": TemplateSerializer(copied_template).data,
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
        serializer.save()


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
