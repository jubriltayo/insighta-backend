from django.utils.deprecation import MiddlewareMixin

from .tokens import decode_access_token
from .models import User


class AuthMiddleware(MiddlewareMixin):
    """
    Attaches authenticated user to request.auth_user
    Supports:
    - Authorization: Bearer <token> (CLI)
    - access_token cookie (web)
    """

    def process_request(self, request):
        request.auth_user = None

        token = None

        # Check Authorization header first (CLI)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        # If no token in header, check cookie (web) as fallback
        if not token:
            token = request.COOKIES.get("access_token")

        try:
            payload = decode_access_token(token)
            user_id = payload.get("user_id")

            user = User.objects.filter(id=user_id).first()
            if user:
                request.auth_user = user

        except Exception:
            # Invalid / expired token - ignore silently
            return
