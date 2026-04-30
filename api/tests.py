"""
api/tests.py
"""

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import User
from authentication.tokens import issue_access_token
from api.models import Profile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_user(username="user", role=User.ROLE_ANALYST, is_active=True):
    return User.objects.create(
        github_id=f"gh_{username}",
        username=username,
        role=role,
        is_active=is_active,
    )


def make_profile(**kwargs):
    defaults = dict(
        name="Test Person",
        gender="male",
        gender_probability=0.9,
        age=25,
        age_group="adult",
        country_id="NG",
        country_name="Nigeria",
        country_probability=0.8,
    )
    defaults.update(kwargs)
    return Profile.objects.create(**defaults)


def api_headers(user):
    token = issue_access_token(user)
    return {
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "HTTP_X_API_VERSION": "1",
    }


# ---------------------------------------------------------------------------
# Authentication enforcement
# ---------------------------------------------------------------------------


class AuthEnforcementTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()

    def test_unauthenticated_list_returns_401(self):
        response = self.client.get("/api/profiles", HTTP_X_API_VERSION="1")
        self.assertEqual(response.status_code, 401)

    def test_unauthenticated_search_returns_401(self):
        response = self.client.get(
            "/api/profiles/search?q=young males", HTTP_X_API_VERSION="1"
        )
        self.assertEqual(response.status_code, 401)

    def test_invalid_token_returns_401(self):
        response = self.client.get(
            "/api/profiles",
            HTTP_AUTHORIZATION="Bearer not-a-real-token",
            HTTP_X_API_VERSION="1",
        )
        self.assertEqual(response.status_code, 401)

    def test_inactive_user_returns_403(self):
        user = make_user(username="inactive", is_active=False)
        response = self.client.get("/api/profiles", **api_headers(user))
        self.assertEqual(response.status_code, 403)


# ---------------------------------------------------------------------------
# API versioning
# ---------------------------------------------------------------------------


class APIVersioningTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        cache.clear()

    def test_missing_version_header_returns_400(self):
        token = issue_access_token(self.user)
        response = self.client.get(
            "/api/profiles",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "API version header required")

    def test_wrong_version_header_returns_400(self):
        token = issue_access_token(self.user)
        response = self.client.get(
            "/api/profiles",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_API_VERSION="2",
        )
        self.assertEqual(response.status_code, 400)

    def test_correct_version_header_passes(self):
        response = self.client.get("/api/profiles", **api_headers(self.user))
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# Role enforcement
# ---------------------------------------------------------------------------


class RoleEnforcementTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()

    def test_analyst_cannot_create_profile(self):
        analyst = make_user(username="analyst", role=User.ROLE_ANALYST)
        response = self.client.post(
            "/api/profiles",
            {"name": "Harriet Tubman"},
            format="json",
            **api_headers(analyst),
        )
        self.assertEqual(response.status_code, 403)

    def test_analyst_cannot_delete_profile(self):
        analyst = make_user(username="analyst2", role=User.ROLE_ANALYST)
        profile = make_profile(name="To Delete")
        response = self.client.delete(
            f"/api/profiles/{profile.id}",
            **api_headers(analyst),
        )
        self.assertEqual(response.status_code, 403)

    def test_analyst_can_list_profiles(self):
        analyst = make_user(username="analyst3", role=User.ROLE_ANALYST)
        response = self.client.get("/api/profiles", **api_headers(analyst))
        self.assertEqual(response.status_code, 200)

    def test_analyst_can_get_profile(self):
        analyst = make_user(username="analyst4", role=User.ROLE_ANALYST)
        profile = make_profile(name="Readable Profile")
        response = self.client.get(
            f"/api/profiles/{profile.id}", **api_headers(analyst)
        )
        self.assertEqual(response.status_code, 200)

    @patch(
        "api.views.GenderizeClient.fetch_gender_data",
        return_value={"gender": "female", "probability": 0.95},
    )
    @patch(
        "api.views.AgifyClient.fetch_age_data",
        return_value={"age": 30, "age_group": "adult"},
    )
    @patch(
        "api.views.NationalizeClient.fetch_nationality_data",
        return_value={
            "country_id": "US",
            "country_name": "United States",
            "country_probability": 0.88,
        },
    )
    def test_admin_can_create_profile(self, _m1, _m2, _m3):
        admin = make_user(username="admin1", role=User.ROLE_ADMIN)
        response = self.client.post(
            "/api/profiles",
            {"name": "Harriet Tubman"},
            format="json",
            **api_headers(admin),
        )
        self.assertEqual(response.status_code, 201)

    def test_admin_can_delete_profile(self):
        admin = make_user(username="admin2", role=User.ROLE_ADMIN)
        profile = make_profile(name="Admin Delete Target")
        response = self.client.delete(
            f"/api/profiles/{profile.id}", **api_headers(admin)
        )
        self.assertEqual(response.status_code, 204)


# ---------------------------------------------------------------------------
# Profile list — filters, sorting, pagination
# ---------------------------------------------------------------------------


class ProfileListTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        cache.clear()

        make_profile(
            name="Alice", gender="female", age=22, age_group="adult", country_id="NG"
        )
        make_profile(
            name="Bob", gender="male", age=35, age_group="adult", country_id="US"
        )
        make_profile(
            name="Charlie", gender="male", age=15, age_group="teenager", country_id="NG"
        )

    def test_list_returns_all_profiles(self):
        response = self.client.get("/api/profiles", **api_headers(self.user))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 3)

    def test_pagination_shape_present(self):
        response = self.client.get(
            "/api/profiles?page=1&limit=2", **api_headers(self.user)
        )
        data = response.json()
        for key in ("page", "limit", "total", "total_pages", "links", "data"):
            self.assertIn(key, data)
        self.assertIn("self", data["links"])
        self.assertIn("next", data["links"])
        self.assertIn("prev", data["links"])

    def test_pagination_next_null_on_last_page(self):
        response = self.client.get(
            "/api/profiles?page=1&limit=10", **api_headers(self.user)
        )
        self.assertIsNone(response.json()["links"]["next"])

    def test_pagination_prev_null_on_first_page(self):
        response = self.client.get(
            "/api/profiles?page=1&limit=2", **api_headers(self.user)
        )
        self.assertIsNone(response.json()["links"]["prev"])

    def test_pagination_next_present_on_first_of_multiple_pages(self):
        response = self.client.get(
            "/api/profiles?page=1&limit=2", **api_headers(self.user)
        )
        self.assertIsNotNone(response.json()["links"]["next"])

    def test_gender_filter(self):
        response = self.client.get(
            "/api/profiles?gender=male", **api_headers(self.user)
        )
        data = response.json()
        self.assertEqual(data["total"], 2)
        for profile in data["data"]:
            self.assertEqual(profile["gender"], "male")

    def test_country_filter(self):
        response = self.client.get(
            "/api/profiles?country_id=NG", **api_headers(self.user)
        )
        self.assertEqual(response.json()["total"], 2)

    def test_min_age_filter(self):
        response = self.client.get("/api/profiles?min_age=30", **api_headers(self.user))
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["data"][0]["name"], "Bob")

    def test_max_age_filter(self):
        response = self.client.get("/api/profiles?max_age=20", **api_headers(self.user))
        for profile in response.json()["data"]:
            self.assertLessEqual(profile["age"], 20)

    def test_invalid_param_returns_400(self):
        response = self.client.get("/api/profiles?foo=bar", **api_headers(self.user))
        self.assertEqual(response.status_code, 400)

    def test_sort_by_age_asc(self):
        response = self.client.get(
            "/api/profiles?sort_by=age&order=asc", **api_headers(self.user)
        )
        ages = [p["age"] for p in response.json()["data"]]
        self.assertEqual(ages, sorted(ages))

    def test_sort_by_age_desc(self):
        response = self.client.get(
            "/api/profiles?sort_by=age&order=desc", **api_headers(self.user)
        )
        ages = [p["age"] for p in response.json()["data"]]
        self.assertEqual(ages, sorted(ages, reverse=True))


# ---------------------------------------------------------------------------
# Profile detail
# ---------------------------------------------------------------------------


class ProfileDetailTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        self.profile = make_profile(name="Detail Target")
        cache.clear()

    def test_get_profile_by_id(self):
        response = self.client.get(
            f"/api/profiles/{self.profile.id}", **api_headers(self.user)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["name"], "Detail Target")

    def test_get_nonexistent_profile_returns_404(self):
        response = self.client.get(
            "/api/profiles/00000000-0000-0000-0000-000000000000",
            **api_headers(self.user),
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_profile_removes_it(self):
        admin = make_user(username="deleter", role=User.ROLE_ADMIN)
        response = self.client.delete(
            f"/api/profiles/{self.profile.id}", **api_headers(admin)
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Profile.objects.filter(id=self.profile.id).exists())


# ---------------------------------------------------------------------------
# Natural language search
# ---------------------------------------------------------------------------


class ProfileSearchTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        cache.clear()

        make_profile(
            name="Young Nigerian Male",
            gender="male",
            age=20,
            age_group="adult",
            country_id="NG",
        )
        make_profile(
            name="Older US Female",
            gender="female",
            age=45,
            age_group="adult",
            country_id="US",
        )

    def test_search_by_gender(self):
        response = self.client.get(
            "/api/profiles/search?q=males", **api_headers(self.user)
        )
        self.assertEqual(response.status_code, 200)
        for profile in response.json()["data"]:
            self.assertEqual(profile["gender"], "male")

    def test_search_by_country(self):
        response = self.client.get(
            "/api/profiles/search?q=people from nigeria", **api_headers(self.user)
        )
        self.assertEqual(response.status_code, 200)
        for profile in response.json()["data"]:
            self.assertEqual(profile["country_id"], "NG")

    def test_search_unparseable_query_returns_400(self):
        response = self.client.get(
            "/api/profiles/search?q=people", **api_headers(self.user)
        )
        self.assertEqual(response.status_code, 400)

    def test_search_missing_query_returns_400(self):
        response = self.client.get("/api/profiles/search", **api_headers(self.user))
        self.assertEqual(response.status_code, 400)

    def test_search_returns_paginated_shape(self):
        response = self.client.get(
            "/api/profiles/search?q=males from nigeria", **api_headers(self.user)
        )
        data = response.json()
        for key in ("page", "limit", "total", "total_pages", "links", "data"):
            self.assertIn(key, data)


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


class ProfileExportTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        cache.clear()

        make_profile(name="Export Male NG", gender="male", country_id="NG")
        make_profile(name="Export Female US", gender="female", country_id="US")

    def test_export_returns_csv_content_type(self):
        response = self.client.get(
            "/api/profiles/export?format=csv", **api_headers(self.user)
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])

    def test_export_content_disposition_header(self):
        response = self.client.get(
            "/api/profiles/export?format=csv", **api_headers(self.user)
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("profiles_", response["Content-Disposition"])

    def test_export_csv_has_correct_columns(self):
        response = self.client.get(
            "/api/profiles/export?format=csv", **api_headers(self.user)
        )
        self.assertEqual(response.status_code, 200)
        lines = response.content.decode().splitlines()
        header = lines[0]
        expected = "id,name,gender,gender_probability,age,age_group,country_id,country_name,country_probability,created_at"
        self.assertEqual(header, expected)

    def test_export_gender_filter_applied(self):
        response = self.client.get(
            "/api/profiles/export?format=csv&gender=male", **api_headers(self.user)
        )
        self.assertEqual(response.status_code, 200)
        lines = response.content.decode().splitlines()
        for line in lines[1:]:
            cols = line.split(",")
            self.assertEqual(cols[2], "male")

    def test_export_invalid_format_returns_400(self):
        response = self.client.get(
            "/api/profiles/export?format=json", **api_headers(self.user)
        )
        self.assertEqual(response.status_code, 400)

    def test_export_requires_auth(self):
        response = self.client.get(
            "/api/profiles/export?format=csv", HTTP_X_API_VERSION="1"
        )
        self.assertEqual(response.status_code, 401)

    def test_export_endpoint_is_reachable(self):
        """Regression: export must not be swallowed by the <profile_id> wildcard route."""
        response = self.client.get(
            "/api/profiles/export?format=csv", **api_headers(self.user)
        )
        self.assertNotEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Create profile
# ---------------------------------------------------------------------------


class ProfileCreateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = make_user(username="admin_create", role=User.ROLE_ADMIN)
        cache.clear()

    @patch(
        "api.views.GenderizeClient.fetch_gender_data",
        return_value={"gender": "male", "probability": 0.91},
    )
    @patch(
        "api.views.AgifyClient.fetch_age_data",
        return_value={"age": 28, "age_group": "adult"},
    )
    @patch(
        "api.views.NationalizeClient.fetch_nationality_data",
        return_value={
            "country_id": "US",
            "country_name": "United States",
            "country_probability": 0.89,
        },
    )
    def test_create_profile_success(self, _m1, _m2, _m3):
        response = self.client.post(
            "/api/profiles",
            {"name": "Harriet Tubman"},
            format="json",
            **api_headers(self.admin),
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertIn("id", data)
        self.assertEqual(data["gender"], "male")

    @patch(
        "api.views.GenderizeClient.fetch_gender_data",
        return_value={"gender": "male", "probability": 0.91},
    )
    @patch(
        "api.views.AgifyClient.fetch_age_data",
        return_value={"age": 28, "age_group": "adult"},
    )
    @patch(
        "api.views.NationalizeClient.fetch_nationality_data",
        return_value={
            "country_id": "US",
            "country_name": "United States",
            "country_probability": 0.89,
        },
    )
    def test_create_profile_idempotent(self, _m1, _m2, _m3):
        self.client.post(
            "/api/profiles",
            {"name": "Idempotent Name"},
            format="json",
            **api_headers(self.admin),
        )
        response = self.client.post(
            "/api/profiles",
            {"name": "Idempotent Name"},
            format="json",
            **api_headers(self.admin),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Profile already exists")

    def test_create_profile_missing_name_returns_400(self):
        response = self.client.post(
            "/api/profiles", {}, format="json", **api_headers(self.admin)
        )
        self.assertEqual(response.status_code, 400)

    @patch("api.views.GenderizeClient.fetch_gender_data", return_value=None)
    def test_genderize_failure_returns_502(self, _mock):
        response = self.client.post(
            "/api/profiles",
            {"name": "Some Name"},
            format="json",
            **api_headers(self.admin),
        )
        self.assertEqual(response.status_code, 502)

    @patch(
        "api.views.GenderizeClient.fetch_gender_data",
        return_value={"gender": "male", "probability": 0.9},
    )
    @patch("api.views.AgifyClient.fetch_age_data", return_value=None)
    def test_agify_failure_returns_502(self, _m1, _m2):
        response = self.client.post(
            "/api/profiles",
            {"name": "Another Name"},
            format="json",
            **api_headers(self.admin),
        )
        self.assertEqual(response.status_code, 502)


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class RateLimitTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_auth_endpoint_rate_limited_after_10_requests(self):
        for i in range(10):
            self.client.post("/auth/refresh", {"refresh_token": "fake"}, format="json")

        response = self.client.post(
            "/auth/refresh", {"refresh_token": "fake"}, format="json"
        )
        self.assertEqual(response.status_code, 429)
