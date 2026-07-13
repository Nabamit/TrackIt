from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    timezone = models.CharField(max_length=50, default='UTC')
    grace_tokens_balance = models.IntegerField(default=0)
    reset_hour = models.IntegerField(default=0)

    # Resolve reverse accessor clashes by adding related_names if needed.
    # Note: AbstractUser already defines groups and user_permissions.
    # By default, they will conflict if there are multiple User models, but since we are overriding
    # and replacing the default User model, it will be standard and clean.
