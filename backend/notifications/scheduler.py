from django_q.models import Schedule


def register_scheduler():
    existing_schedule = Schedule.objects.filter(
        func="notifications.tasks.check_notifications"
    ).order_by("pk").first()

    if existing_schedule is not None:
        return existing_schedule

    return Schedule.objects.create(
        func="notifications.tasks.check_notifications",
        schedule_type=Schedule.DAILY,
        repeats=-1,
    )
