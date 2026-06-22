from django.conf import settings
from django.db import models

from templates_mgmt.models import Template, TemplateTask, TemplateActivity


# CycleInstance represents an active running cycle created from an existing template
class CycleInstance(models.Model):
    STATUS_CHOICES = [
        ("running", "Running"),
        ("completed", "Completed"),
        ("shut_down", "Shut Down"),
    ]

    cycle_id = models.AutoField(primary_key=True)

    # Each cycle belongs to one user
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cycle_instances"
    )

    # Each cycle is created from one existing template
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


# CycleTask is a runtime task generated from a TemplateTask
class CycleTask(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("overdue", "Overdue"),
        ("delayed", "Delayed"),
    ]

    cycle_task_id = models.AutoField(primary_key=True)

    # Runtime task belongs to one cycle instance
    cycle = models.ForeignKey(
        CycleInstance,
        on_delete=models.CASCADE,
        related_name="cycle_tasks"
    )

    # Runtime task keeps a reference to the template task it was generated from
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


# CycleActivity is a runtime activity generated from a TemplateActivity
class CycleActivity(models.Model):
    cycle_activity_id = models.AutoField(primary_key=True)

    # Runtime activity belongs to one cycle instance
    cycle = models.ForeignKey(
        CycleInstance,
        on_delete=models.CASCADE,
        related_name="cycle_activities"
    )

    # Runtime activity keeps a reference to the template activity it was generated from
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


# TaskDependency stores dependency rules between template tasks
# It shows which task depends on another task
class TaskDependency(models.Model):
    dependency_id = models.AutoField(primary_key=True)

    # The task that has a dependency
    task = models.ForeignKey(
        TemplateTask,
        on_delete=models.CASCADE,
        related_name="dependencies"
    )

    # The task that must be completed or considered before the dependent task
    depends_on_task = models.ForeignKey(
        TemplateTask,
        on_delete=models.CASCADE,
        related_name="dependent_tasks"
    )

    dependency_depth = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.task} depends on {self.depends_on_task}"