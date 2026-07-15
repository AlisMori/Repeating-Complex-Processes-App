from django_q.models import Schedule
from django_q.tasks import schedule


def register_scheduler():

    Schedule.objects.get_or_create(

        func="notifications.tasks.check_notifications",

        defaults={

            "schedule_type": Schedule.MINUTES,

            "repeats": -1,

        }

    )