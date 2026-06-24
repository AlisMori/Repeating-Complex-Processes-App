from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import TaskDependencyViewSet


router = DefaultRouter()
router.register("task-dependencies", TaskDependencyViewSet, basename="task-dependencies")

urlpatterns = [
    path("", include(router.urls)),
]