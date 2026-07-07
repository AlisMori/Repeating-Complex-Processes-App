from django.core.management.base import BaseCommand

from cycles.task_status_engine import mark_overdue_tasks


class Command(BaseCommand):
    # NFR-6-adjacent: this is the first management command in the project,
    # nothing registers it against django-q2's scheduler yet (Q_CLUSTER
    # isn't configured anywhere either). Runnable by hand for now:
    #   python manage.py mark_overdue_tasks
    # Wiring an actual Schedule row for django-q2, or a cron/Task
    # Scheduler entry, is a deployment decision, not a code one.
    help = "Flips pending/in_progress tasks past their end date to overdue, running cycles only."

    def handle(self, *args, **options):
        count = mark_overdue_tasks()
        self.stdout.write(self.style.SUCCESS(f"Marked {count} task(s) overdue."))