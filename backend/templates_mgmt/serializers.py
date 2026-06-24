from rest_framework import serializers

from .models import (
    Template,
    UserTemplate,
    Tag,
    TemplateTask,
    TemplateActivity,
    TemplateTaskTag,
    TemplateActivityTag,
)


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Template
        fields = "__all__"
        read_only_fields = ["template_id", "user", "created_at"]


class UserTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserTemplate
        fields = "__all__"
        read_only_fields = ["user_template_id", "created_at"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = "__all__"
        read_only_fields = ["tag_id", "user"]


class TemplateTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateTask
        fields = "__all__"
        read_only_fields = ["template_task_id"]


class TemplateActivitySerializer(serializers.ModelSerializer):
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