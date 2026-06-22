from django.conf import settings
from django.db import models


# This model stores reusable process templates.
# Template is the main blueprint that later can be used to create cycle instances.
class Template(models.Model):
    template_id = models.AutoField(primary_key=True)

    # user can be null because some templates may be system-created, not user-created
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="templates"
    )

    template_version = models.PositiveIntegerField(default=1)
    template_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_public = models.BooleanField(default=False)
    created_by_type = models.CharField(max_length=20, default="user")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.template_name


# This association model connects users and templates.
# It supports access types such as owner, saved, or shared.
class UserTemplate(models.Model):
    ACCESS_TYPE_CHOICES = [
        ("owner", "Owner"),
        ("saved", "Saved"),
        ("shared", "Shared"),
    ]

    user_template_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    template = models.ForeignKey(Template, on_delete=models.CASCADE)
    access_type = models.CharField(max_length=20, choices=ACCESS_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.template} ({self.access_type})"


# Tags are used to categorise template tasks and activities.
class Tag(models.Model):
    tag_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    tag_name = models.CharField(max_length=50)

    def __str__(self):
        return self.tag_name


# TemplateTask stores reusable actionable tasks inside a template.
class TemplateTask(models.Model):
    template_task_id = models.AutoField(primary_key=True)
    template = models.ForeignKey(
        Template,
        on_delete=models.CASCADE,
        related_name="template_tasks"
    )

    task_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    day_offset = models.PositiveIntegerField()
    duration_days = models.PositiveIntegerField(blank=True, null=True)
    is_mandatory = models.BooleanField(default=True)
    is_fixed_date = models.BooleanField(default=False)
    reminder_lead_days = models.PositiveIntegerField(blank=True, null=True)
    note_text = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.task_name


# TemplateActivity stores non-actionable timeline activities inside a template.
class TemplateActivity(models.Model):
    template_activity_id = models.AutoField(primary_key=True)
    template = models.ForeignKey(
        Template,
        on_delete=models.CASCADE,
        related_name="template_activities"
    )

    activity_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    start_offset_days = models.PositiveIntegerField()
    end_offset_days = models.PositiveIntegerField()
    note_text = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.activity_name


# This association model allows one task to have multiple tags.
class TemplateTaskTag(models.Model):
    template_task_tag_id = models.AutoField(primary_key=True)
    template_task = models.ForeignKey(TemplateTask, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.template_task} - {self.tag}"


# This association model allows one activity to have multiple tags.
class TemplateActivityTag(models.Model):
    template_activity_tag_id = models.AutoField(primary_key=True)
    template_activity = models.ForeignKey(TemplateActivity, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.template_activity} - {self.tag}"