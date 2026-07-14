from django.core.management.base import BaseCommand

from cycles.task_status_engine import run_scheduled_maintenance


class Command(BaseCommand):
    # Manual trigger for the same function the scheduled job runs every
    # day, activate_started_tasks followed by mark_overdue_tasks, in
    # that order. See cycles/SCHEDULER_SETUP.md for the qcluster side
    # of this, this command is only for running it by hand.
    help = "Activates tasks whose start date has arrived, then flags anything overdue."

    def handle(self, *args, **options):
        result = run_scheduled_maintenance()
        self.stdout.write(
            self.style.SUCCESS(
                f"Activated {result['activated']} task(s), marked {result['overdue']} overdue."
            )
        )