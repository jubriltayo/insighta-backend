"""
authentication/tests.py
"""

from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import User
from authentication.tokens import (
    issue_access_token,
    issue_refresh_token_record,
    decode_access_token,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_user(username="testuser", role=User.ROLE_ANALYST, is_active=True):
    return User.objects.create(
        github_id=f"gh_{username}",
        username=username,
        email=f"{username}@example.com",
        role=role,
        is_active=is_active,
    )


# ---------------------------------------------------------------------------
# Token unit tests (no HTTP, no rate limiting)
# ---------------------------------------------------------------------------


class TokenTests(TestCase):
    def test_access_token_issued_and_decodable(self):
        user = make_user()
        token = issue_access_token(user)
        self.assertIsNotNone(token)
        payload = decode_access_token(token)
        self.assertEqual(payload["user_id"], str(user.id))
        self.assertEqual(payload["username"], user.username)
        self.assertEqual(payload["role"], user.role)

    def test_refresh_token_record_created(self):
        user = make_user()
        record = issue_refresh_token_record(user)
        self.assertIsNotNone(record.token)
        self.assertFalse(record.is_revoked)
        self.assertGreater(record.expires_at, timezone.now())

    def test_expired_access_token_raises(self):
        import jwt
        from datetime import datetime
        from django.conf import settings

        user = make_user()
        payload = {
            "user_id": str(user.id),
            "username": user.username,
            "role": user.role,
            "iat": datetime(2000, 1, 1),
            "exp": datetime(2000, 1, 1),
        }
        expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        with self.assertRaises(jwt.ExpiredSignatureError):
            decode_access_token(expired_token)


# ---------------------------------------------------------------------------
# Token refresh endpoint
# Rate limiting applies to /auth/* so cache.clear() is required in setUp.
# ---------------------------------------------------------------------------


class TokenRefreshTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        cache.clear()  # prevent rate limit bleed from other tests

    def test_valid_refresh_issues_new_pair(self):
        record = issue_refresh_token_record(self.user)
        response = self.client.post(
            "/auth/refresh",
            {"refresh_token": record.token},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)

    def test_old_refresh_token_is_revoked_after_use(self):
        record = issue_refresh_token_record(self.user)
        self.client.post(
            "/auth/refresh", {"refresh_token": record.token}, format="json"
        )
        record.refresh_from_db()
        self.assertTrue(record.is_revoked)

    def test_reused_refresh_token_is_rejected(self):
        record = issue_refresh_token_record(self.user)
        self.client.post(
            "/auth/refresh", {"refresh_token": record.token}, format="json"
        )
        response = self.client.post(
            "/auth/refresh",
            {"refresh_token": record.token},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_expired_refresh_token_rejected(self):
        record = issue_refresh_token_record(self.user)
        record.expires_at = timezone.now() - timedelta(seconds=1)
        record.save()
        response = self.client.post(
            "/auth/refresh",
            {"refresh_token": record.token},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_nonexistent_refresh_token_rejected(self):
        response = self.client.post(
            "/auth/refresh",
            {"refresh_token": "this-does-not-exist"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_inactive_user_refresh_rejected(self):
        inactive_user = make_user(username="inactive", is_active=False)
        record = issue_refresh_token_record(inactive_user)
        response = self.client.post(
            "/auth/refresh",
            {"refresh_token": record.token},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_missing_refresh_token_returns_400(self):
        response = self.client.post("/auth/refresh", {}, format="json")
        self.assertEqual(response.status_code, 400)


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


class LogoutTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        cache.clear()

    def test_logout_revokes_refresh_token(self):
        record = issue_refresh_token_record(self.user)
        self.client.post(
            "/auth/logout",
            {"refresh_token": record.token},
            format="json",
        )
        record.refresh_from_db()
        self.assertTrue(record.is_revoked)

    def test_logout_with_no_token_still_returns_200(self):
        response = self.client.post("/auth/logout", {}, format="json")
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# WhoAmI
# ---------------------------------------------------------------------------


class WhoAmITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()

    def test_whoami_returns_user_data(self):
        user = make_user(username="jubril", role=User.ROLE_ADMIN)
        response = self.client.get(
            "/auth/me",
            HTTP_AUTHORIZATION=f"Bearer {issue_access_token(user)}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["username"], "jubril")
        self.assertEqual(data["role"], "admin")

    def test_whoami_unauthenticated_returns_401(self):
        response = self.client.get("/auth/me")
        self.assertEqual(response.status_code, 401)


# ---------------------------------------------------------------------------
# CLI token exchange
# ---------------------------------------------------------------------------

FAKE_GH_USER = {
    "id": 99999,
    "login": "cliuser",
    "email": "cli@example.com",
    "avatar_url": "https://example.com/avatar.png",
}


class CLITokenExchangeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()

    @patch("authentication.views._fetch_github_user", return_value=FAKE_GH_USER)
    def test_valid_exchange_returns_tokens(self, _mock):
        response = self.client.post(
            "/auth/cli/token",
            {"code": "abc", "code_verifier": "verifier123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertEqual(data["username"], "cliuser")

    def test_missing_code_returns_400(self):
        response = self.client.post(
            "/auth/cli/token",
            {"code_verifier": "verifier123"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_code_verifier_returns_400(self):
        response = self.client.post(
            "/auth/cli/token",
            {"code": "abc"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("authentication.views._fetch_github_user", return_value=None)
    def test_github_failure_returns_502(self, _mock):
        response = self.client.post(
            "/auth/cli/token",
            {"code": "bad", "code_verifier": "verifier"},
            format="json",
        )
        self.assertEqual(response.status_code, 502)

    @patch("authentication.views._fetch_github_user", return_value=FAKE_GH_USER)
    def test_inactive_user_blocked(self, _mock):
        User.objects.create(
            github_id=str(FAKE_GH_USER["id"]),
            username=FAKE_GH_USER["login"],
            is_active=False,
        )
        response = self.client.post(
            "/auth/cli/token",
            {"code": "abc", "code_verifier": "verifier"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
