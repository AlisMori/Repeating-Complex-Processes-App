from django.core.management.base import BaseCommand

from cycles.task_status_engine import mark_overdue_tasks


class Command(BaseCommand):
    # Manual trigger for the overdue check on its own, without also
    # running activate_started_tasks. Useful when testing the overdue
    # path in isolation. The scheduled job that actually runs every day
    # calls run_scheduled_maintenance instead, see
    # cycles/management/commands/run_task_maintenance.py and
    # setup_scheduled_jobs.py.
    help = "Flips pending/in_progress tasks past their end date to overdue, running cycles only."

    def handle(self, *args, **options):
        count = mark_overdue_tasks()
        self.stdout.write(self.style.SUCCESS(f"Marked {count} task(s) overdue."))