import threading

_thread_locals = threading.local()

def get_current_request():
    """Retrieve the current HTTP request object from the thread-local storage."""
    return getattr(_thread_locals, 'request', None)

class ThreadLocalRequestMiddleware:
    """Middleware that stores the current HTTP request in thread-local storage."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.request = request
        try:
            response = self.get_response(request)
        finally:
            if hasattr(_thread_locals, 'request'):
                del _thread_locals.request
        return response
