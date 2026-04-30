import secrets
from uuid_extensions import uuid7
from django.db import models


def generate_uuid7():
    return uuid7()


class User(models.Model):
    ROLE_ADMIN = "admin"
    ROLE_ANALYST = "analyst"
    ROLE_CHOICES = [
        (ROLE_ADMIN, "Admin"),
        (ROLE_ANALYST, "Analyst"),
    ]

    id = models.UUIDField(primary_key=True, default=generate_uuid7, editable=False)
    github_id = models.CharField(max_length=50, unique=True)
    username = models.CharField(max_length=150)
    email = models.CharField(max_length=254, blank=True, default="")
    avatar_url = models.CharField(max_length=500, blank=True, default="")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_ANALYST)
    is_active = models.BooleanField(default=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users"

    def __str__(self):
        return f"@{self.username} ({self.role})"

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN


class RefreshToken(models.Model):
    id = models.UUIDField(primary_key=True, default=generate_uuid7, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="refresh_tokens"
    )
    token = models.CharField(max_length=128, unique=True)
    is_revoked = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "refresh_tokens"

    @staticmethod
    def generate_token():
        return secrets.token_urlsafe(64)

    def __str__(self):
        return f"RefreshToken({self.user.username}, revoked={self.is_revoked})"
