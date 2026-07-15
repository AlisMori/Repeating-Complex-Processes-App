from django.conf import settings
from django.core.mail import send_mail


def send_reminder_email(user, task):
    print("Calling send_mail()")
    subject = f"Reminder: {task.task_name}"

    message = (
        f"Your task '{task.task_name}' "
        f"starts on {task.calculated_start_date}."
    )

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def send_overdue_email(user, task):

    subject = f"Task overdue: {task.task_name}"

    message = (
        f"Your task '{task.task_name}' "
        f"was due on {task.calculated_end_date}."
    )

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )