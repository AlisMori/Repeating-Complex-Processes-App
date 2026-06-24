from rest_framework import permissions, viewsets
from rest_framework.filters import SearchFilter

from .models import TaskDependency
from .serializers import TaskDependencySerializer


class TaskDependencyViewSet(viewsets.ModelViewSet):
    serializer_class = TaskDependencySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = [
        "task__task_name",
        "depends_on_task__task_name",
    ]

    def get_queryset(self):
        # Users can manage dependencies only for their own templates or public templates.
        return TaskDependency.objects.filter(
            task__template__user=self.request.user
        ) | TaskDependency.objects.filter(
            task__template__is_public=True
        )