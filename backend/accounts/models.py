import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    # Stores whether the user wants to receive notifications.
    # This field is needed for notification settings and future reminder logic.
    notification_opt_in = models.BooleanField(default=True)

    # Stores when the user record was created.
    # Django already has date_joined, but this field matches our ERD naming.
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username


class AuthSession(models.Model):
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="auth_sessions",
    )
    current_refresh_jti = models.CharField(max_length=255, unique=True)
    last_activity_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}:{self.session_id}"


class ShareNotification(models.Model):
    notification_id = models.AutoField(primary_key=True)
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="share_notifications",
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_share_notifications",
    )
    template = models.ForeignKey(
        "templates_mgmt.Template",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="share_notifications",
    )
    template_name = models.CharField(max_length=100)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.sender.username} -> {self.recipient.username}: {self.template_name}"
