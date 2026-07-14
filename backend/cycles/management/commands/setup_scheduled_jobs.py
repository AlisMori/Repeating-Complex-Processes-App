from django.core.management.base import BaseCommand
from django_q.models import Schedule


class Command(BaseCommand):
    # Registers the daily maintenance job with django-q2's own
    # scheduler, so it runs automatically once a qcluster worker is
    # running (see cycles/SCHEDULER_SETUP.md). Safe to run more than
    # once, it updates the existing row instead of duplicating it, run
    # this again any time the schedule itself needs to change.
    #
    # One scheduled function, run_scheduled_maintenance, covers both
    # checks the job needs to make each day: activating tasks whose
    # start date has arrived, then flagging anything now overdue.
    help = "Registers cycles.task_status_engine.run_scheduled_maintenance to run daily via django-q2."

    def handle(self, *args, **options):
        schedule, created = Schedule.objects.update_or_create(
            func="cycles.task_status_engine.run_scheduled_maintenance",
            defaults={
                "name": "run_scheduled_maintenance",
                "schedule_type": Schedule.DAILY,
                "repeats": -1,
            },
        )
        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} schedule '{schedule.name}' (id={schedule.id})."))