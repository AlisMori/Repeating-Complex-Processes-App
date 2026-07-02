from django.conf import settings
from django.db import models

from templates_mgmt.models import Template, TemplateTask, TemplateActivity


class CycleInstance(models.Model):
    STATUS_CHOICES = [
        ("running", "Running"),
        ("completed", "Completed"),
        ("shut_down", "Shut Down"),
    ]

    cycle_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cycle_instances"
    )
    template = models.ForeignKey(
        Template,
        on_delete=models.CASCADE,
        related_name="cycle_instances"
    )
    cycle_name = models.CharField(max_length=100)
    start_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="running")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.cycle_name


class CycleTask(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("overdue", "Overdue"),
        ("skipped", "Skipped"),
    ]

    cycle_task_id = models.AutoField(primary_key=True)
    cycle = models.ForeignKey(
        CycleInstance,
        on_delete=models.CASCADE,
        related_name="cycle_tasks"
    )
    template_task = models.ForeignKey(
        TemplateTask,
        on_delete=models.CASCADE,
        related_name="cycle_tasks"
    )
    task_name = models.CharField(max_length=100)
    calculated_start_date = models.DateField()
    calculated_end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    is_mandatory = models.BooleanField(default=True)
    is_fixed_date = models.BooleanField(default=False)
    reminder_lead_days = models.PositiveIntegerField(blank=True, null=True)
    note_text = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.task_name


class CycleActivity(models.Model):
    cycle_activity_id = models.AutoField(primary_key=True)
    cycle = models.ForeignKey(
        CycleInstance,
        on_delete=models.CASCADE,
        related_name="cycle_activities"
    )
    template_activity = models.ForeignKey(
        TemplateActivity,
        on_delete=models.CASCADE,
        related_name="cycle_activities"
    )
    activity_name = models.CharField(max_length=100)
    calculated_start_date = models.DateField()
    calculated_end_date = models.DateField()
    note_text = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.activity_name


class TaskDependency(models.Model):
    dependency_id = models.AutoField(primary_key=True)
    task = models.ForeignKey(
        TemplateTask,
        on_delete=models.CASCADE,
        related_name="dependencies"
    )
    depends_on_task = models.ForeignKey(
        TemplateTask,
        on_delete=models.CASCADE,
        related_name="dependent_tasks"
    )
    dependency_depth = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.task} depends on {self.depends_on_task}"