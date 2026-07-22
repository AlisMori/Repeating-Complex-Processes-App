from django.core.management.base import BaseCommand

from notifications.scheduler import register_scheduler


class Command(BaseCommand):
    help = "Registers notifications.tasks.check_notifications to run every 5 minutes via django-q2."

    def handle(self, *args, **options):
        schedule, created = register_scheduler()
        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} schedule '{schedule.name}' (id={schedule.id})."))
