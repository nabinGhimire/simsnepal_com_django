import requests
import logging
from django.conf import settings
from .models import PlatformSetting, Group, UserRegistrationStatus
from django.utils import timezone

logger = logging.getLogger(__name__)

import os

def get_platform_setting(key, default=''):
    try:
        obj = PlatformSetting.objects.filter(key=key).first()
        if obj and obj.value:
            return obj.value
    except Exception:
        pass
    return default

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
    """Base URL for Hamro API – taken from settings, env or DB fallback."""
    if hasattr(settings, 'HAMRO_API_BASE_URL') and settings.HAMRO_API_BASE_URL:
        return settings.HAMRO_API_BASE_URL.rstrip('/')
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



def get_current_session():
    """Helper to get current session from threadlocal request or fallback."""
    from sms.models import EduSession
    from sms.middleware import get_current_request
    request = get_current_request()
    if request and hasattr(request, 'session') and request.session:
        active_session_id = request.session.get('active_session_id')
        if active_session_id:
            try:
                return EduSession.objects.get(id=active_session_id)
            except EduSession.DoesNotExist:
                pass
    try:
        return EduSession.objects.get(year=2083)
    except EduSession.DoesNotExist:
        return EduSession.objects.filter(status=True).order_by('-year').first()

def ensure_channel(name, school=None):
    """Create or retrieve a broadcast channel for the school.
    Returns the external_id of the channel.
    """
    session = get_current_session()
    
    # Query without session filtering, but with school if available
    if school:
        channel = Group.objects.filter(is_broadcast=True, school=school).first()
    else:
        channel = Group.objects.filter(is_broadcast=True, name=name).first()
        
    if channel:
        if channel.session != session:
            channel.session = session
            channel.save()
        if channel.name != name:
            if channel.external_id:
                update_thread(channel.external_id, name)
            channel.name = name
            channel.save()
        if channel.external_id:
            current_users = get_thread_users(channel.external_id)
            if current_users is None:
                channel.external_id = None
                channel.save()
            else:
                return channel.external_id

    external_id = create_thread('channel', name, f"School channel for {name}")
    if external_id:
        if channel:
            channel.external_id = external_id
            channel.save()
            return external_id
        else:
            Group.objects.create(
                name=name,
                is_broadcast=True,
                external_id=external_id,
                session=session,
                school=school,
            )
            return external_id
    else:
        logger.error(f'Failed to ensure channel {name}')
        return None

def ensure_group(name, session_id, grade=None, section=None, school=None):
    """Create or retrieve a group for a grade/section.
    Returns the Group instance (with external_id populated).
    """
    if not school:
        if section:
            school = section.grade.school
        elif grade:
            school = grade.school

    if grade is not None:
        group = Group.objects.filter(grade=grade, section=section, session_id=session_id, is_broadcast=False, school=school).first()
    else:
        group = Group.objects.filter(name=name, session_id=session_id, is_broadcast=False, school=school).first()

    if group:
        if group.name != name:
            if group.external_id:
                update_thread(group.external_id, name)
            group.name = name
            group.save()
        if group.external_id:
            current_users = get_thread_users(group.external_id)
            if current_users is None:
                group.external_id = None
                group.save()
            else:
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
                school=school,
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

def update_thread(thread_id, name, description=""):
    """Update an existing thread's name/description on Hamro platform."""
    url = f"{get_base_url()}/api/v1/platform/threads/{thread_id}"
    payload = {
        'name': name,
        'description': description
    }
    try:
        response = requests.put(url, json=payload, headers=get_headers())
        if response.status_code == 200:
            logger.info(f"Successfully updated thread {thread_id} name to '{name}' on platform.")
            return True
        else:
            logger.error(f"Failed to update thread {thread_id}: status={response.status_code}, response={response.text}")
    except Exception as e:
        logger.error(f"Error updating thread {thread_id}: {e}")
    return False

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

def chunk_list(lst, chunk_size):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

def lookup_hamro_users_batch(emails=None, phones=None):
    """Lookup multiple users on Hamro platform by lists of emails and phones.
    Returns a dictionary of {email_or_phone: user_id} on success.
    Raises requests.HTTPError or requests.RequestException on failure.
    """
    url = f"{get_base_url()}/api/v1/platform/users/lookup/batch"
    
    formatted_phones = []
    if phones:
        for p in phones:
            if p:
                formatted_phones.append(format_phone(p))
                
    emails = emails or []
    results = {}
    
    # Process in chunks of 50 to avoid payload limits
    email_chunks = list(chunk_list(emails, 50)) or [[]]
    phone_chunks = list(chunk_list(formatted_phones, 50)) or [[]]
    
    # Pad chunks to have same length for zip
    max_chunks = max(len(email_chunks), len(phone_chunks))
    while len(email_chunks) < max_chunks: email_chunks.append([])
    while len(phone_chunks) < max_chunks: phone_chunks.append([])
    
    for e_chunk, p_chunk in zip(email_chunks, phone_chunks):
        if not e_chunk and not p_chunk: continue
        payload = {
            'emails': e_chunk,
            'phones': p_chunk
        }
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
            raise requests.HTTPError(f"Batch user lookup failed: status={response.status_code}, response={response.text}")
    return results

def add_users_to_thread_batch(thread_id, user_ids):
    """Add multiple users to a thread in Hamro platform using batch endpoint."""
    url = f"{get_base_url()}/api/v1/platform/threads/{thread_id}/users/batch"
    user_ids = list(set(user_ids))
    last_response = None
    
    # Chunk the user_ids to avoid 413 errors
    for chunk in chunk_list(user_ids, 50):
        if not chunk: continue
        payload = {
            'user_ids': chunk
        }
        try:
            response = requests.post(url, json=payload, headers=get_headers())
            if response.status_code in (200, 201):
                last_response = response.json()
            else:
                logger.error(f"Failed to batch add users to thread {thread_id}: status={response.status_code}, response={response.text}")
        except Exception as e:
            logger.error(f"Error in batch adding users to thread: {e}")
            
    return last_response

def get_thread_participants(thread_id):
    """Fetch current participant details in a thread from Hamro platform.
    Returns list of dicts containing 'user_id' and 'admin' on success, or None if 404.
    Raises requests.HTTPError or requests.RequestException on failure.
    """
    url = f"{get_base_url()}/api/v1/platform/threads/{thread_id}/users"
    response = requests.get(url, headers=get_headers())
    if response.status_code == 200:
        users_list = response.json()
        return [{'user_id': u.get('user_id'), 'admin': u.get('admin', False)} for u in users_list if u.get('user_id')]
    elif response.status_code == 404:
        logger.warning(f"Thread {thread_id} not found on platform (404).")
        return None
    else:
        raise requests.HTTPError(f"Failed to fetch users for thread {thread_id}: status={response.status_code}, response={response.text}")

def get_thread_users(thread_id):
    """Fetch current user_ids in a thread from Hamro platform.
    Returns list of user_ids on success, or None if the thread does not exist (404).
    Raises requests.HTTPError or requests.RequestException on failure.
    """
    participants = get_thread_participants(thread_id)
    if participants is None:
        return None
    return [p['user_id'] for p in participants]

def update_user_role_in_thread(thread_id, user_id, role):
    """Update a user's role (admin or member) in a thread on Hamro platform."""
    url = f"{get_base_url()}/api/v1/platform/threads/{thread_id}/users/{user_id}/role"
    payload = {
        'role': role
    }
    try:
        response = requests.patch(url, json=payload, headers=get_headers())
        if response.status_code == 200:
            logger.info(f"Successfully updated role of user {user_id} to '{role}' in thread {thread_id}.")
            return True
        else:
            logger.error(f"Failed to update role of user {user_id} in thread {thread_id}: status={response.status_code}, response={response.text}")
    except Exception as e:
        logger.error(f"Error updating user role in thread: {e}")
    return False

def update_user_roles_batch(thread_id, admin_ids=None, member_ids=None):
    """Update roles of multiple users in bulk in a thread on Hamro platform."""
    url = f"{get_base_url()}/api/v1/platform/threads/{thread_id}/users/role/batch"
    payload = {}
    if admin_ids:
        payload['admin'] = list(admin_ids)
    if member_ids:
        payload['member'] = list(member_ids)
        
    if not payload:
        return True

    try:
        response = requests.post(url, json=payload, headers=get_headers())
        if response.status_code in (200, 201, 204):
            logger.info(f"Successfully batch updated roles in thread {thread_id}.")
            return True
        else:
            logger.error(f"Failed to batch update roles in thread {thread_id}: status={response.status_code}, response={response.text}")
    except Exception as e:
        logger.error(f"Error batch updating roles in thread {thread_id}: {e}")
    return False
