from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CycleActivityViewSet,
    CycleInstanceViewSet,
    CycleTaskViewSet,
    TaskDependencyViewSet,
)


router = DefaultRouter()
router.register("cycles", CycleInstanceViewSet, basename="cycles")
router.register("cycle-tasks", CycleTaskViewSet, basename="cycle-tasks")
router.register("cycle-activities", CycleActivityViewSet, basename="cycle-activities")
router.register("task-dependencies", TaskDependencyViewSet, basename="task-dependencies")

urlpatterns = [
    path("", include(router.urls)),
]
