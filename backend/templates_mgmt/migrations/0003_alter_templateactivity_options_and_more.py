# templates_mgmt/migrations/0003_alter_templateactivity_options_and_more.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('templates_mgmt', '0002_template_is_current_version_template_parent_template'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='templateactivity',
            options={'ordering': ['template_activity_id']},
        ),
        migrations.AlterModelOptions(
            name='templatetask',
            options={'ordering': ['template_task_id']},
        ),
    ]