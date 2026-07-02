from django.core.management.base import BaseCommand
from django_q.models import Schedule


class Command(BaseCommand):
    # Registers the overdue-check job with django-q2's own scheduler, so
    # it runs automatically once a qcluster worker is running (see
    # cycles/SCHEDULER_SETUP.md). Safe to run more than once, it updates
    # the existing row instead of duplicating it, run this again any time
    # the schedule itself needs to change.
    help = "Registers cycles.task_status_engine.mark_overdue_tasks to run daily via django-q2."

    def handle(self, *args, **options):
        schedule, created = Schedule.objects.update_or_create(
            func="cycles.task_status_engine.mark_overdue_tasks",
            defaults={
                "name": "mark_overdue_tasks",
                "schedule_type": Schedule.DAILY,
                "repeats": -1,
            },
        )
        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} schedule '{schedule.name}' (id={schedule.id})."))