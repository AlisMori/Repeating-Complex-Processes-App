from datetime import timedelta
import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import User
from cycles.models import CycleInstance, CycleTask

from .models import NotificationDelivery
from .services import (
    send_reminder_email,
    send_overdue_email,
)

MAX_NOTIFICATION_ATTEMPTS = 2


def check_notifications(today=None):
    # Use unified timezone
    today = today or timezone.localdate()

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
            tasks = CycleTask.objects.filter(cycle=cycle)

            # Check whether a task requires a reminder before task's start or whether a task is overdue
            for task in tasks:

                check_reminder(user, cycle, task, today)
                check_overdue(user, cycle, task, today)


def check_reminder(user, cycle, task, today):
    if not task.notification_opt_in:
        return

    # Ensure reminders are set and present
    if not task.reminder_lead_days:
        return

    # Check against all set reminders
    for days_before in task.reminder_lead_days:
        reminder_date = (
            task.calculated_start_date
            - timedelta(days=days_before)
        )

        # Preserve the configured lead-time; only due or previously failed
        # deliveries are eligible to run.
        if reminder_date > today:
            continue

        send_notification_delivery(
            user=user,
            cycle=cycle,
            task=task,
            notification_kind=NotificationDelivery.KIND_REMINDER,
            notification_key=f"reminder:{days_before}",
            scheduled_for=reminder_date,
            today=today,
            reminder_lead_days=days_before,
        )


def check_overdue(user, cycle, task, today):
    if not task.notification_opt_in:
        return

    # Don't notify about tasks that are completed
    if task.status == "completed":
        return

    # Don't notify about tasks that are not yet overdue
    if task.calculated_end_date >= today:
        return

    send_notification_delivery(
        user=user,
        cycle=cycle,
        task=task,
        notification_kind=NotificationDelivery.KIND_OVERDUE,
        notification_key="overdue",
        scheduled_for=task.calculated_end_date + timedelta(days=1),
        today=today,
    )


def send_notification_delivery(
    *,
    user,
    cycle,
    task,
    notification_kind,
    notification_key,
    scheduled_for,
    today,
    reminder_lead_days=None,
):
    logger = logging.getLogger("emails")
    if scheduled_for > today:
        return False

    with transaction.atomic():
        delivery = _get_or_create_delivery(
            task=task,
            notification_kind=notification_kind,
            notification_key=notification_key,
            scheduled_for=scheduled_for,
            reminder_lead_days=reminder_lead_days,
        )

        if delivery.status == NotificationDelivery.STATUS_SENT:
            return False

        if delivery.status == NotificationDelivery.STATUS_FAILED:
            return False

        attempt_count = delivery.attempt_count + 1
        attempted_at = timezone.now()

        try:
            if notification_kind == NotificationDelivery.KIND_REMINDER:
                send_reminder_email(user, cycle, task)
                success_message = (
                    f"Reminder sent | User={user.email} | Cycle={cycle.cycle_name} "
                    f"(ID={cycle.cycle_id}) | Task={task.task_name} "
                    f"(ID={task.cycle_task_id}) | LeadDays={reminder_lead_days}"
                )
            else:
                send_overdue_email(user, cycle, task)
                success_message = (
                    f"Overdue message sent | User={user.email} | Cycle={cycle.cycle_name} "
                    f"(ID={cycle.cycle_id}) | Task={task.task_name} "
                    f"(ID={task.cycle_task_id})"
                )
        except Exception as exc:
            delivery.attempt_count = attempt_count
            delivery.last_attempt_at = attempted_at
            delivery.last_error = str(exc)
            update_fields = ["attempt_count", "last_attempt_at", "last_error", "updated_at"]

            if attempt_count >= MAX_NOTIFICATION_ATTEMPTS:
                delivery.status = NotificationDelivery.STATUS_FAILED
                delivery.final_failure_at = attempted_at
                update_fields.extend(["status", "final_failure_at"])
                logger.error(
                    f"{notification_kind.title()} permanently failed | User={user.email} | "
                    f"Cycle={cycle.cycle_name} (ID={cycle.cycle_id}) | Task={task.task_name} "
                    f"(ID={task.cycle_task_id}) | Attempt={attempt_count} | Error={exc}"
                )
            else:
                logger.error(
                    f"{notification_kind.title()} failed; retry pending | User={user.email} | "
                    f"Cycle={cycle.cycle_name} (ID={cycle.cycle_id}) | Task={task.task_name} "
                    f"(ID={task.cycle_task_id}) | Attempt={attempt_count} | Error={exc}"
                )

            delivery.save(update_fields=update_fields)
            return False

        delivery.attempt_count = attempt_count
        delivery.last_attempt_at = attempted_at
        delivery.status = NotificationDelivery.STATUS_SENT
        delivery.sent_at = attempted_at
        delivery.final_failure_at = None
        delivery.last_error = ""
        delivery.save(
            update_fields=[
                "attempt_count",
                "last_attempt_at",
                "status",
                "sent_at",
                "final_failure_at",
                "last_error",
                "updated_at",
            ]
        )
        logger.info(success_message)
        return True


def _get_or_create_delivery(
    *,
    task,
    notification_kind,
    notification_key,
    scheduled_for,
    reminder_lead_days,
):
    try:
        return NotificationDelivery.objects.select_for_update().get(
            task=task,
            notification_key=notification_key,
        )
    except NotificationDelivery.DoesNotExist:
        try:
            return NotificationDelivery.objects.create(
                task=task,
                notification_kind=notification_kind,
                notification_key=notification_key,
                scheduled_for=scheduled_for,
                reminder_lead_days=reminder_lead_days,
            )
        except IntegrityError:
            return NotificationDelivery.objects.select_for_update().get(
                task=task,
                notification_key=notification_key,
            )
