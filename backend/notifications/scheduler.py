from django.db import transaction
from django_q.models import Schedule


def register_scheduler():
    with transaction.atomic():
        schedules = list(
            Schedule.objects.select_for_update()
            .filter(func="notifications.tasks.check_notifications")
            .order_by("id")
        )
        created = not schedules

        if schedules:
            schedule = schedules[0]
            duplicate_ids = [item.id for item in schedules[1:]]
            if duplicate_ids:
                Schedule.objects.filter(id__in=duplicate_ids).delete()
        else:
            schedule = Schedule(func="notifications.tasks.check_notifications")

        schedule.name = "check_notifications"
        schedule.schedule_type = Schedule.MINUTES
        schedule.minutes = 5
        schedule.repeats = -1
        schedule.save()
        return schedule, created


def register_scheduler_on_migrate(sender, apps, **kwargs):
    register_scheduler()
