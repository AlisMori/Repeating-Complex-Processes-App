from django.apps import apps as global_apps
from django.test import TestCase
from django_q.models import Schedule

from notifications.scheduler import register_scheduler, register_scheduler_on_migrate


class NotificationSchedulerRegistrationTests(TestCase):
    def test_register_scheduler_is_idempotent(self):
        first_schedule, first_created = register_scheduler()
        second_schedule, second_created = register_scheduler()

        self.assertFalse(second_created)
        self.assertEqual(first_schedule.pk, second_schedule.pk)
        self.assertIn(first_created, (True, False))
        self.assertEqual(first_schedule.name, "check_notifications")
        self.assertEqual(first_schedule.schedule_type, Schedule.DAILY)
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
        self.assertEqual(schedule.schedule_type, Schedule.DAILY)
        self.assertEqual(schedule.repeats, -1)
