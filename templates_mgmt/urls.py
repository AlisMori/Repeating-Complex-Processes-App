from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    TemplateViewSet,
    TemplateTaskViewSet,
    TemplateActivityViewSet,
    TagViewSet,
)


router = DefaultRouter()
router.register("templates", TemplateViewSet, basename="templates")
router.register("template-tasks", TemplateTaskViewSet, basename="template-tasks")
router.register("template-activities", TemplateActivityViewSet, basename="template-activities")
router.register("tags", TagViewSet, basename="tags")

urlpatterns = [
    path("", include(router.urls)),
]