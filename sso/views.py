from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth import login, get_user_model
from django.contrib.auth.decorators import login_required
import requests
from django.conf import settings


@login_required
def dashboard(request):
    """Simple dashboard page for logged‑in users."""
    return render(request, 'sso/dashboard.html')


def auto_login(request):
    """Validate `auth_token` from business.hamro.com and log the user in.

    Expected query string: ``?auth_token=xxxx``
    The view calls the validation endpoint:
        https://business.hamro.com/api/v1/sso/validate/?token={auth_token}
    If the token is valid, the user data from the response is used to
    ``get_or_create`` a Django ``User`` and the user is logged in.
    On success we redirect to ``/`` (or any landing page you prefer).
    """
    token = request.GET.get('auth_token')
    if not token:
        return HttpResponseBadRequest('auth_token missing')

    # Call the validation endpoint (adjust URL if needed for local dev)
    validate_url = settings.BUSINESS_SITE
    try:
        resp = requests.get(validate_url, params={'token': token}, timeout=5)
        print(resp)
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
    # Identify the user uniquely – using the ``hamro_uuid`` if present, otherwise fallback to email
    identifier = user_info.get('hamro_uuid') or user_info.get('email')
    username = user_info.get('username') or identifier
    
    defaults = {
        'email': user_info.get('email', ''),
        'first_name': user_info.get('first_name', ''),
        'last_name': user_info.get('last_name', ''),
        'is_staff': user_info.get('is_staff', False),
    }
    user, _ = User.objects.get_or_create(username=username, defaults=defaults)
    # Update fields in case they changed on the IdP
    for attr, val in defaults.items():
        setattr(user, attr, val)
    user.save()
    login(request, user)
    # Redirect to a landing page – you may change this as needed
    return redirect('/')

