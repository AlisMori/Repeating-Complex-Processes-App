# cycles/migrations/0002_alter_cycletask_reminder_lead_days.py

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cycles', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE cycles_cycletask
                DROP CONSTRAINT IF EXISTS cycles_cycletask_reminder_lead_days_check;
                ALTER TABLE cycles_cycletask
                ALTER COLUMN reminder_lead_days TYPE integer[]
                USING (CASE WHEN reminder_lead_days IS NULL THEN NULL ELSE ARRAY[reminder_lead_days] END);
            """,
            reverse_sql="""
                ALTER TABLE cycles_cycletask
                ALTER COLUMN reminder_lead_days TYPE integer
                USING (reminder_lead_days[1]);
                ALTER TABLE cycles_cycletask
                ADD CONSTRAINT cycles_cycletask_reminder_lead_days_check CHECK (reminder_lead_days >= 0);
            """,
            state_operations=[
                migrations.AlterField(
                    model_name='cycletask',
                    name='reminder_lead_days',
                    field=django.contrib.postgres.fields.ArrayField(base_field=models.PositiveIntegerField(), blank=True, null=True),
                ),
            ],
        ),
    ]