from datetime import timedelta
import logging

from django.utils import timezone

from accounts.models import User
from cycles.models import CycleInstance, CycleTask

from .services import (
    send_reminder_email,
    send_overdue_email,
)


def check_notifications():
    # Use unified timezone
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
                    cycle,
                    task,
                    today
                )

                check_overdue(
                    user,
                    cycle,
                    task,
                    today
                )


def check_reminder(user, cycle, task, today):
    logger = logging.getLogger("emails")
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
            send_reminder_email(user, cycle, task)

            # Log successful reminder notification
            logger.info(
                f"Reminder sent | User={user.email} | Cycle={cycle.cycle_name} (ID={cycle.cycle_id}) | Task={task.task_name} (ID={task.cycle_task_id})"
            )

        except Exception as e:
            # Log failed reminder notification
            logger.error(
                f"Reminder failed | User={user.email} | "
                f"Cycle={cycle.cycle_name} (ID={cycle.cycle_id}) | Task={task.task_name} (ID={task.cycle_task_id}) | Error={e}"
            )


def check_overdue(user, cycle, task, today):
    logger = logging.getLogger("emails")
    # Don't notify about tasks that are completed
    if task.status == "completed":
        return

    # Don't notify about tasks that are not yet overdue
    if task.calculated_end_date >= today:
        return

    try:
        send_overdue_email(user,cycle, task)

        # Log successful overdue notification
        logger.info(
            f"Overdue message sent | User={user.email} | Cycle={cycle.cycle_name} (ID={cycle.cycle_id}) | Task={task.task_name} (ID={task.cycle_task_id})"
        )

    except Exception as e:
        # Log failed overdue notification
        logger.error(
            f"Overdue message failed | User={user.email} | "
            f"Cycle={cycle.cycle_name} (ID={cycle.cycle_id}) | Task={task.task_name} (ID={task.cycle_task_id}) | Error={e}"
        )