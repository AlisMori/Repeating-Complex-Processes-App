from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    # Stores whether the user wants to receive notifications.
    # This field is needed for notification settings and future reminder logic.
    notification_opt_in = models.BooleanField(default=True)

    # Stores when the user record was created.
    # Django already has date_joined, but this field matches our ERD naming.
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username