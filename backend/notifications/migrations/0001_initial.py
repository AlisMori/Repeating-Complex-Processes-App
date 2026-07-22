from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("cycles", "0006_alter_template_fks_set_null"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationDelivery",
            fields=[
                ("delivery_id", models.BigAutoField(primary_key=True, serialize=False)),
                ("notification_kind", models.CharField(choices=[("reminder", "Reminder"), ("overdue", "Overdue")], max_length=20)),
                ("notification_key", models.CharField(max_length=100)),
                ("scheduled_for", models.DateField()),
                ("reminder_lead_days", models.PositiveIntegerField(blank=True, null=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed")], default="pending", max_length=20)),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("final_failure_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("task", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notification_deliveries", to="cycles.cycletask")),
            ],
            options={
                "ordering": ["task_id", "scheduled_for", "delivery_id"],
            },
        ),
        migrations.AddConstraint(
            model_name="notificationdelivery",
            constraint=models.UniqueConstraint(fields=("task", "notification_key"), name="unique_task_notification_delivery"),
        ),
    ]
