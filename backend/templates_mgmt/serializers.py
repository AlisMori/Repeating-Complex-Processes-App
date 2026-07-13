from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from core.permissions import user_can_edit_template
from .models import (
    Template,
    TemplateCategory,
    UserTemplate,
    Tag,
    TemplateTask,
    TemplateActivity,
    TemplateTaskTag,
    TemplateActivityTag,
)


class TemplateCategorySerializer(serializers.ModelSerializer):
    template_count = serializers.SerializerMethodField()

    def get_template_count(self, obj):
        return obj.templates.count()

    def validate_category_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Category name cannot be empty.")
        request = self.context.get("request")
        if request is not None:
            existing = TemplateCategory.objects.filter(
                user=request.user, category_name__iexact=value
            )
            if self.instance is not None:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError("You already have a category with this name.")
        return value

    class Meta:
        model = TemplateCategory
        fields = "__all__"
        read_only_fields = ["category_id", "user"]


class TemplateSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.category_name", read_only=True, default=None)

    def validate_category(self, value):
        request = self.context.get("request")
        if value is not None and request is not None and value.user_id != request.user.id:
            raise PermissionDenied("You do not have permission to use this category.")
        return value

    class Meta:
        model = Template
        fields = "__all__"
        read_only_fields = ["template_id", "user", "created_at", "created_by_type"]


class UserTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserTemplate
        fields = "__all__"
        read_only_fields = ["user_template_id", "user", "template", "created_at"]


class TagSerializer(serializers.ModelSerializer):
    def validate_tag_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Tag name cannot be empty.")
        request = self.context.get("request")
        if request is not None:
            existing = Tag.objects.filter(user=request.user, tag_name__iexact=value)
            if self.instance is not None:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError("You already have a tag with this name.")
        return value

    class Meta:
        model = Tag
        fields = "__all__"
        read_only_fields = ["tag_id", "user"]


class TemplateTaskSerializer(serializers.ModelSerializer):
    def validate_template(self, value):
        request = self.context.get("request")
        if request is None or not user_can_edit_template(request.user, value):
            raise PermissionDenied(
                "You do not have permission to attach a task to this template."
            )
        return value

    def validate(self, attrs):
        template = attrs.get("template") or getattr(self.instance, "template", None)
        template_activity = attrs.get("template_activity") or getattr(
            self.instance,
            "template_activity",
            None,
        )

        if template and template_activity and template_activity.template_id != template.template_id:
            raise serializers.ValidationError(
                {
                    "template_activity": [
                        "The selected activity must belong to the same template as the task."
                    ]
                }
            )

        task_start = attrs.get("day_offset", getattr(self.instance, "day_offset", None))
        duration = attrs.get("duration_days", getattr(self.instance, "duration_days", None))
        task_end = task_start + (duration or 0) if task_start is not None else None

        if (
                self.instance is None
                and template_activity
                and task_start is not None
                and task_end is not None
        ):
            if (
                    task_start < template_activity.start_offset_days
                    or task_end > template_activity.end_offset_days
            ):
                raise serializers.ValidationError(
                    {
                        "template_activity": [
                            "Task dates must stay within the selected activity date range."
                        ]
                    }
                )

        return attrs

    class Meta:
        model = TemplateTask
        fields = "__all__"
        read_only_fields = ["template_task_id"]


class TemplateActivitySerializer(serializers.ModelSerializer):
    def validate_template(self, value):
        request = self.context.get("request")
        if request is None or not user_can_edit_template(request.user, value):
            raise PermissionDenied(
                "You do not have permission to attach an activity to this template."
            )
        return value

    class Meta:
        model = TemplateActivity
        fields = "__all__"
        read_only_fields = ["template_activity_id"]


class TemplateTaskTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateTaskTag
        fields = "__all__"
        read_only_fields = ["template_task_tag_id"]


class TemplateActivityTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateActivityTag
        fields = "__all__"
        read_only_fields = ["template_activity_tag_id"]