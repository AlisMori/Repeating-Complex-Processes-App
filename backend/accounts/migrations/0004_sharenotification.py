from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("templates_mgmt", "0008_templatecategory_tag_unique_user_tag_name_and_more"),
        ("accounts", "0003_authsession"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShareNotification",
            fields=[
                ("notification_id", models.AutoField(primary_key=True, serialize=False)),
                ("template_name", models.CharField(max_length=100)),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="share_notifications",
                        to="accounts.user",
                    ),
                ),
                (
                    "sender",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sent_share_notifications",
                        to="accounts.user",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="share_notifications",
                        to="templates_mgmt.template",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
