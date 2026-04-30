from django.http import JsonResponse
from django.views import View
from rest_framework.views import APIView


class AuthenticatedAPIView(APIView):
    """
    For JSON endpoints
    Enforces:
    - Authentication required
    - Active user only
    """

    def dispatch(self, request, *args, **kwargs):
        user = getattr(request, "auth_user", None)

        if not user:
            return JsonResponse(
                {"status": "error", "message": "Authentication required"}, status=401
            )

        if not user.is_active:
            return JsonResponse(
                {"status": "error", "message": "Account is inactive"}, status=403
            )

        return super().dispatch(request, *args, **kwargs)


class AuthenticatedView(View):
    """
    Use this for views that return non-JSON responses (e.g. CSV downloads).
    Plain Django View with auth enforcement.
    Enforces:
    - Authentication required
    - Active user only
    """

    def dispatch(self, request, *args, **kwargs):
        user = getattr(request, "auth_user", None)

        if not user:
            return JsonResponse(
                {"status": "error", "message": "Authentication required"}, status=401
            )

        if not user.is_active:
            return JsonResponse(
                {"status": "error", "message": "Account is inactive"}, status=403
            )

        return super().dispatch(request, *args, **kwargs)
