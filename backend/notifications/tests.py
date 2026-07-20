from datetime import date, timedelta
from unittest.mock import patch

from django.apps import apps as global_apps
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django_q.models import Schedule

from accounts.models import User
from cycles.models import CycleInstance, CycleTask
from notifications.models import NotificationDelivery
from notifications.scheduler import register_scheduler, register_scheduler_on_migrate
from notifications.services import send_reminder_email as real_send_reminder_email
from notifications.tasks import MAX_NOTIFICATION_ATTEMPTS, check_notifications
from templates_mgmt.models import Template, TemplateTask


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class NotificationSchedulerRegistrationTests(TestCase):
    def test_register_scheduler_is_idempotent_and_runs_every_five_minutes(self):
        first_schedule, first_created = register_scheduler()
        second_schedule, second_created = register_scheduler()

        self.assertFalse(second_created)
        self.assertEqual(first_schedule.pk, second_schedule.pk)
        self.assertIn(first_created, (True, False))
        self.assertEqual(first_schedule.name, "check_notifications")
        self.assertEqual(first_schedule.schedule_type, Schedule.MINUTES)
        self.assertEqual(first_schedule.minutes, 5)
        self.assertEqual(first_schedule.repeats, -1)
        self.assertEqual(
            Schedule.objects.filter(func="notifications.tasks.check_notifications").count(),
            1,
        )

    def test_post_migrate_registration_is_idempotent(self):
        register_scheduler_on_migrate(sender=None, apps=global_apps)
        register_scheduler_on_migrate(sender=None, apps=global_apps)

        schedule = Schedule.objects.get(func="notifications.tasks.check_notifications")
        self.assertEqual(schedule.name, "check_notifications")
        self.assertEqual(schedule.schedule_type, Schedule.MINUTES)
        self.assertEqual(schedule.minutes, 5)
        self.assertEqual(schedule.repeats, -1)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class NotificationDeliveryTests(TestCase):
    def setUp(self):
        self.today = date(2026, 7, 20)
        self.user = User.objects.create_user(
            username="notify-user",
            email="notify@example.com",
            password="strong-password-1",
            notification_opt_in=True,
        )
        self.template = Template.objects.create(
            user=self.user,
            template_name="Notification Template",
        )
        self.template_task = TemplateTask.objects.create(
            template=self.template,
            task_name="Reminder Task",
            day_offset=0,
            duration_days=1,
        )
        self.cycle = CycleInstance.objects.create(
            user=self.user,
            template=self.template,
            cycle_name="Notification Cycle",
            start_date=self.today - timedelta(days=3),
            status="running",
        )

    def _make_task(
        self,
        *,
        task_name="Reminder Task",
        start_delta_days=0,
        end_delta_days=1,
        reminders=None,
        status="pending",
    ):
        return CycleTask.objects.create(
            cycle=self.cycle,
            template_task=self.template_task,
            task_name=task_name,
            calculated_start_date=self.today + timedelta(days=start_delta_days),
            calculated_end_date=self.today + timedelta(days=end_delta_days),
            reminder_lead_days=reminders,
            status=status,
        )

    def test_successful_delivery_is_persisted_once(self):
        task = self._make_task(reminders=[0])

        check_notifications(today=self.today)
        check_notifications(today=self.today)

        self.assertEqual(len(mail.outbox), 1)
        delivery = NotificationDelivery.objects.get(task=task, notification_key="reminder:0")
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_SENT)
        self.assertEqual(delivery.attempt_count, 1)
        self.assertIsNotNone(delivery.sent_at)
        self.assertEqual(delivery.last_error, "")

    def test_failure_is_retried_and_then_succeeds(self):
        task = self._make_task(reminders=[0])

        attempts = {"count": 0}

        def flaky_send(user, cycle, cycle_task):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("smtp down")
            return real_send_reminder_email(user, cycle, cycle_task)

        with patch("notifications.tasks.send_reminder_email", side_effect=flaky_send):
            check_notifications(today=self.today)
            first = NotificationDelivery.objects.get(task=task, notification_key="reminder:0")
            self.assertEqual(first.status, NotificationDelivery.STATUS_PENDING)
            self.assertEqual(first.attempt_count, 1)
            self.assertEqual(len(mail.outbox), 0)

            check_notifications(today=self.today)

        delivery = NotificationDelivery.objects.get(task=task, notification_key="reminder:0")
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_SENT)
        self.assertEqual(delivery.attempt_count, 2)
        self.assertIsNotNone(delivery.sent_at)
        self.assertEqual(len(mail.outbox), 1)

    def test_retry_limit_marks_final_failure(self):
        task = self._make_task(reminders=[0])

        with patch("notifications.tasks.send_reminder_email", side_effect=RuntimeError("still failing")):
            check_notifications(today=self.today)
            check_notifications(today=self.today)
            check_notifications(today=self.today)

        delivery = NotificationDelivery.objects.get(task=task, notification_key="reminder:0")
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_FAILED)
        self.assertEqual(delivery.attempt_count, MAX_NOTIFICATION_ATTEMPTS)
        self.assertIsNotNone(delivery.final_failure_at)
        self.assertEqual(len(mail.outbox), 0)

    def test_overdue_notification_is_sent_once_across_repeated_runs(self):
        overdue_task = self._make_task(
            task_name="Overdue Task",
            start_delta_days=-5,
            end_delta_days=-1,
        )

        check_notifications(today=self.today)
        check_notifications(today=self.today)
        check_notifications(today=self.today)

        self.assertEqual(len(mail.outbox), 1)
        delivery = NotificationDelivery.objects.get(task=overdue_task, notification_key="overdue")
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_SENT)
        self.assertEqual(delivery.attempt_count, 1)

    def test_overdue_failure_does_not_mark_sent_before_success(self):
        overdue_task = self._make_task(
            task_name="Broken Overdue Task",
            start_delta_days=-5,
            end_delta_days=-1,
        )

        with patch("notifications.tasks.send_overdue_email", side_effect=RuntimeError("mail failure")):
            check_notifications(today=self.today)

        delivery = NotificationDelivery.objects.get(task=overdue_task, notification_key="overdue")
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_PENDING)
        self.assertEqual(delivery.attempt_count, 1)
        self.assertIsNone(delivery.sent_at)
        self.assertEqual(len(mail.outbox), 0)

    def test_notification_opt_out_skips_delivery(self):
        self.user.notification_opt_in = False
        self.user.save(update_fields=["notification_opt_in"])
        self._make_task(reminders=[0])

        check_notifications(today=self.today)

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(NotificationDelivery.objects.count(), 0)

    def test_tests_use_locmem_backend_and_send_no_real_emails(self):
        task = self._make_task(reminders=[0])

        check_notifications(today=self.today)

        self.assertEqual(mail.outbox[0].to, ["notify@example.com"])
        self.assertEqual(NotificationDelivery.objects.get(task=task, notification_key="reminder:0").status, "sent")

    def test_management_command_registers_five_minute_schedule(self):
        call_command("setup_notification_schedule")

        schedule = Schedule.objects.get(func="notifications.tasks.check_notifications")
        self.assertEqual(schedule.schedule_type, Schedule.MINUTES)
        self.assertEqual(schedule.minutes, 5)
