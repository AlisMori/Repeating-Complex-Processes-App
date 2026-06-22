from rest_framework import permissions, viewsets
from rest_framework.filters import SearchFilter

from .models import Template
from .serializers import TemplateSerializer


class TemplateViewSet(viewsets.ModelViewSet):
    serializer_class = TemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ["template_name", "description"]

    def get_queryset(self):
        # Users can see their own templates and public templates
        return Template.objects.filter(user=self.request.user) | Template.objects.filter(is_public=True)

    def perform_create(self, serializer):
        # Automatically attach the logged-in user to a new template
        serializer.save(user=self.request.user, created_by_type="user")