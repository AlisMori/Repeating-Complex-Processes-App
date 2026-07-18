from django.apps import AppConfig
from django.db.models.signals import post_migrate


class NotificationsConfig(AppConfig):

    default_auto_field = "django.db.models.BigAutoField"

    name = "notifications"

    def ready(self):
        from .scheduler import register_scheduler_on_migrate

        post_migrate.connect(
            register_scheduler_on_migrate,
            sender=self,
            dispatch_uid="notifications.register_scheduler_on_migrate",
        )
