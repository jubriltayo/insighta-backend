from functools import wraps
from rest_framework.response import Response


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        user = request.auth_user

        if user.role != "admin":
            return Response({"status": "error", "message": "Forbidden"}, status=403)

        return view_func(self, request, *args, **kwargs)

    return wrapper
