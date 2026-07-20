from django.db import models


class NotificationDelivery(models.Model):
    KIND_REMINDER = "reminder"
    KIND_OVERDUE = "overdue"
    KIND_CHOICES = [
        (KIND_REMINDER, "Reminder"),
        (KIND_OVERDUE, "Overdue"),
    ]

    STATUS_PENDING = "pending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
    ]

    delivery_id = models.BigAutoField(primary_key=True)
    task = models.ForeignKey(
        "cycles.CycleTask",
        on_delete=models.CASCADE,
        related_name="notification_deliveries",
    )
    notification_kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    notification_key = models.CharField(max_length=100)
    scheduled_for = models.DateField()
    reminder_lead_days = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    attempt_count = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    final_failure_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["task", "notification_key"],
                name="unique_task_notification_delivery",
            )
        ]
        ordering = ["task_id", "scheduled_for", "delivery_id"]

    def __str__(self):
        return f"{self.task_id}:{self.notification_key}:{self.status}"
