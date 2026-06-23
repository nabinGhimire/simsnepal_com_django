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
        
    external_id = create_thread('group', name, f"Group for {name}")
    if external_id:
        if group:
            # Group exists but no external_id, update it
            group.external_id = external_id
            group.save()
            return group
        else:
            group = Group.objects.create(
                name=name,
                session_id=session_id,
                grade=grade,
                section=section,
                external_id=external_id,
                is_broadcast=False,
            )
            return group
    else:
        logger.error(f'Failed to ensure group {name}')
        return None

def add_user_to_group(user_external_id, group_external_id):
    """Add a user to a Hamro group.
    Returns True on success.
    """
    return add_user_to_thread(group_external_id, user_external_id)

def remove_user_from_group(user_external_id, group_external_id):
    """Remove a user from a Hamro group.
    Returns True on success.
    """
    return remove_user_from_thread(group_external_id, user_external_id)

def format_phone(phone):
    if not phone:
        return phone
    phone = str(phone).strip()
    if phone.startswith('+'):
        phone = phone[1:]
    if len(phone) == 10:
        phone = '977' + phone
    return '+' + phone

def user_exists_in_hamro(email=None, phone=None):
    """Check if a user exists on Hamro by email or phone.
    Returns the external_id if found, else None.
    """
    return lookup_hamro_user(email=email, phone=phone)

def create_thread(thread_type, name, description=""):
    """Create a new thread (group or channel) in Hamro platform."""
    url = f"{get_base_url()}/api/v1/platform/threads"
    payload = {
        'type': thread_type,
        'name': name,
        'description': description
    }
    try:
        response = requests.post(url, json=payload, headers=get_headers())
        if response.status_code in (200, 201):
            data = response.json()
            return data.get('id')
        else:
            logger.error(f"Failed to create thread {name}: status={response.status_code}, response={response.text}")
    except Exception as e:
        logger.error(f"Error creating thread {name}: {e}")
    return None

def add_user_to_thread(thread_id, user_id):
    """Add a user to a thread in Hamro platform."""
    url = f"{get_base_url()}/api/v1/platform/threads/{thread_id}/users"
    payload = {
        'user_id': user_id
    }
    try:
        response = requests.post(url, json=payload, headers=get_headers())
        if response.status_code in (200, 201):
            return True
        else:
            logger.error(f"Failed to add user {user_id} to thread {thread_id}: status={response.status_code}, response={response.text}")
    except Exception as e:
        logger.error(f"Error adding user to thread: {e}")
    return False

def remove_user_from_thread(thread_id, user_id):
    """Remove a user from a thread in Hamro platform."""
    url = f"{get_base_url()}/api/v1/platform/threads/{thread_id}/users"
    payload = {
        'user_id': user_id
    }
    try:
        response = requests.delete(url, json=payload, headers=get_headers())
        if response.status_code in (200, 204, 202):
            return True
        else:
            logger.error(f"Failed to remove user {user_id} from thread {thread_id}: status={response.status_code}, response={response.text}")
    except Exception as e:
        logger.error(f"Error removing user from thread: {e}")
    return False

def send_message_to_thread(thread_id, body):
    """Send a message to a thread in Hamro platform."""
    url = f"{get_base_url()}/api/v1/platform/threads/{thread_id}/messages"
    payload = {
        'body': body,
        'type': 'text'
    }
    try:
        response = requests.post(url, json=payload, headers=get_headers())
        if response.status_code in (200, 201):
            data = response.json()
            return data.get('id') or "success"
        else:
            logger.error(f"Failed to send message to thread {thread_id}: status={response.status_code}, response={response.text}")
    except Exception as e:
        logger.error(f"Error sending message to thread: {e}")
    return None

def lookup_hamro_user(email=None, phone=None):
    """Lookup a user on Hamro platform by email or phone.
    Returns external user ID if found, else None.
    """
    url = f"{get_base_url()}/api/v1/platform/users/lookup"
    params = {}
    if phone:
        phone = format_phone(phone)
    if email:
        params['email'] = email
    elif phone:
        params['phone'] = phone
    else:
        return None
    try:
        response = requests.get(url, params=params, headers=get_headers())
        if response.status_code == 200:
            data = response.json()
            if data.get('exists') and data.get('user'):
                return data['user'].get('id')
        else:
            logger.error(f"User lookup failed: status={response.status_code}, response={response.text}")
    except Exception as e:
        logger.error(f"Error looking up user (email={email}, phone={phone}): {e}")
    return None

def lookup_hamro_users_batch(emails=None, phones=None):
    """Lookup multiple users on Hamro platform by lists of emails and phones.
    Returns a dictionary of {email_or_phone: user_id}.
    """
    url = f"{get_base_url()}/api/v1/platform/users/lookup/batch"
    
    formatted_phones = []
    if phones:
        for p in phones:
            if p:
                formatted_phones.append(format_phone(p))
                
    payload = {
        'emails': emails or [],
        'phones': formatted_phones
    }
    results = {}
    try:
        response = requests.post(url, json=payload, headers=get_headers())
        if response.status_code == 200:
            data = response.json()
            users_list = data.get('users', [])
            for u in users_list:
                u_id = u.get('id')
                if u_id:
                    if u.get('email'):
                        results[u['email']] = u_id
                    if u.get('phone'):
                        results[str(u['phone'])] = u_id
        else:
            logger.error(f"Batch user lookup failed: status={response.status_code}, response={response.text}")
    except Exception as e:
        logger.error(f"Error in batch user lookup: {e}")
    return results

def add_users_to_thread_batch(thread_id, user_ids):
    """Add multiple users to a thread in Hamro platform using batch endpoint."""
    url = f"{get_base_url()}/api/v1/platform/threads/{thread_id}/users/batch"
    payload = {
        'user_ids': list(set(user_ids))
    }
    try:
        response = requests.post(url, json=payload, headers=get_headers())
        if response.status_code in (200, 201):
            return response.json()
        else:
            logger.error(f"Failed to batch add users to thread {thread_id}: status={response.status_code}, response={response.text}")
    except Exception as e:
        logger.error(f"Error in batch adding users to thread: {e}")
    return None


