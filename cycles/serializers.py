from rest_framework import serializers

from .models import TaskDependency


class TaskDependencySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskDependency
        fields = "__all__"
        read_only_fields = ["dependency_id"]