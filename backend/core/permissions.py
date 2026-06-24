from django.db.models import Q
from rest_framework.permissions import SAFE_METHODS, BasePermission

from cycles.models import CycleActivity, CycleInstance, CycleTask, TaskDependency
from templates_mgmt.models import Template, TemplateActivity, TemplateTask, UserTemplate


TEMPLATE_SHARED_ACCESS_TYPES = ("owner", "saved", "shared")
TEMPLATE_OWNER_ACCESS_TYPE = "owner"


def accessible_templates_q(user):
    if not user or not user.is_authenticated:
        return Q(pk__in=[])

    return (
        Q(user=user)
        | Q(is_public=True)
        | Q(usertemplate__user=user, usertemplate__access_type__in=TEMPLATE_SHARED_ACCESS_TYPES)
    )


def editable_templates_q(user):
    if not user or not user.is_authenticated:
        return Q(pk__in=[])

    return (
        Q(user=user)
        | Q(usertemplate__user=user, usertemplate__access_type=TEMPLATE_OWNER_ACCESS_TYPE)
    )


def owned_cycles_q(user):
    if not user or not user.is_authenticated:
        return Q(pk__in=[])

    return Q(user=user)


def user_can_access_template(user, template):
    if not user or not user.is_authenticated:
        return False

    if template.user_id == user.id or template.is_public:
        return True

    return UserTemplate.objects.filter(
        user=user,
        template=template,
        access_type__in=TEMPLATE_SHARED_ACCESS_TYPES,
    ).exists()


def user_can_edit_template(user, template):
    if not user or not user.is_authenticated:
        return False

    if template.user_id == user.id:
        return True

    return UserTemplate.objects.filter(
        user=user,
        template=template,
        access_type=TEMPLATE_OWNER_ACCESS_TYPE,
    ).exists()


def user_can_access_cycle(user, cycle):
    return bool(
        user
        and user.is_authenticated
        and cycle is not None
        and cycle.user_id == user.id
    )


def _resolve_template(obj):
    if isinstance(obj, Template):
        return obj
    if isinstance(obj, (TemplateTask, TemplateActivity)):
        return obj.template
    if isinstance(obj, TaskDependency):
        return obj.task.template

    template = getattr(obj, "template", None)
    if template is not None:
        return template

    task = getattr(obj, "task", None)
    if task is not None and hasattr(task, "template"):
        return task.template

    template_task = getattr(obj, "template_task", None)
    if template_task is not None and hasattr(template_task, "template"):
        return template_task.template

    template_activity = getattr(obj, "template_activity", None)
    if template_activity is not None and hasattr(template_activity, "template"):
        return template_activity.template

    return None


def _resolve_cycle(obj):
    if isinstance(obj, CycleInstance):
        return obj
    if isinstance(obj, (CycleTask, CycleActivity)):
        return obj.cycle

    cycle = getattr(obj, "cycle", None)
    if cycle is not None:
        return cycle

    return None


class IsOwner(BasePermission):
    message = "You do not have permission to access this object."

    def has_object_permission(self, request, view, obj):
        return getattr(obj, "user_id", None) == request.user.id


class IsTemplateOwnerOrSharedAccess(BasePermission):
    message = "You do not have permission to access this template resource."

    def has_object_permission(self, request, view, obj):
        template = _resolve_template(obj)
        if template is None:
            return False

        if request.method in SAFE_METHODS:
            return user_can_access_template(request.user, template)

        return user_can_edit_template(request.user, template)


class IsCycleOwner(BasePermission):
    message = "You do not have permission to access this cycle."

    def has_object_permission(self, request, view, obj):
        cycle = _resolve_cycle(obj)
        return user_can_access_cycle(request.user, cycle)


class IsParentCycleOwner(BasePermission):
    message = "You do not have permission to access this cycle resource."

    def has_object_permission(self, request, view, obj):
        cycle = _resolve_cycle(obj)
        return user_can_access_cycle(request.user, cycle)
