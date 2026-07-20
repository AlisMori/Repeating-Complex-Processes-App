"""Product verification tests for the current Recurra build.

Test ID to requirement mapping:
- PV-01 verifies current-build environment startup, URL loading, and core API route availability for FR-1, FR-8, FR-12, FR-14.
- PV-02 verifies migration graph integrity and that the current models match committed migrations for all installed apps with migrations.
- PV-03 verifies the authentication and dashboard smoke workflow for FR-1, FR-8, and FR-12.
- PV-04 verifies the template-to-cycle core workflow for implemented parts of FR-2, FR-4, FR-5, FR-6, FR-12, and FR-14.
- PV-05 verifies template versioning and cycle isolation for FR-3 and the snapshot behaviour relied on by FR-4.
- PV-06 verifies runtime task updates, dependency-driven date shifting, and overdue visibility for implemented parts of FR-6, FR-7, FR-10, and FR-12.
- PV-07 verifies ownership isolation and template sharing for FR-13.
- PV-08 verifies password recovery plus reminder/overdue notification behaviour for implemented parts of FR-9 and FR-11.
- PV-09 verifies notes persistence plus the implemented export surface for FR-14 and the currently available part of FR-15.
- PV-10 verifies the primary read endpoints of completed backend modules through controlled smoke checks.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, timedelta

from django.apps import apps
from django.core import mail
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.test import override_settings
from django.urls import resolve, reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from cycles.models import CycleTask
from notifications.models import NotificationDelivery
from notifications.tasks import check_notifications
from templates_mgmt.models import Template, TemplateActivity, TemplateTask


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="test@example.com",
    ALLOWED_HOSTS=["testserver", "localhost"],
    FRONTEND_URL="http://localhost:5173",
)
class ProductVerificationTests(APITestCase):
    maxDiff = None

    base_today = date(2026, 7, 20)

    def register_user(self, username, email, password="StrongPass123!"):
        response = self.client.post(
            reverse("auth-register"),
            {
                "username": username,
                "email": email,
                "password": password,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data

    def login_user(self, username, password="StrongPass123!"):
        response = self.client.post(
            reverse("auth-login"),
            {
                "username": username,
                "password": password,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def authenticate(self, username, email=None, password="StrongPass123!"):
        if not User.objects.filter(username=username).exists():
            self.register_user(username, email or f"{username}@example.com", password=password)
        tokens = self.login_user(username, password=password)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        return tokens

    def create_template(self, template_name, description="", is_public=False):
        response = self.client.post(
            reverse("templates-list"),
            {
                "template_name": template_name,
                "description": description,
                "is_public": is_public,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data

    def create_template_activity(self, template_id, activity_name, start_offset, end_offset, note_text=None):
        payload = {
            "template": template_id,
            "activity_name": activity_name,
            "start_offset_days": start_offset,
            "end_offset_days": end_offset,
        }
        if note_text is not None:
            payload["note_text"] = note_text
        response = self.client.post(reverse("template-activities-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data

    def create_template_task(
        self,
        template_id,
        task_name,
        day_offset,
        duration_days=1,
        *,
        template_activity_id=None,
        is_mandatory=True,
        is_fixed_date=False,
        reminder_lead_days=None,
        note_text=None,
    ):
        payload = {
            "template": template_id,
            "task_name": task_name,
            "day_offset": day_offset,
            "duration_days": duration_days,
            "is_mandatory": is_mandatory,
            "is_fixed_date": is_fixed_date,
        }
        if template_activity_id is not None:
            payload["template_activity"] = template_activity_id
        if reminder_lead_days is not None:
            payload["reminder_lead_days"] = reminder_lead_days
        if note_text is not None:
            payload["note_text"] = note_text
        response = self.client.post(reverse("template-tasks-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data

    def create_dependency(self, task_id, depends_on_task_id):
        response = self.client.post(
            reverse("task-dependencies-list"),
            {"task": task_id, "depends_on_task": depends_on_task_id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data

    def create_cycle_from_template(self, template_id, cycle_name, start_date_value):
        response = self.client.post(
            reverse("templates-create-cycle", args=[template_id]),
            {"cycle_name": cycle_name, "start_date": start_date_value.isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data

    def get_cycle_tasks(self, cycle_id):
        response = self.client.get(reverse("cycle-tasks-list"), {"cycle": cycle_id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def get_cycle_activities(self, cycle_id):
        response = self.client.get(reverse("cycle-activities-list"), {"cycle": cycle_id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def get_template_tasks(self, template_id):
        response = self.client.get(reverse("template-tasks-list"), {"template": template_id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def get_template_activities(self, template_id):
        response = self.client.get(reverse("template-activities-list"), {"template": template_id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def extract_password_reset_link(self):
        self.assertEqual(len(mail.outbox), 1)
        urls = re.findall(
            r"http://localhost:5173/auth/password-reset/confirm/\S+",
            mail.outbox[0].body,
        )
        self.assertEqual(len(urls), 1)
        return urls[0]

    def test_pv01_environment_and_route_configuration_are_valid(self):
        """PV-01: system checks, app loading, URL configuration, and key route resolution succeed."""
        call_command("check", fail_level="ERROR", verbosity=0)

        self.assertEqual(resolve(reverse("auth-register")).url_name, "auth-register")
        self.assertEqual(resolve(reverse("auth-login")).url_name, "auth-login")
        self.assertEqual(resolve(reverse("auth-password-reset")).url_name, "auth-password-reset")
        self.assertEqual(resolve(reverse("dashboard-summary")).url_name, "dashboard-summary")
        self.assertEqual(resolve(reverse("templates-list")).url_name, "templates-list")
        self.assertEqual(resolve(reverse("template-tasks-list")).url_name, "template-tasks-list")
        self.assertEqual(resolve(reverse("template-activities-list")).url_name, "template-activities-list")
        self.assertEqual(resolve(reverse("task-dependencies-list")).url_name, "task-dependencies-list")
        self.assertEqual(resolve(reverse("cycles-list")).url_name, "cycles-list")
        self.assertEqual(resolve(reverse("cycle-tasks-list")).url_name, "cycle-tasks-list")
        self.assertEqual(resolve(reverse("cycle-activities-list")).url_name, "cycle-activities-list")
        self.assertEqual(resolve(reverse("smart-search")).url_name, "smart-search")

        for app_label in ("accounts", "cycles", "notifications", "templates_mgmt", "dashboard"):
            self.assertIn(app_label, apps.app_configs)

    def test_pv02_migration_graph_matches_the_current_model_state(self):
        """PV-02: migration loader, leaf migrations, and model-to-migration state are all current."""
        loader = MigrationLoader(connection, ignore_no_migrations=True)
        executor = MigrationExecutor(connection)

        leaf_nodes = loader.graph.leaf_nodes()
        self.assertTrue(leaf_nodes)

        apps_with_disk_migrations = {app_label for app_label, _ in loader.disk_migrations}
        for app_label in apps_with_disk_migrations:
            for leaf in loader.graph.leaf_nodes(app_label):
                self.assertIn(leaf, loader.applied_migrations)

        self.assertEqual(executor.migration_plan(leaf_nodes), [])
        call_command("makemigrations", check=True, dry_run=True, verbosity=0)

    def test_pv03_authentication_and_dashboard_smoke_workflow(self):
        """PV-03: a user can register, log in, access the dashboard, and unauthenticated access is rejected."""
        anonymous_dashboard = self.client.get(reverse("dashboard-summary"))
        self.assertEqual(anonymous_dashboard.status_code, status.HTTP_401_UNAUTHORIZED)

        register_data = self.register_user("pv03_user", "pv03_user@example.com")
        self.assertEqual(register_data["user"]["username"], "pv03_user")

        tokens = self.login_user("pv03_user")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        me_response = self.client.get(reverse("auth-me"))
        dashboard_response = self.client.get(reverse("dashboard-summary"))

        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data["username"], "pv03_user")
        self.assertEqual(dashboard_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            dashboard_response.data,
            {"active_cycles": [], "overdue_tasks": [], "upcoming_tasks": []},
        )

        logout_response = self.client.post(
            reverse("auth-logout"),
            {"refresh": tokens["refresh"]},
            format="json",
        )
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

    def test_pv04_template_to_cycle_core_workflow(self):
        """PV-04: template content is created through the API and materializes into a running cycle and dashboard data."""
        self.authenticate("pv04_owner", "pv04_owner@example.com")
        template = self.create_template("Employee Onboarding", "PV-04 template")
        activity = self.create_template_activity(
            template["template_id"],
            "Orientation Week",
            0,
            5,
            note_text="Attend all orientation events.",
        )
        task_a = self.create_template_task(
            template["template_id"],
            "Sign contract",
            0,
            duration_days=2,
            template_activity_id=activity["template_activity_id"],
            reminder_lead_days=[3, 0],
            note_text="Contract note",
        )
        task_b = self.create_template_task(
            template["template_id"],
            "Provision laptop",
            2,
            duration_days=1,
            template_activity_id=activity["template_activity_id"],
            is_mandatory=False,
            note_text="Laptop note",
        )
        self.create_dependency(task_b["template_task_id"], task_a["template_task_id"])

        template_detail = self.client.get(reverse("templates-detail", args=[template["template_id"]]))
        template_tasks = self.get_template_tasks(template["template_id"])
        template_activities = self.get_template_activities(template["template_id"])

        self.assertEqual(template_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(template_detail.data["template_name"], "Employee Onboarding")
        self.assertEqual({task["task_name"] for task in template_tasks}, {"Sign contract", "Provision laptop"})
        self.assertEqual(template_tasks[0]["note_text"], "Contract note")
        self.assertEqual(template_activities[0]["note_text"], "Attend all orientation events.")

        cycle = self.create_cycle_from_template(
            template["template_id"],
            "July 20 Onboarding",
            self.base_today,
        )
        cycle_detail = self.client.get(reverse("cycles-detail", args=[cycle["cycle_id"]]))
        cycle_tasks = self.get_cycle_tasks(cycle["cycle_id"])
        cycle_activities = self.get_cycle_activities(cycle["cycle_id"])
        dashboard = self.client.get(reverse("dashboard-summary"))

        self.assertEqual(cycle_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(cycle_detail.data["status"], "running")
        self.assertEqual(len(cycle_tasks), 2)
        self.assertEqual(len(cycle_activities), 1)

        runtime_tasks = {task["task_name"]: task for task in cycle_tasks}
        self.assertEqual(runtime_tasks["Sign contract"]["calculated_start_date"], "2026-07-20")
        self.assertEqual(runtime_tasks["Sign contract"]["calculated_end_date"], "2026-07-22")
        self.assertEqual(runtime_tasks["Sign contract"]["reminder_lead_days"], [3, 0])
        self.assertEqual(runtime_tasks["Provision laptop"]["calculated_start_date"], "2026-07-22")
        self.assertEqual(runtime_tasks["Provision laptop"]["calculated_end_date"], "2026-07-23")
        self.assertEqual(runtime_tasks["Provision laptop"]["is_mandatory"], False)
        self.assertEqual(runtime_tasks["Provision laptop"]["note_text"], "Laptop note")
        self.assertEqual(cycle_activities[0]["calculated_start_date"], "2026-07-20")
        self.assertEqual(cycle_activities[0]["calculated_end_date"], "2026-07-25")

        self.assertEqual(dashboard.status_code, status.HTTP_200_OK)
        self.assertEqual(len(dashboard.data["active_cycles"]), 1)
        self.assertEqual(dashboard.data["active_cycles"][0]["cycle_name"], "July 20 Onboarding")

    def test_pv05_template_versioning_preserves_existing_cycle_snapshots(self):
        """PV-05: editing a used template creates a new version and leaves older cycles on their original copied data."""
        self.authenticate("pv05_owner", "pv05_owner@example.com")
        template = self.create_template("Versioned Template", "PV-05 template")
        task = self.create_template_task(template["template_id"], "Original Task", 0, duration_days=1)

        old_cycle = self.create_cycle_from_template(template["template_id"], "Original Cycle", self.base_today)
        old_cycle_tasks_before = self.get_cycle_tasks(old_cycle["cycle_id"])
        self.assertEqual(old_cycle_tasks_before[0]["task_name"], "Original Task")
        self.assertEqual(old_cycle_tasks_before[0]["calculated_start_date"], "2026-07-20")

        update_response = self.client.patch(
            reverse("template-tasks-detail", args=[task["template_task_id"]]),
            {"task_name": "Revised Task", "day_offset": 5, "duration_days": 2},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        new_template_id = update_response.data["new_template_version"]["template_id"]
        self.assertNotEqual(new_template_id, template["template_id"])

        versions_response = self.client.get(reverse("templates-versions", args=[new_template_id]))
        old_template_detail = self.client.get(reverse("templates-detail", args=[template["template_id"]]))
        new_template_tasks = self.get_template_tasks(new_template_id)
        old_cycle_tasks_after = self.get_cycle_tasks(old_cycle["cycle_id"])

        self.assertEqual(versions_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(versions_response.data), 2)
        self.assertEqual(old_template_detail.status_code, status.HTTP_200_OK)
        self.assertFalse(old_template_detail.data["is_current_version"])
        self.assertEqual(new_template_tasks[0]["task_name"], "Revised Task")
        self.assertEqual(new_template_tasks[0]["day_offset"], 5)
        self.assertEqual(old_cycle_tasks_after[0]["task_name"], "Original Task")
        self.assertEqual(old_cycle_tasks_after[0]["calculated_start_date"], "2026-07-20")

        new_cycle = self.create_cycle_from_template(new_template_id, "Revised Cycle", self.base_today)
        new_cycle_tasks = self.get_cycle_tasks(new_cycle["cycle_id"])
        self.assertEqual(new_cycle_tasks[0]["task_name"], "Revised Task")
        self.assertEqual(new_cycle_tasks[0]["calculated_start_date"], "2026-07-25")
        self.assertEqual(new_cycle_tasks[0]["calculated_end_date"], "2026-07-27")

    def test_pv06_runtime_task_dependency_shift_and_overdue_visibility_workflow(self):
        """PV-06: runtime status changes, dependency-driven shifts, and overdue visibility behave through the current product surface."""
        self.authenticate("pv06_owner", "pv06_owner@example.com")
        template = self.create_template("Runtime Template", "PV-06 template")
        task_a = self.create_template_task(template["template_id"], "Upstream", 0, duration_days=2)
        task_b = self.create_template_task(template["template_id"], "Downstream", 2, duration_days=1)
        self.create_dependency(task_b["template_task_id"], task_a["template_task_id"])

        cycle_one = self.create_cycle_from_template(template["template_id"], "Cycle One", self.base_today)
        cycle_two = self.create_cycle_from_template(template["template_id"], "Cycle Two", self.base_today)

        cycle_one_tasks = {task["task_name"]: task for task in self.get_cycle_tasks(cycle_one["cycle_id"])}
        cycle_two_tasks = {task["task_name"]: task for task in self.get_cycle_tasks(cycle_two["cycle_id"])}

        start_response = self.client.patch(
            reverse("cycle-tasks-detail", args=[cycle_one_tasks["Upstream"]["cycle_task_id"]]),
            {"status": "in_progress"},
            format="json",
        )
        self.assertEqual(start_response.status_code, status.HTTP_200_OK)
        self.assertEqual(start_response.data["status"], "in_progress")

        shift_response = self.client.post(
            reverse("cycle-tasks-shift", args=[cycle_one_tasks["Upstream"]["cycle_task_id"]]),
            {"delay_days": 2, "scope": "cascade"},
            format="json",
        )
        self.assertEqual(shift_response.status_code, status.HTTP_200_OK)

        shifted_cycle_one_tasks = {task["task_name"]: task for task in self.get_cycle_tasks(cycle_one["cycle_id"])}
        cycle_two_tasks_after = {task["task_name"]: task for task in self.get_cycle_tasks(cycle_two["cycle_id"])}
        template_tasks_after = {task["task_name"]: task for task in self.get_template_tasks(template["template_id"])}

        self.assertEqual(shifted_cycle_one_tasks["Upstream"]["calculated_start_date"], "2026-07-22")
        self.assertEqual(shifted_cycle_one_tasks["Downstream"]["calculated_start_date"], "2026-07-24")
        self.assertEqual(template_tasks_after["Upstream"]["day_offset"], 0)
        self.assertEqual(template_tasks_after["Downstream"]["day_offset"], 2)
        self.assertEqual(cycle_two_tasks_after["Upstream"]["calculated_start_date"], "2026-07-20")
        self.assertEqual(cycle_two_tasks_after["Downstream"]["calculated_start_date"], "2026-07-22")

        overdue_task = CycleTask.objects.get(cycle_task_id=shifted_cycle_one_tasks["Downstream"]["cycle_task_id"])
        overdue_task.status = "overdue"
        overdue_task.calculated_end_date = self.base_today - timedelta(days=1)
        overdue_task.save(update_fields=["status", "calculated_end_date"])

        cycle_tasks_with_overdue = {task["task_name"]: task for task in self.get_cycle_tasks(cycle_one["cycle_id"])}
        dashboard = self.client.get(reverse("dashboard-summary"))

        self.assertEqual(cycle_tasks_with_overdue["Downstream"]["status"], "overdue")
        overdue_names = [task["task_name"] for task in dashboard.data["overdue_tasks"]]
        self.assertIn("Downstream", overdue_names)

    def test_pv07_template_sharing_creates_an_isolated_recipient_copy(self):
        """PV-07: another user cannot access private data before sharing and receives an independent copy after sharing."""
        self.authenticate("pv07_owner", "pv07_owner@example.com")
        template = self.create_template("Private Template", "PV-07 template")
        self.create_template_task(template["template_id"], "Shared Task", 0, duration_days=1)

        self.register_user("pv07_recipient", "pv07_recipient@example.com")
        recipient_tokens = self.login_user("pv07_recipient")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {recipient_tokens['access']}")

        forbidden_before_share = self.client.get(reverse("templates-detail", args=[template["template_id"]]))
        self.assertEqual(forbidden_before_share.status_code, status.HTTP_404_NOT_FOUND)

        owner_tokens = self.login_user("pv07_owner")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_tokens['access']}")
        share_response = self.client.post(
            reverse("templates-share", args=[template["template_id"]]),
            {"username": "pv07_recipient"},
            format="json",
        )
        self.assertEqual(share_response.status_code, status.HTTP_201_CREATED)

        shared_template_id = share_response.data["template"]["template_id"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {recipient_tokens['access']}")
        shared_detail = self.client.get(reverse("templates-detail", args=[shared_template_id]))
        shared_tasks = self.get_template_tasks(shared_template_id)

        self.assertEqual(shared_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(shared_detail.data["created_by_type"], "shared")
        self.assertEqual({task["task_name"] for task in shared_tasks}, {"Shared Task"})

        recipient_update = self.client.patch(
            reverse("templates-detail", args=[shared_template_id]),
            {"template_name": "Recipient Copy"},
            format="json",
        )
        self.assertEqual(recipient_update.status_code, status.HTTP_200_OK)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_tokens['access']}")
        owner_detail = self.client.get(reverse("templates-detail", args=[template["template_id"]]))
        self.assertEqual(owner_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(owner_detail.data["template_name"], "Private Template")

    def test_pv08_password_reset_and_notifications_workflow(self):
        """PV-08: password reset, reminder delivery, overdue delivery, opt-out, and duplicate suppression all work in the current build."""
        self.register_user("pv08_user", "pv08_user@example.com")

        reset_request = self.client.post(
            reverse("auth-password-reset"),
            {"email": "pv08_user@example.com"},
            format="json",
        )
        self.assertEqual(reset_request.status_code, status.HTTP_200_OK)

        reset_link = self.extract_password_reset_link()
        _, uid, token = reset_link.rstrip("/").rsplit("/", 2)

        validate_response = self.client.get(reverse("password_reset_confirm", args=[uid, token]))
        self.assertEqual(validate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(validate_response.data["code"], "valid_link")

        reset_confirm = self.client.post(
            reverse("auth-password-reset-confirm"),
            {"uid": uid, "token": token, "new_password": "EvenStronger123!"},
            format="json",
        )
        self.assertEqual(reset_confirm.status_code, status.HTTP_200_OK)

        new_login = self.client.post(
            reverse("auth-login"),
            {"username": "pv08_user", "password": "EvenStronger123!"},
            format="json",
        )
        reused_token = self.client.post(
            reverse("auth-password-reset-confirm"),
            {"uid": uid, "token": token, "new_password": "AnotherStrong123!"},
            format="json",
        )

        self.assertEqual(new_login.status_code, status.HTTP_200_OK)
        self.assertEqual(reused_token.status_code, status.HTTP_400_BAD_REQUEST)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_login.data['access']}")
        template = self.create_template("Notifications Template", "PV-08 template")
        reminder_template_task = self.create_template_task(
            template["template_id"],
            "Reminder Task",
            0,
            duration_days=1,
            reminder_lead_days=[0],
        )
        overdue_template_task = self.create_template_task(
            template["template_id"],
            "Overdue Task",
            0,
            duration_days=1,
        )
        opt_out_template_task = self.create_template_task(
            template["template_id"],
            "Opt-out Task",
            0,
            duration_days=1,
            reminder_lead_days=[0],
        )
        cycle = self.create_cycle_from_template(
            template["template_id"],
            "Notifications Cycle",
            self.base_today,
        )
        runtime_tasks = {task["task_name"]: task for task in self.get_cycle_tasks(cycle["cycle_id"])}

        opt_out_response = self.client.post(
            reverse(
                "cycle-tasks-notification-preference",
                args=[runtime_tasks["Opt-out Task"]["cycle_task_id"]],
            ),
            {"notification_opt_in": False},
            format="json",
        )
        self.assertEqual(opt_out_response.status_code, status.HTTP_200_OK)

        overdue_task = CycleTask.objects.get(cycle_task_id=runtime_tasks["Overdue Task"]["cycle_task_id"])
        overdue_task.calculated_end_date = self.base_today - timedelta(days=1)
        overdue_task.save(update_fields=["calculated_end_date"])

        mail.outbox.clear()
        check_notifications(today=self.base_today)
        check_notifications(today=self.base_today)

        self.assertEqual(len(mail.outbox), 2)
        subjects = {message.subject for message in mail.outbox}
        self.assertIn("Recurra - Reminder: Reminder Task", subjects)
        self.assertIn("Recurra - Task overdue: Overdue Task", subjects)

        reminder_delivery = NotificationDelivery.objects.get(
            task_id=runtime_tasks["Reminder Task"]["cycle_task_id"],
            notification_key="reminder:0",
        )
        overdue_delivery = NotificationDelivery.objects.get(
            task_id=runtime_tasks["Overdue Task"]["cycle_task_id"],
            notification_key="overdue",
        )
        self.assertEqual(reminder_delivery.status, NotificationDelivery.STATUS_SENT)
        self.assertEqual(overdue_delivery.status, NotificationDelivery.STATUS_SENT)
        self.assertFalse(
            NotificationDelivery.objects.filter(
                task_id=runtime_tasks["Opt-out Task"]["cycle_task_id"]
            ).exists()
        )

    def test_pv09_notes_and_export_workflow(self):
        """PV-09: notes remain attached to the correct objects and the implemented export endpoints return usable content."""
        self.authenticate("pv09_owner", "pv09_owner@example.com")
        template = self.create_template("Export Template", "PV-09 template")
        activity = self.create_template_activity(
            template["template_id"],
            "Implementation Activity",
            0,
            2,
            note_text="Template activity note",
        )
        task = self.create_template_task(
            template["template_id"],
            "Implementation Task",
            0,
            duration_days=1,
            template_activity_id=activity["template_activity_id"],
            note_text="Template task note",
        )
        cycle = self.create_cycle_from_template(template["template_id"], "Export Cycle", self.base_today)

        runtime_task = self.get_cycle_tasks(cycle["cycle_id"])[0]
        runtime_activity = self.get_cycle_activities(cycle["cycle_id"])[0]

        set_task_note = self.client.post(
            reverse("cycle-tasks-note", args=[runtime_task["cycle_task_id"]]),
            {"note_text": "Runtime task note"},
            format="json",
        )
        set_activity_note = self.client.post(
            reverse("cycle-activities-note", args=[runtime_activity["cycle_activity_id"]]),
            {"note_text": "Runtime activity note"},
            format="json",
        )
        template_download = self.client.get(
            reverse("templates-download", args=[template["template_id"]]),
            {"file_format": "csv"},
        )
        cycle_export = self.client.get(reverse("cycles-export", args=[cycle["cycle_id"]]))

        self.assertEqual(set_task_note.status_code, status.HTTP_200_OK)
        self.assertEqual(set_activity_note.status_code, status.HTTP_200_OK)
        self.assertEqual(set_task_note.data["note_text"], "Runtime task note")
        self.assertEqual(set_activity_note.data["note_text"], "Runtime activity note")

        template_task_detail = self.client.get(reverse("template-tasks-detail", args=[task["template_task_id"]]))
        template_activity_detail = self.client.get(
            reverse("template-activities-detail", args=[activity["template_activity_id"]])
        )

        self.assertEqual(template_task_detail.data["note_text"], "Template task note")
        self.assertEqual(template_activity_detail.data["note_text"], "Template activity note")
        self.assertEqual(template_download.status_code, status.HTTP_200_OK)
        self.assertEqual(template_download["Content-Type"], "text/csv")
        self.assertIn(".csv", template_download["Content-Disposition"])

        parsed_csv = list(csv.DictReader(io.StringIO(template_download.content.decode("utf-8"))))
        row_types = {row["row_type"] for row in parsed_csv}
        self.assertIn("template", row_types)
        self.assertIn("activity", row_types)
        self.assertIn("task", row_types)
        self.assertIn("Template task note", template_download.content.decode("utf-8"))

        self.assertEqual(cycle_export.status_code, status.HTTP_200_OK)
        self.assertEqual(cycle_export.data["cycle_name"], "Export Cycle")
        self.assertEqual(cycle_export.data["cycle_tasks"][0]["note_text"], "Runtime task note")
        self.assertEqual(cycle_export.data["cycle_activities"][0]["note_text"], "Runtime activity note")

        self.register_user("pv09_other", "pv09_other@example.com")
        other_tokens = self.login_user("pv09_other")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {other_tokens['access']}")
        forbidden_download = self.client.get(
            reverse("templates-download", args=[template["template_id"]]),
            {"file_format": "csv"},
        )
        self.assertEqual(forbidden_download.status_code, status.HTTP_404_NOT_FOUND)

    def test_pv10_primary_completed_module_read_endpoints_return_expected_statuses(self):
        """PV-10: the primary read endpoints of completed backend modules answer with controlled success codes."""
        self.authenticate("pv10_owner", "pv10_owner@example.com")
        template = self.create_template("Smoke Template", "PV-10 template")
        activity = self.create_template_activity(template["template_id"], "Smoke Activity", 0, 1)
        task = self.create_template_task(
            template["template_id"],
            "Smoke Task",
            0,
            duration_days=1,
            template_activity_id=activity["template_activity_id"],
        )
        cycle = self.create_cycle_from_template(template["template_id"], "Smoke Cycle", self.base_today)
        cycle_task = self.get_cycle_tasks(cycle["cycle_id"])[0]
        cycle_activity = self.get_cycle_activities(cycle["cycle_id"])[0]

        checks = [
            ("auth-me", reverse("auth-me"), {}, status.HTTP_200_OK),
            ("auth-user-search", reverse("auth-user-search"), {"q": "pv10"}, status.HTTP_200_OK),
            ("smart-search", reverse("smart-search"), {"q": "Sm", "context": "global"}, status.HTTP_200_OK),
            ("dashboard-summary", reverse("dashboard-summary"), {}, status.HTTP_200_OK),
            ("templates-list", reverse("templates-list"), {}, status.HTTP_200_OK),
            ("templates-detail", reverse("templates-detail", args=[template["template_id"]]), {}, status.HTTP_200_OK),
            ("templates-versions", reverse("templates-versions", args=[template["template_id"]]), {}, status.HTTP_200_OK),
            (
                "templates-timeline-preview",
                reverse("templates-timeline-preview", args=[template["template_id"]]),
                {},
                status.HTTP_200_OK,
            ),
            ("template-tasks-list", reverse("template-tasks-list"), {"template": template["template_id"]}, status.HTTP_200_OK),
            ("template-tasks-detail", reverse("template-tasks-detail", args=[task["template_task_id"]]), {}, status.HTTP_200_OK),
            (
                "template-activities-list",
                reverse("template-activities-list"),
                {"template": template["template_id"]},
                status.HTTP_200_OK,
            ),
            (
                "template-activities-detail",
                reverse("template-activities-detail", args=[activity["template_activity_id"]]),
                {},
                status.HTTP_200_OK,
            ),
            ("tags-list", reverse("tags-list"), {}, status.HTTP_200_OK),
            ("template-categories-list", reverse("template-categories-list"), {}, status.HTTP_200_OK),
            ("task-dependencies-list", reverse("task-dependencies-list"), {}, status.HTTP_200_OK),
            ("cycles-list", reverse("cycles-list"), {}, status.HTTP_200_OK),
            ("cycles-detail", reverse("cycles-detail", args=[cycle["cycle_id"]]), {}, status.HTTP_200_OK),
            ("cycles-export", reverse("cycles-export", args=[cycle["cycle_id"]]), {}, status.HTTP_200_OK),
            ("cycle-tasks-list", reverse("cycle-tasks-list"), {"cycle": cycle["cycle_id"]}, status.HTTP_200_OK),
            ("cycle-tasks-detail", reverse("cycle-tasks-detail", args=[cycle_task["cycle_task_id"]]), {}, status.HTTP_200_OK),
            (
                "cycle-tasks-available-statuses",
                reverse("cycle-tasks-available-statuses", args=[cycle_task["cycle_task_id"]]),
                {},
                status.HTTP_200_OK,
            ),
            (
                "cycle-activities-list",
                reverse("cycle-activities-list"),
                {"cycle": cycle["cycle_id"]},
                status.HTTP_200_OK,
            ),
            (
                "cycle-activities-detail",
                reverse("cycle-activities-detail", args=[cycle_activity["cycle_activity_id"]]),
                {},
                status.HTTP_200_OK,
            ),
        ]

        for name, url, params, expected_status in checks:
            with self.subTest(endpoint=name):
                response = self.client.get(url, params)
                self.assertEqual(response.status_code, expected_status)
