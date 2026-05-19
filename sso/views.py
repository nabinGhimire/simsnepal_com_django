from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth import login, get_user_model, logout as django_logout
from django.contrib.auth.decorators import login_required
import requests
from django.conf import settings


@login_required
def dashboard(request):
    """Simple dashboard page for logged‑in users."""
    sso_user = request.session.get('sso_user', {})
    sso_business = request.session.get('sso_business', {})
    
    # Fallback to local user model fields if session data doesn't exist
    user = request.user
    context = {
        'user': user,
        'sso_user': sso_user or {
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': f"{user.first_name} {user.last_name}".strip() or user.username,
            'phone': 'N/A',
            'avatar': None,
            'email_verified': False,
        },
        'sso_business': sso_business or {
            'id': 'N/A',
            'name': 'Hamro School/Business',
            'module': 'students',
        }
    }
    return render(request, 'sso/dashboard.html', context)


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
    
    # Store SSO details in session
    request.session['sso_user'] = user_info
    
    business_info = data.get('business') or {}
    business_name = business_info.get('name') or data.get('business_name')
    business_id = business_info.get('id') or data.get('business_id')
    
    request.session['sso_business'] = {
        'id': business_id,
        'name': business_name or 'Hamro School/Business',
        'module': data.get('module', 'students'),
    }
    
    login(request, user)
    # Redirect to dashboard landing page
    return redirect('dashboard')


def logout_user(request):
    """Log the user out locally and redirect to the public home page."""
    django_logout(request)
    return redirect('home')



