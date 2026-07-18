from django_q.models import Schedule


def register_scheduler():
    return Schedule.objects.update_or_create(
        func="notifications.tasks.check_notifications",
        defaults={
            "name": "check_notifications",
            "schedule_type": Schedule.DAILY,
            "repeats": -1,
        },
    )


def register_scheduler_on_migrate(sender, apps, **kwargs):
    register_scheduler()
