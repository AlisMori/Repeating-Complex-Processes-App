# templates_mgmt/migrations/0003_alter_templateactivity_options_and_more.py

import django.contrib.postgres.fields
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
        migrations.RunSQL(
            sql="""
                ALTER TABLE templates_mgmt_templatetask
                DROP CONSTRAINT IF EXISTS templates_mgmt_templatetask_reminder_lead_days_check;
                ALTER TABLE templates_mgmt_templatetask
                ALTER COLUMN reminder_lead_days TYPE integer[]
                USING (CASE WHEN reminder_lead_days IS NULL THEN NULL ELSE ARRAY[reminder_lead_days] END);
            """,
            reverse_sql="""
                ALTER TABLE templates_mgmt_templatetask
                ALTER COLUMN reminder_lead_days TYPE integer
                USING (reminder_lead_days[1]);
                ALTER TABLE templates_mgmt_templatetask
                ADD CONSTRAINT templates_mgmt_templatetask_reminder_lead_days_check CHECK (reminder_lead_days >= 0);
            """,
            state_operations=[
                migrations.AlterField(
                    model_name='templatetask',
                    name='reminder_lead_days',
                    field=django.contrib.postgres.fields.ArrayField(base_field=models.PositiveIntegerField(), blank=True, help_text="Lead times in days before the task is due (e.g. [7, 3, 0]). Multiple simultaneous reminders are supported per the client's requirement that 'chains of reminders are valid'.", null=True),
                ),
            ],
        ),
    ]