from rest_framework import permissions, viewsets
from rest_framework.filters import SearchFilter
from rest_framework.exceptions import PermissionDenied

from core.permissions import (
    IsTemplateOwnerOrSharedAccess,
    accessible_templates_q,
    user_can_edit_template,
)
from templates_mgmt.models import Template
from .models import TaskDependency
from .serializers import TaskDependencySerializer


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
            raise PermissionDenied("Task dependencies must stay within the same template.")

        if not user_can_edit_template(self.request.user, task.template):
            raise PermissionDenied("You do not have permission to modify this template.")
