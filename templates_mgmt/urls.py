from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import TemplateViewSet


router = DefaultRouter()
router.register("templates", TemplateViewSet, basename="templates")

urlpatterns = [
    path("", include(router.urls)),
]