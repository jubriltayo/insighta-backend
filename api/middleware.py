from django.http import JsonResponse


class APIVersionMiddleware:
    """
    Enforces X-API-Version: 1 on all /api/* endpoints
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/"):
            version = request.headers.get("X-API-Version")

            if not version:
                return JsonResponse(
                    {"status": "error", "message": "API version header required"},
                    status=400,
                )

            if version != "1":
                return JsonResponse(
                    {"status": "error", "message": "Invalid API version"}, status=400
                )

        response = self.get_response(request)
        return response
