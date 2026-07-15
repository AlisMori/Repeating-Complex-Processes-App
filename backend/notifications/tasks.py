from datetime import timedelta

from django.utils import timezone

from accounts.models import User
from cycles.models import CycleInstance, CycleTask

from .services import (
    send_reminder_email,
    send_overdue_email,
)


def check_notifications():
    today = timezone.now().date()

    # Users who want to receive notifications would get them
    users = User.objects.filter(
        notification_opt_in=True
    )

    # Check against every user who wants notifications
    for user in users:

        # Check user's running cycle instances only
        cycles = CycleInstance.objects.filter(
            user=user,
            status="running"
        )

        # Each cycle instance's tasks need to be checked
        for cycle in cycles:

            # Take all tasks of a cycle instance
            tasks = CycleTask.objects.filter(
                cycle=cycle
            )

            # Check whether a task requires a reminder before task's start or whether a task is overdue
            for task in tasks:

                check_reminder(
                    user,
                    task,
                    today
                )

                check_overdue(
                    user,
                    task,
                    today
                )


def check_reminder(user, task, today):
    # Ensure reminders are set and present
    if not task.reminder_lead_days:
        return

    # Check against all set reminders
    for days_before in task.reminder_lead_days:
        # Check whether reminder date is today

        reminder_date = (
            task.calculated_start_date
            - timedelta(days=days_before)
        )

        # Check reminder date
        if reminder_date != today:
            continue

        # If program reaches here, reminder email is sent to user
        try:

            send_reminder_email(user, task)

            # TODO:
            # Log successful reminder notification


        except Exception as e:

            # TODO:
            # Log failed reminder notification
            print(e)


def check_overdue(user, task, today):
    # Don't notify about tasks that are completed
    if task.status == "completed":
        return

    # Don't notify about tasks that are not yet overdue
    if task.calculated_end_date >= today:
        return

    try:

        send_overdue_email(user, task)


        # Log successful overdue notification

    except Exception as e:


        # Log failed overdue notification
        print(e)