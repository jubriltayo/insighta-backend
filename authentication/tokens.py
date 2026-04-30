import jwt
from datetime import datetime, timezone, timedelta
from django.conf import settings


from .models import RefreshToken


ACCESS_TOKEN_EXPIRY_MINUTES = 3
REFRESH_TOKEN_EXPIRY_MINUTES = 5


def issue_access_token(user):
    """
    Issue a short-lived JWT access token (3 minutes)
    Payload carries user ID, username, and role so the middleware
    can authorize requests without a DB lookup on every call.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": str(user.id),
        "username": user.username,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRY_MINUTES),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return token


def decode_access_token(token):
    """
    Decode and validate the JWT access token.
    Raises jwt.ExpiredSignatureError if expired.
    Raises jwt.InvalidTokenError if invalid.
    """
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    return payload


def issue_refresh_token_record(user):
    """
    Create and persist a refresh token DB record.
    Returns the RefreshToken instance.
    """
    now = datetime.now(tz=timezone.utc)
    raw_token = RefreshToken.generate_token()

    return RefreshToken.objects.create(
        user=user,
        token=raw_token,
        expires_at=now + timedelta(minutes=REFRESH_TOKEN_EXPIRY_MINUTES),
    )
