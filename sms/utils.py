from django.core.exceptions import ObjectDoesNotExist
from sms.middleware import get_current_request
from django.apps import apps

def get_current_school():
    """Return the :class:`SchoolBranch` associated with the logged‑in user.

    The SSO middleware stores the business identifier in ``request.session['sso_business']['id']``.
    If the session or the identifier is missing, ``None`` is returned.
    """
    request = get_current_request()
    if not request or not hasattr(request, "session"):
        return None
    sso_business = request.session.get("sso_business", {})
    school_id = sso_business.get("id")
    if not school_id:
        return None
    # Lazily get the SchoolBranch model to avoid circular imports
    SchoolBranch = apps.get_model('sms', 'SchoolBranch')
    try:
        return SchoolBranch.objects.get(shortcode=school_id)
    except ObjectDoesNotExist:
        return None
