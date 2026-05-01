import base64
import hashlib
import json
import os
import secrets
from urllib.parse import urlencode

import requests as http_requests
from django.conf import settings
from django.utils import timezone as dj_timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from .models import User, RefreshToken
from .tokens import issue_access_token, issue_refresh_token_record

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"


def _error(message, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"status": "error", "message": message}, status=status_code)


def _cookie_domain():
    env = os.getenv("ENVIRONMENT", "development")
    if env == "production":
        return "up.railway.app"
    return None


def _redirect_response(location, status=status.HTTP_302_FOUND):
    return Response(status=status, headers={"Location": location})


def _fetch_github_user(code, code_verifier=None, redirect_uri=None):
    """
    Exchange code (+ optional code verifier for PKCE) with Github
    Returns the Github user dict or None on failure
    """
    payload = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "client_secret": settings.GITHUB_CLIENT_SECRET,
        "code": code,
    }
    if redirect_uri:
        payload["redirect_uri"] = redirect_uri
    if code_verifier:
        payload["code_verifier"] = code_verifier

    token_response = http_requests.post(
        GITHUB_TOKEN_URL,
        headers={"Accept": "application/json"},
        data=payload,
        timeout=10,
    )

    if token_response.status_code != 200:
        return None

    github_access_token = token_response.json().get("access_token")
    if not github_access_token:
        return None

    user_response = http_requests.get(
        GITHUB_USER_URL,
        headers={
            "Authorization": f"Bearer {github_access_token}",
            "Accept": "application/json",
        },
        timeout=10,
    )

    if user_response.status_code != 200:
        return None

    return user_response.json()


def _fetch_github_user_cli(code, code_verifier=None, redirect_uri=None):
    """
    Same as _fetch_github_user but uses CLI OAuth App credentials.
    """
    payload = {
        "client_id": settings.CLI_GITHUB_CLIENT_ID,
        "client_secret": settings.CLI_GITHUB_CLIENT_SECRET,
        "code": code,
    }
    if redirect_uri:
        payload["redirect_uri"] = redirect_uri
    if code_verifier:
        payload["code_verifier"] = code_verifier

    token_response = http_requests.post(
        GITHUB_TOKEN_URL,
        headers={"Accept": "application/json"},
        data=payload,
        timeout=10,
    )

    if token_response.status_code != 200:
        return None

    github_access_token = token_response.json().get("access_token")
    if not github_access_token:
        return None

    user_response = http_requests.get(
        GITHUB_USER_URL,
        headers={
            "Authorization": f"Bearer {github_access_token}",
            "Accept": "application/json",
        },
        timeout=10,
    )

    if user_response.status_code != 200:
        return None

    return user_response.json()


def _upsert_user(gh_user):
    """
    Create or update a user from Github user data
    """
    user, _ = User.objects.update_or_create(
        github_id=str(gh_user["id"]),
        defaults={
            "username": gh_user.get("login", ""),
            "email": gh_user.get("email", "") or "",
            "avatar_url": gh_user.get("avatar_url", "") or "",
            "last_login_at": dj_timezone.now(),
        },
    )
    return user


class GithubOAuthInitView(APIView):
    """
    GET /auth/github
    Web flow: backend generates state + PKCE
    """

    def get(self, request):
        state = secrets.token_urlsafe(32)

        code_verifier = secrets.token_urlsafe(64)
        code_challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )

        params = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "scope": "read:user user:email",
            "redirect_uri": settings.GITHUB_CALLBACK_URL,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        response = _redirect_response(f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}")

        domain = _cookie_domain()

        response.set_cookie(
            "oauth_state",
            state,
            httponly=True,
            secure=True,
            samesite="None",
            max_age=300,
            domain=domain,
        )

        response.set_cookie(
            "code_verifier",
            code_verifier,
            httponly=True,
            secure=True,
            samesite="None",
            max_age=300,
            domain=domain,
        )

        return response



class GithubCallbackView(APIView):
    """
    GET /auth/github/callback
    Web flow only. Github redirects here after user approves.
    Sets HTTP-only cookies and redirects to the web portal.
    """

    def get(self, request):
        code = request.GET.get("code")
        state = request.GET.get("state")
        error = request.GET.get("error")

        if error:
            return _error(f"Github OAuth error: {error}")

        if not code:
            return _error("Missing authorization code")

        # vailidate state
        cookie_state = request.COOKIES.get("oauth_state")
        if not state or state != cookie_state:
            return _error("Invalid state")

        code_verifier = request.COOKIES.get("code_verifier")

        gh_user = _fetch_github_user(
            code, code_verifier=code_verifier, redirect_uri=settings.GITHUB_CALLBACK_URL
        )

        if not gh_user:
            return _error(
                "Failed to authenticate with Github", status.HTTP_502_BAD_GATEWAY
            )

        user = _upsert_user(gh_user)

        if not user.is_active:
            return _error("Account is inactive", status.HTTP_403_FORBIDDEN)

        access_token = issue_access_token(user)
        refresh_record = issue_refresh_token_record(user)

        response = _redirect_response(f"{settings.WEB_PORTAL_URL}/dashboard")

        domain = _cookie_domain()

        response.set_cookie(
            "access_token",
            access_token,
            httponly=True,
            secure=True,
            samesite="None",
            max_age=180,
            domain=domain,
        )
        response.set_cookie(
            "refresh_token",
            refresh_record.token,
            httponly=True,
            secure=True,
            samesite="None",
            max_age=300,
            path="/auth/refresh",
            domain=domain,
        )

        response.delete_cookie("oauth_state")
        response.delete_cookie("code_verifier")

        return response


@method_decorator(csrf_exempt, name="dispatch")
class CLITokenExchangeView(APIView):
    """
    POST /auth/cli/token
    CLI flow only. After Github redirects to the CLI's local server,
    the CLI sends { code, code_verifier } here.
    Backend exchanges with Github (Github verifies PKCE)
    then returns { access_token, refresh_token } as JSON.
    """

    def post(self, request):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return _error("Invalid JSON body")

        code = body.get("code")
        code_verifier = body.get("code_verifier")
        # _state = body.get(
        #     "state"
        # )  # optional, can be used by CLI to prevent CSRF in its own flow
        redirect_uri = body.get(
            "redirect_uri"
        )  # optional, only needed if CLI used a custom one

        if not code:
            return _error("Missing code")

        if not code_verifier:
            return _error("Missing code_verifier")

        gh_user = _fetch_github_user_cli(
            code, code_verifier=code_verifier, redirect_uri=redirect_uri
        )
        if not gh_user:
            return _error(
                "Failed to authenticate with Github", status.HTTP_502_BAD_GATEWAY
            )

        user = _upsert_user(gh_user)

        if not user.is_active:
            return _error("Account is inactive", status.HTTP_403_FORBIDDEN)

        access_token = issue_access_token(user)
        refresh_record = issue_refresh_token_record(user)

        return Response(
            {
                "status": "success",
                "username": user.username,
                "role": user.role,
                "access_token": access_token,
                "refresh_token": refresh_record.token,
            }
        )


class TokenRefreshView(APIView):
    """
    POST /auth/refresh
    Accepts refresh token from JSON body (CLI) or cookie (web).
    Revokes old token immediately. Issues a new pair
    """

    def post(self, request):
        raw_token = request.COOKIES.get("refresh_token")
        if not raw_token:
            try:
                body = json.loads(request.body)
                raw_token = body.get("refresh_token")
            except (json.JSONDecodeError, AttributeError):
                pass

        if not raw_token:
            return _error("Missing refresh token")

        try:
            record = RefreshToken.objects.select_related("user").get(token=raw_token)
        except RefreshToken.DoesNotExist:
            return _error(
                "Invalid or reused refresh token", status.HTTP_401_UNAUTHORIZED
            )

        if record.is_revoked:
            return _error("Refresh token already used", status.HTTP_401_UNAUTHORIZED)

        if dj_timezone.now() > record.expires_at:
            return _error("Refresh token expired", status.HTTP_401_UNAUTHORIZED)

        if not record.user.is_active:
            return _error("Account is inactive", status.HTTP_403_FORBIDDEN)

        record.is_revoked = True
        record.save(update_fields=["is_revoked"])

        user = record.user
        new_access_token = issue_access_token(user)
        new_refresh_record = issue_refresh_token_record(user)

        if request.COOKIES.get("refresh_token"):
            response = Response(
                {
                    "status": "success",
                }
            )

            domain = _cookie_domain()

            response.set_cookie(
                "access_token",
                new_access_token,
                httponly=True,
                secure=True,
                samesite="None",
                max_age=180,
                domain=domain,
            )
            response.set_cookie(
                "refresh_token",
                new_refresh_record.token,
                httponly=True,
                secure=True,
                samesite="None",
                max_age=300,
                path="/auth/refresh",
                domain=domain,
            )
            return response

        return Response(
            {
                "status": "success",
                "access_token": new_access_token,
                "refresh_token": new_refresh_record.token,
            }
        )


class LogoutView(APIView):
    """
    POST /auth/logout
    Revokes refresh token server-side. Clears cookies for web.
    """

    def post(self, request):
        raw_token = request.COOKIES.get("refresh_token")
        if not raw_token:
            try:
                body = json.loads(request.body)
                raw_token = body.get("refresh_token")
            except (json.JSONDecodeError, AttributeError):
                pass

        if raw_token:
            RefreshToken.objects.filter(token=raw_token).update(is_revoked=True)

        response = Response({"status": "success", "message": "Logged out"})
        domain = _cookie_domain()
        response.delete_cookie("access_token", domain=domain)
        response.delete_cookie("refresh_token", path="/auth/refresh", domain=domain)
        return response


class WhoAmIView(APIView):
    """
    GET /auth/me
    Returns the currently authenticated user's profile.
    """

    def get(self, request):
        user = getattr(request, "auth_user", None)
        if not user:
            return _error("Authentication required", status.HTTP_401_UNAUTHORIZED)

        return Response(
            {
                "status": "success",
                "data": {
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                    "avatar_url": user.avatar_url,
                    "role": user.role,
                    "is_active": user.is_active,
                    "last_login_at": (
                        user.last_login_at.isoformat().replace("+00:00", "Z")
                        if user.last_login_at
                        else None
                    ),
                    "created_at": user.created_at.isoformat().replace("+00:00", "Z"),
                },
            }
        )
