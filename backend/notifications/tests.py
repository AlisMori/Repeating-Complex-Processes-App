from django.test import TestCase
from django.core import mail

import datetime

from cycles.models import CycleInstance, CycleTask, CycleActivity, TaskDependency
from templates_mgmt.models import Template, TemplateActivity,TemplateTask
from accounts.models import User

from notifications.tasks import check_notifications

# Create your tests here.
class NotificationsTest(TestCase):
    def setUp(self):
        self.today = datetime.date.today()
        # 1. Set Up Users
        # Create a user who wants notifications
        self.user = User.objects.create(
            password="recurrabestapp1!",
            last_login= None,
            is_superuser= False,
            username= "er",
            first_name="Iskandar",
            last_name="Chekayev",
            email="example@gmail.com",
            is_staff=False,
            is_active=True,
            date_joined=datetime.datetime(2026, 7, 14, 11, 46, 11, 99947, tzinfo = datetime.timezone.utc),
            notification_opt_in= True,
            created_at= datetime.datetime(
            2026, 7, 14, 11, 46, 11, 612017, tzinfo=datetime.timezone.utc))

        self.user = User.objects.create(
            password="recurrabestapp2@",
            last_login=None,
            is_superuser=False,
            username="re",
            first_name="Iskandar",
            last_name="Zalishew",
            email="example@gmail.com",
            is_staff=False,
            is_active=True,
            date_joined=datetime.datetime(2026, 7, 14, 11, 46, 11, 99947, tzinfo=datetime.timezone.utc),
            notification_opt_in=True,
            created_at=datetime.datetime(
                2026, 7, 14, 11, 46, 11, 612017, tzinfo=datetime.timezone.utc))

        # 2. Set Up Templates, Activities and Tasks with Dependencies
        self.test_template = Template.objects.create(
            user=self.user,
            template_name="Unit Coordination",
        )

        # Template tasks
        self.template_task1 = TemplateTask.objects.create(
            template=self.test_template,
            task_name="Lab2",
            day_offset=0,
            duration_days=1,
        )

        self.template_task2 = TemplateTask.objects.create(
            template=self.test_template,
            task_name="Lab8",
            day_offset=0,
            duration_days=1,
        )

        self.template_task3 = TemplateTask.objects.create(
            template=self.test_template,
            task_name="Assignment1",
            day_offset=0,
            duration_days=1,
        )

        self.template_task4 = TemplateTask.objects.create(
            template=self.test_template,
            task_name="Assignment2",
            day_offset=0,
            duration_days=1,
        )

        self.template_task5 = TemplateTask.objects.create(
            template=self.test_template,
            task_name="Exam",
            day_offset=0,
            duration_days=1,
        )

        # Sample Activity
        self.template_activity = TemplateActivity.objects.create(
            template=self.test_template,
            activity_name="Teaching",
            start_offset_days=0,
            end_offset_days=30,
        )


        # 3. Set Up Cycles with its Activities and Tasks
        # Create a running cycle
        self.cycle = CycleInstance.objects.create(
            user=self.user,
            template=self.test_template,
            start_date=datetime.date(2026, 6, 19),
            status="running"
        )

        # Create task with one seven day reminder
        self.task_7_day_reminder = CycleTask.objects.create(
            cycle=self.cycle,
            template_task=self.template_task1,
            task_name="Lab2",
            calculated_start_date=self.today + datetime.timedelta(days=7),
            calculated_end_date=self.today + datetime.timedelta(days=8),
            reminder_lead_days=[7,],
            status=False
        )

        # Create task with one three day reminder
        self.task_3_day_reminder = CycleTask.objects.create(
            cycle=self.cycle,
            template_task=self.template_task2,
            task_name="Lab8",
            calculated_start_date=self.today + datetime.timedelta(days=3),
            calculated_end_date=self.today + datetime.timedelta(days=4),
            reminder_lead_days=[3,],
            status=False
        )

        # Create task with one current day reminder
        self.task_0_day_reminder = CycleTask.objects.create(
            cycle=self.cycle,
            template_task=self.template_task3,
            task_name="Assignment1",
            calculated_start_date=self.today,
            calculated_end_date=self.today + datetime.timedelta(days=1),
            reminder_lead_days=[0,],
            status=False
        )

        # Overdue task
        self.overdue_task = CycleTask.objects.create(
            cycle=self.cycle,
            template_task=self.template_task4,
            task_name="Assignment2",
            calculated_start_date=self.today + datetime.timedelta(days=-1),
            calculated_end_date=self.today,
            reminder_lead_days=[7, 3, 0],
            status=False
        )

        # Multiple reminders task
        self.task_7_day_reminder = CycleTask.objects.create(
            cycle=self.cycle,
            template_task=self.template_task5,
            task_name="Exam",
            calculated_start_date=self.today + datetime.timedelta(days=7),
            calculated_end_date=self.today + datetime.timedelta(days=8),
            reminder_lead_days=[7, 3, 0],
            status=False
        )

        # Test Cycle Activity
        self.test_cycle_activity = CycleActivity.objects.create(
            cycle=self.cycle,
            template_activity=self.template_activity,
            activity_name="Teaching",
            calculated_start_date=datetime.date(2026, 6, 19),
            calculated_end_date=datetime.date(2026, 7, 19),
        )

    def test_setUp(self):
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(Template.objects.count(), 1)
        self.assertEqual(TemplateTask.objects.count(), 5)
        self.assertEqual(TemplateActivity.objects.count(), 1)
        self.assertEqual(CycleInstance.objects.count(), 1)
        self.assertEqual(CycleTask.objects.count(), 5)
        self.assertEqual(CycleActivity.objects.count(), 1)



    def test_opted_users(self):
        check_notifications()
        self.assertEqual(len(mail.outbox), 4)

    def test_7day_reminders(self):
        check_notifications()
        self.assertEqual(len(mail.outbox), 4)

    def test_3day_reminders(self):
        check_notifications()
        self.assertEqual(len(mail.outbox), 4)

    def test_on_day_reminders(self):
        check_notifications()
        self.assertEqual(len(mail.outbox), 4)

    def test_overdue_notifications(self):
        check_notifications()
        self.assertEqual(len(mail.outbox), 4)




class EmailsTest(TestCase):
    pass


class SchedulerTest(TestCase):
    pass

