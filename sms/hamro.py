import requests
import logging
from django.conf import settings
from .models import PlatformSetting, Group, UserRegistrationStatus
from django.utils import timezone

logger = logging.getLogger(__name__)

import os

def get_platform_key():
    """Return the platform key from env variable or DB fallback."""
    env_key = os.getenv('SIMS_HAMRO_PLATFORM_KEY')
    if env_key:
        return env_key
    return get_platform_setting('PLATFORM_KEY', default='')

def get_business_key():
    """Fetch the business key stored in PlatformSetting (key='BUSINESS_KEY')."""
    try:
        return PlatformSetting.objects.get(key='BUSINESS_KEY').value
    except PlatformSetting.DoesNotExist:
        return None

def get_base_url():
    """Base URL for Hamro API – taken from env or DB fallback."""
    env_url = os.getenv('HAMRO_API_BASE_URL')
    if env_url:
        return env_url.rstrip('/')
    return get_platform_setting('HAMRO_API_BASE_URL', default='https://api.chat-hamro.com/api/v1')

def get_headers():
    """Headers required for every Hamro request, pulling both keys."""
    platform_key = get_platform_key()
    business_key = get_business_key()
    headers = {
        'Content-Type': 'application/json',
    }
    if platform_key:
        headers['X-Platform-Key'] = platform_key
    if business_key:
        headers['X-Business-Key'] = business_key
    return headers



def ensure_channel(name):
    """Create or retrieve a broadcast channel for the school.
    Returns the external_id of the channel.
    """
    channel = Group.objects.filter(name=name, is_broadcast=True).first()
    if channel and channel.external_id:
        return channel.external_id
    url = f"{get_base_url()}/channels/"
    payload = {'name': name}
    try:
        response = requests.post(url, json=payload, headers=get_headers())
        response.raise_for_status()
        data = response.json()
        external_id = data.get('id')
        Group.objects.create(
            name=name,
            is_broadcast=True,
            external_id=external_id,
            session=None,
        )
        return external_id
    except Exception as e:
        logger.error(f'Failed to ensure channel {name}: {e}')
        return None

def ensure_group(name, session_id, grade=None, section=None):
    """Create or retrieve a group for a grade/section.
    Returns the Group instance (with external_id populated).
    """
    group = Group.objects.filter(name=name, session_id=session_id).first()
    if group and group.external_id:
        return group
    url = f"{get_base_url()}/groups/"
    payload = {
        'name': name,
        'session_id': session_id,
    }
    if grade:
        payload['grade_id'] = grade.id
    if section:
        payload['section_id'] = section.id
    try:
        response = requests.post(url, json=payload, headers=get_headers())
        response.raise_for_status()
        data = response.json()
        external_id = data.get('id')
        group = Group.objects.create(
            name=name,
            session_id=session_id,
            grade=grade,
            section=section,
            external_id=external_id,
            is_broadcast=False,
        )
        return group
    except Exception as e:
        logger.error(f'Failed to ensure group {name}: {e}')
        return None

def add_user_to_group(user_external_id, group_external_id):
    """Add a user to a Hamro group.
    Returns True on success.
    """
    url = f"{get_base_url()}/groups/{group_external_id}/members/"
    payload = {'user_id': user_external_id}
    try:
        response = requests.post(url, json=payload, headers=get_headers())
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f'Failed to add user {user_external_id} to group {group_external_id}: {e}')
        return False

def remove_user_from_group(user_external_id, group_external_id):
    """Remove a user from a Hamro group.
    Returns True on success.
    """
    url = f"{get_base_url()}/groups/{group_external_id}/members/{user_external_id}/"
    try:
        response = requests.delete(url, headers=get_headers())
        if response.status_code in (200, 204, 202):
            return True
        response.raise_for_status()
        return False
    except Exception as e:
        logger.error(f'Failed to remove user {user_external_id} from group {group_external_id}: {e}')
        return False

def user_exists_in_hamro(email=None, phone=None):
    """Check if a user exists on Hamro by email or phone.
    If not, create and return the new external_id.
    """
    base = get_base_url()
    if email:
        lookup_url = f"{base}/users?email={email}"
    elif phone:
        lookup_url = f"{base}/users?phone={phone}"
    else:
        return None
    try:
        resp = requests.get(lookup_url, headers=get_headers())
        resp.raise_for_status()
        data = resp.json()
        if data and isinstance(data, list) and len(data) > 0:
            return data[0].get('id')
        # Not found – create
        create_url = f"{base}/users/"
        payload = {}
        if email:
            payload['email'] = email
        if phone:
            payload['phone'] = phone
        create_resp = requests.post(create_url, json=payload, headers=get_headers())
        create_resp.raise_for_status()
        created = create_resp.json()
        return created.get('id')
    except Exception as e:
        logger.error(f'Failed to lookup/create Hamro user (email={email}, phone={phone}): {e}')
        return None
