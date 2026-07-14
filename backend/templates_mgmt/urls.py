from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    TemplateViewSet,
    TemplateCategoryViewSet,
    TemplateTaskViewSet,
    TemplateActivityViewSet,
    TagViewSet,
    TemplateTaskTagViewSet,
    TemplateActivityTagViewSet,
)


router = DefaultRouter()
router.register("templates", TemplateViewSet, basename="templates")
router.register("template-categories", TemplateCategoryViewSet, basename="template-categories")
router.register("template-tasks", TemplateTaskViewSet, basename="template-tasks")
router.register("template-activities", TemplateActivityViewSet, basename="template-activities")
router.register("tags", TagViewSet, basename="tags")
router.register(
    "template-task-tags",
    TemplateTaskTagViewSet,
    basename="template-task-tags",
)



router.register(
    "template-activity-tags",
    TemplateActivityTagViewSet,
    basename="template-activity-tags",
)

urlpatterns = [
    path("", include(router.urls)),
]