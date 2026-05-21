from django.http import HttpResponse
from django.shortcuts import redirect
from . import settings

# Import the auto_login view from the sso app
from sso.views import auto_login


def home(request):
    """Root view for the project.

    If an ``auth_token`` query parameter is present, delegate to the ``sso.auto_login``
    view which validates the token and logs the user in. Otherwise, show a simple
    welcome page.
    """
    token = request.GET.get('auth_token')
    if token:
        # Re‑use the existing auto_login logic – it reads the same query param.
        return auto_login(request)
    return HttpResponse('<h1>Welcome to SIMS Nepal</h1>')
