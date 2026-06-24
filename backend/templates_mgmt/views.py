from rest_framework import permissions, viewsets
from rest_framework.filters import SearchFilter

from .models import Template, TemplateTask, TemplateActivity, Tag
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
        serializer.save(user=self.request.user, created_by_type="user")


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