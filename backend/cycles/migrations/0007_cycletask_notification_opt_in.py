from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cycles", "0006_alter_template_fks_set_null"),
    ]

    operations = [
        migrations.AddField(
            model_name="cycletask",
            name="notification_opt_in",
            field=models.BooleanField(default=True),
        ),
    ]
