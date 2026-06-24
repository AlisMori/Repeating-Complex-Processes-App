from rest_framework import permissions, viewsets
from rest_framework.filters import SearchFilter
from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

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


class TemplateViewSet(viewsets.ModelViewSet):
    serializer_class = TemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ["template_name", "description"]

    def get_queryset(self):
        # Users can see their own templates and public templates.
        return Template.objects.filter(user=self.request.user) | Template.objects.filter(is_public=True)

    def perform_create(self, serializer):
        # The logged-in user automatically becomes the creator of the template.
        serializer.save(user=self.request.user, created_by_type="user"
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

        return Response(
            {
                "message": "Template duplicated successfully.",
                "template": TemplateSerializer(copied_template).data,
            },
            status=status.HTTP_201_CREATED,
        )

class TemplateTaskViewSet(viewsets.ModelViewSet):
    serializer_class = TemplateTaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ["task_name", "description", "note_text"]

    def get_queryset(self):
        # Users can only manage tasks that belong to their own templates or public templates.
        return TemplateTask.objects.filter(
            template__user=self.request.user
        ) | TemplateTask.objects.filter(
            template__is_public=True
        )


class TemplateActivityViewSet(viewsets.ModelViewSet):
    serializer_class = TemplateActivitySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ["activity_name", "description", "note_text"]

    def get_queryset(self):
        # Users can only manage activities that belong to their own templates or public templates.
        return TemplateActivity.objects.filter(
            template__user=self.request.user
        ) | TemplateActivity.objects.filter(
            template__is_public=True
        )


class TagViewSet(viewsets.ModelViewSet):
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ["tag_name"]

    def get_queryset(self):
        # Users only see their own tags.
        return Tag.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # The logged-in user automatically becomes the owner of the tag.
        serializer.save(user=self.request.user)