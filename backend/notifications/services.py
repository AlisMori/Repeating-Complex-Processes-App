from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def _send_notification_email(*, user, cycle, task, subject, heading, intro, detail, cta_label):
    cycle_url = f"{settings.FRONTEND_URL}/cycles/{cycle.cycle_id}"
    context = {
        "heading": heading,
        "intro": intro,
        "detail": detail,
        "cycle_name": cycle.cycle_name,
        "task_name": task.task_name,
        "cycle_url": cycle_url,
        "cta_label": cta_label,
    }

    text_body = render_to_string("notifications/notification_email.txt", context)
    html_body = render_to_string("notifications/notification_email.html", context)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_body, "text/html")
    email.send(fail_silently=False)


def send_reminder_email(user, cycle, task):
    _send_notification_email(
        user=user,
        cycle=cycle,
        task=task,
        subject=f"Recurra - Reminder: {task.task_name}",
        heading="Upcoming task reminder",
        intro="A task in one of your Recurra cycles is coming up soon.",
        detail=(
            f"'{task.task_name}' in '{cycle.cycle_name}' starts on "
            f"{task.calculated_start_date}."
        ),
        cta_label="Open Cycle",
    )


def send_overdue_email(user, cycle, task):
    _send_notification_email(
        user=user,
        cycle=cycle,
        task=task,
        subject=f"Recurra - Task overdue: {task.task_name}",
        heading="Task overdue",
        intro="A task in one of your Recurra cycles has passed its due date.",
        detail=(
            f"'{task.task_name}' in '{cycle.cycle_name}' was due on "
            f"{task.calculated_end_date}."
        ),
        cta_label="Review Task",
    )
