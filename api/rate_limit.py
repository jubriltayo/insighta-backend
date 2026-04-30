from django.core.cache import cache
from django.http import JsonResponse


class RateLimitMiddleware:
    """
    - /auth/* -> 10 req/min (keyed by IP)
    - all others -> 60 req/min per authenticated user (or IP if anonymous)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "auth_user", None)

        if request.path.startswith("/auth/"):
            limit = 10
            key = f"rl:auth:{self._get_ip(request)}"
        else:
            limit = 60
            identifier = str(user.id) if user else self._get_ip(request)
            key = f"rl:user:{identifier}:{request.path}"

        count = cache.get(key, 0)

        if count >= limit:
            return JsonResponse(
                {"status": "error", "message": "Too many requests"}, status=429
            )

        cache.set(key, count + 1, timeout=60)

        response = self.get_response(request)
        return response

    def _get_ip(self, request):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
