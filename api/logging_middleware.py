import time


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.time()

        response = self.get_response(request)

        duration = (time.time() - start) * 1000

        print(
            f"{request.method} {request.path} {response.status_code} {duration:.2f}ms"
        )

        return response
