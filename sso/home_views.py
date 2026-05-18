from django.shortcuts import render, redirect
from django.http import HttpResponseBadRequest
from django.contrib.auth import login, get_user_model
from django.contrib.auth.decorators import login_required
import requests

# Base URL of the IdP (adjust for dev if needed)
BUSINESS_IDP_URL = 'https://business.hamro.com'

def _validate_and_login(request, token):
    """Internal helper: validate token with IdP, create/update user, log in.
    Returns a HttpResponse (redirect) on success or HttpResponseBadRequest on failure.
    """
    if not token:
        return HttpResponseBadRequest('auth_token missing')
    validate_url = f"{BUSINESS_IDP_URL}/api/v1/sso/validate/"
    try:
        resp = requests.get(validate_url, params={'token': token}, timeout=5)
    except requests.RequestException as e:
        return HttpResponseBadRequest(f'Validation request failed: {e}')
    if resp.status_code != 200:
        return HttpResponseBadRequest('Invalid response from SSO service')
    data = resp.json()
    if not data.get('valid'):
        return HttpResponseBadRequest('Token validation failed')
    user_info = data.get('user')
    if not user_info:
        return HttpResponseBadRequest('No user info returned')
    User = get_user_model()
    identifier = user_info.get('hamro_uuid') or user_info.get('email')
    defaults = {
        'username': user_info.get('username') or identifier,
        'email': user_info.get('email', ''),
        'first_name': user_info.get('first_name', ''),
        'last_name': user_info.get('last_name', ''),
        'is_staff': user_info.get('is_staff', False),
    }
    user, _ = User.objects.get_or_create(username=identifier, defaults=defaults)
    for attr, val in defaults.items():
        setattr(user, attr, val)
    user.save()
    login(request, user)
    # After login, send the user to the dashboard
    return redirect('dashboard')

def sso_home(request):
    """Root view for the SSO app.
    - If `auth_token` is present, validate it and log the user in.
    - Otherwise render a landing page that shows different content for
      authenticated vs unauthenticated users.
    """
    token = request.GET.get('auth_token')
    if token:
        # Token flow – validate and log in, then redirect to dashboard
        return _validate_and_login(request, token)
    # Normal landing page
    return render(request, 'sso/home.html')

@login_required
def dashboard(request):
    """Simple dashboard page for logged‑in users."""
    return render(request, 'sso/dashboard.html')
