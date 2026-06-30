from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from core.permissions import user_can_access_cycle, user_can_access_template
from .models import CycleActivity, CycleInstance, CycleTask, TaskDependency


class CycleInstanceSerializer(serializers.ModelSerializer):
    def validate_template(self, value):
        request = self.context.get("request")
        if request is None or not user_can_access_template(request.user, value):
            raise PermissionDenied(
                "You do not have permission to create a cycle from this template."
            )
        return value

    class Meta:
        model = CycleInstance
        fields = "__all__"
        read_only_fields = ["cycle_id", "user", "status", "created_at"]


class CycleTaskSerializer(serializers.ModelSerializer):
    def validate_cycle(self, value):
        request = self.context.get("request")
        if request is None or not user_can_access_cycle(request.user, value):
            raise PermissionDenied(
                "You do not have permission to attach a task to this cycle."
            )
        return value

    def validate_template_task(self, value):
        request = self.context.get("request")
        if request is None or not user_can_access_template(request.user, value.template):
            raise PermissionDenied(
                "You do not have permission to use this template task."
            )
        return value

    def validate(self, attrs):
        cycle = attrs.get("cycle") or getattr(self.instance, "cycle", None)
        template_task = attrs.get("template_task") or getattr(self.instance, "template_task", None)
        if cycle and template_task and cycle.template_id != template_task.template_id:
            raise serializers.ValidationError(
                {"template_task": ["The template task must belong to the cycle template."]}
            )
        return attrs

    class Meta:
        model = CycleTask
        fields = "__all__"
        read_only_fields = ["cycle_task_id"]


class CycleActivitySerializer(serializers.ModelSerializer):
    def validate_cycle(self, value):
        request = self.context.get("request")
        if request is None or not user_can_access_cycle(request.user, value):
            raise PermissionDenied(
                "You do not have permission to attach an activity to this cycle."
            )
        return value

    def validate_template_activity(self, value):
        request = self.context.get("request")
        if request is None or not user_can_access_template(request.user, value.template):
            raise PermissionDenied(
                "You do not have permission to use this template activity."
            )
        return value

    def validate(self, attrs):
        cycle = attrs.get("cycle") or getattr(self.instance, "cycle", None)
        template_activity = attrs.get("template_activity") or getattr(
            self.instance,
            "template_activity",
            None,
        )
        if cycle and template_activity and cycle.template_id != template_activity.template_id:
            raise serializers.ValidationError(
                {
                    "template_activity": [
                        "The template activity must belong to the cycle template."
                    ]
                }
            )
        return attrs

    class Meta:
        model = CycleActivity
        fields = "__all__"
        read_only_fields = ["cycle_activity_id"]


class TaskDependencySerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        task = attrs.get("task") or getattr(self.instance, "task", None)
        depends_on_task = attrs.get("depends_on_task") or getattr(
            self.instance,
            "depends_on_task",
            None,
        )
        request = self.context.get("request")

        if task is None or depends_on_task is None:
            return attrs

        if task.template_id != depends_on_task.template_id:
            raise serializers.ValidationError(
                {"depends_on_task": ["Task dependencies must stay within the same template."]}
            )

        if request is None or not user_can_access_template(request.user, task.template):
            raise PermissionDenied(
                "You do not have permission to modify this template dependency."
            )

        return attrs

    class Meta:
        model = TaskDependency
        fields = "__all__"
        read_only_fields = ["dependency_id"]
