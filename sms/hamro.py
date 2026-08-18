import requests
import logging
import time
from django.conf import settings
from .models import PlatformSetting, Group, GroupMembershipCache, UserRegistrationStatus
from django.utils import timezone

logger = logging.getLogger(__name__)

import os

def _request_with_retry(method, url, max_retries=3, backoff=1.0, **kwargs):
    """
    Make an HTTP request with exponential backoff retry for transient errors.
    Retries on connection errors, timeouts, and 5xx status codes.

    Args:
        method (str): HTTP verb ('get', 'post', 'put', 'delete', ...)
        url (str): Request URL
        max_retries (int): Maximum number of retry attempts
        backoff (float): Initial backoff factor (sleep = backoff * 2^attempt)
        **kwargs: Additional arguments passed to requests (headers, json, timeout, etc.)

    Returns:
        requests.Response: Successful response (status < 500)

    Raises:
        requests.HTTPError: On persistent server errors
        requests.RequestException: On persistent network errors
    """
    kwargs.setdefault('timeout', 15)  # Reasonable default timeout

    last_exc = None

    for attempt in range(max_retries):
        try:
            # Log the attempt for debugging
            logger.debug(f"Sending {method.upper()} request to {url} (attempt {attempt+1}/{max_retries})")

            # Use explicit method calls for clarity and safety
            method_lower = method.lower()
            if method_lower == 'get':
                response = requests.get(url, **kwargs)
            elif method_lower == 'post':
                response = requests.post(url, **kwargs)
            elif method_lower == 'put':
                response = requests.put(url, **kwargs)
            elif method_lower == 'delete':
                response = requests.delete(url, **kwargs)
            else:
                # Fallback to dynamic dispatch for any other verb (e.g., 'patch')
                response = getattr(requests, method_lower)(url, **kwargs)

            # Log if a redirect happened – this is the most common reason POST becomes GET
            if response.history:
                for resp in response.history:
                    if resp.status_code in (301, 302, 303) and method_lower != 'get':
                        logger.warning(
                            f"Redirect {resp.status_code} from {method.upper()} to GET "
                            f"(final URL: {response.url}). Server may not accept POST."
                        )
                # Optionally, you could raise an exception to stop the request
                # raise requests.HTTPError(f"Unexpected redirect from POST to GET", response=response)

            # Success: any status < 500 is returned to the caller (including 4xx)
            if response.status_code < 500:
                return response

            # Server error (5xx) → log and retry
            logger.warning(
                f"Server error {response.status_code} on {method.upper()} {url} "
                f"(attempt {attempt+1}/{max_retries})"
            )
            last_exc = requests.HTTPError(
                f"Server error: {response.status_code}", response=response
            )

        except (requests.ConnectionError, requests.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            # Network‑level transient errors → retry
            logger.warning(
                f"Transient error on {method.upper()} {url} "
                f"(attempt {attempt+1}/{max_retries}): {e}"
            )
            last_exc = e

        # Exponential backoff before next retry (skip after last attempt)
        if attempt < max_retries - 1:
            sleep_time = backoff * (2 ** attempt)
            time.sleep(sleep_time)

    # All retries exhausted – raise the last captured exception
    raise last_exc
"""
def _request_with_retry(method, url, max_retries=3, backoff=1.0, **kwargs):
    ""Make an HTTP request with exponential backoff retry for transient errors.
    Retries on connection errors, timeouts, and 5xx status codes.
    Returns the response on success, raises on persistent failure.
    ""
    kwargs.setdefault('timeout', 15)
    last_exc = None
    for attempt in range(max_retries):
        try:
            # response = getattr(requests, method)(url, **kwargs)
            if method == 'get':
                response = requests.get(url, **kwargs)
            elif method == 'post':
            response = requests.post(url, **kwargs)
            if response.status_code < 500:
                return response  # 2xx, 3xx, 4xx — caller handles
            logger.warning(f"Server error {response.status_code} on {method} {url} (attempt {attempt + 1}/{max_retries})")
            last_exc = requests.HTTPError(f"Server error: {response.status_code}", response=response)
        except (requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError) as e:
            logger.warning(f"Transient error on {method} {url} (attempt {attempt + 1}/{max_retries}): {e}")
            last_exc = e
        if attempt < max_retries - 1:
            time.sleep(backoff * (2 ** attempt))
    raise last_exc

"""

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

def get_business_key(school=None):
    """Fetch the per-school business key from SchoolBranch.business_key.
    Returns None if the school has no key configured — admin must set it up first.
    """
    if school and hasattr(school, 'business_key') and school.business_key:
        return school.business_key
    return None

def get_base_url():
    """Base URL for Hamro Platform API – taken from settings, env or DB fallback."""
    if hasattr(settings, 'HAMRO_API_BASE_URL') and settings.HAMRO_API_BASE_URL:
        return settings.HAMRO_API_BASE_URL.rstrip('/')
    env_url = os.getenv('HAMRO_API_BASE_URL')
    if env_url:
        return env_url.rstrip('/')
    return get_platform_setting('HAMRO_API_BASE_URL', default='https://messengerin.hamro.com')

def get_system_base_url():
    """Base URL for Hamro System API (business sync, key creation).
    System endpoints run on messengerin.hamro.com, separate from the platform API.
    """
    env_url = os.getenv('HAMRO_SYSTEM_BASE_URL')
    if env_url:
        return env_url.rstrip('/')
    return 'https://messengerin.hamro.com'

def get_headers(school=None):
    """Headers required for every Hamro request, pulling both keys."""
    platform_key = get_platform_key()
    business_key = get_business_key(school=school)
    headers = {
        'Content-Type': 'application/json',
    }
    if platform_key:
        headers['X-Platform-Key'] = platform_key
    if business_key:
        headers['X-Business-Key'] = business_key
    return headers

def get_system_headers():
    """Headers required for System API requests."""
    api_key = getattr(settings, 'HAMRO_SYSTEM_API_KEY', None)
    return {
        'X-System-API-Key': api_key,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

def sync_hamro_business(user_id, name, business_type, existing_id=None):
    """Sync/Register a business on Hamro. Returns the business ID."""
    url = f"{get_system_base_url()}/system/businesses/sync"
    payload = {
        'user_id': str(user_id),
        'name': name,
        'type': business_type,
        'is_active': True
    }
    if existing_id:
        payload['id'] = str(existing_id)
        
    try:
        response = requests.post(url, json=payload, headers=get_system_headers(), timeout=10)
        if response.status_code == 200:
            data = response.json()
            business = data.get('business', {})
            return business.get('id')
        else:
            logger.error(f"Failed to sync business '{name}': {response.status_code} {response.text}")
    except Exception as e:
        logger.error(f"Error syncing business '{name}': {e}")
    return None

def create_delegated_api_key(company_id, platform_id, name, service_name):
    """Create a delegated API key for a company. Returns the new API key string."""
    url = f"{get_system_base_url()}/system/businesses/{company_id}/api-keys/delegated"
    payload = {
        'platform_business_id': str(platform_id),
        'name': name,
        'service_name': service_name
    }
    try:
        response = requests.post(url, json=payload, headers=get_system_headers(), timeout=10)
        if response.status_code == 201:
            data = response.json()
            return data.get('key')
        else:
            logger.error(f"Failed to create delegated key for company {company_id}: {response.status_code} {response.text}")
    except Exception as e:
        logger.error(f"Error creating delegated key: {e}")
    return None


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
    
    # Query by group_type if school provided, else fallback to name
    if school:
        channel = Group.objects.filter(group_type='school', school=school, session=session).first()
    else:
        channel = Group.objects.filter(name__iexact=name).first()
        
    if channel:
        if channel.session != session:
            channel.session = session
            channel.save()
        if channel.name != name:
            if channel.external_id:
                update_thread(channel.external_id, name, school=school)
            channel.name = name
            channel.save()
        if channel.external_id:
            # Use thread_exists (safe) instead of get_thread_users (destructive).
            # Only destroy the reference on confirmed 404, not on transient errors.
            exists = thread_exists(channel.external_id, school=school)
            if exists is False:
                logger.warning(f"Channel {name} (thread {channel.external_id}) confirmed deleted on platform. Recreating.")
                channel.external_id = None
                channel.save()
                GroupMembershipCache.objects.filter(group=channel).delete()
            else:
                # exists is True or None (transient error) — trust the DB record
                return channel.external_id

    external_id = create_thread('channel', name, f"School channel for {name}", school=school)
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
        group = Group.objects.filter(grade=grade, section=section, session_id=session_id, group_type='class', school=school).first()
    else:
        group = Group.objects.filter(group_type='teachers', session_id=session_id, school=school).first()

    if group:
        if group.name != name:
            if group.external_id:
                update_thread(group.external_id, name, school=school)
            group.name = name
            group.save()
        if group.external_id:
            # Use thread_exists (safe) instead of get_thread_users (destructive).
            # Only destroy the reference on confirmed 404, not on transient errors.
            exists = thread_exists(group.external_id, school=school)
            if exists is False:
                logger.warning(f"Group {name} (thread {group.external_id}) confirmed deleted on platform. Recreating.")
                group.external_id = None
                group.save()
                GroupMembershipCache.objects.filter(group=group).delete()
            else:
                # exists is True or None (transient error) — trust the DB record
                return group
        
    external_id = create_thread('group', name, f"Group for {name}", school=school)
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

def add_user_to_group(user_external_id, group_external_id, school=None):
    """Add a user to a Hamro group.
    Returns True on success.
    """
    return add_user_to_thread(group_external_id, user_external_id, school=school)

def remove_user_from_group(user_external_id, group_external_id, school=None):
    """Remove a user from a Hamro group.
    Returns True on success.
    """
    return remove_user_from_thread(group_external_id, user_external_id, school=school)

def format_phone(phone):
    if not phone:
        return phone
    phone = str(phone).strip()
    if phone.startswith('+'):
        phone = phone[1:]
    if len(phone) == 10:
        phone = '977' + phone
    return '+' + phone

def user_exists_in_hamro(email=None, phone=None, school=None):
    """Check if a user exists on Hamro by email or phone.
    Returns the external_id if found, else None.
    """
    return lookup_hamro_user(email=email, phone=phone, school=school)

def list_threads(school=None):
    """List all threads owned by this platform on Hamro.
    Returns a list of dicts with 'id', 'name', 'type' keys, or None on error.
    """
    url = f"{get_base_url()}/api/v1/platform/threads"
    try:
        response = _request_with_retry('get', url, headers=get_headers(school=school), max_retries=2, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get('results', data.get('threads', data.get('data', [])))
        else:
            logger.error(f"Failed to list threads: status={response.status_code}, response={response.text}")
    except Exception as e:
        logger.error(f"Error listing threads: {e}")
    return None

def create_thread(thread_type, name, description="", school=None):
    """Create a new thread (group or channel) in Hamro platform."""
    url = f"{get_base_url()}/api/v1/platform/threads"
    payload = {
        'type': thread_type,
        'name': name,
        'description': description
    }
    try:
        response = requests.post(url, json=payload, headers=get_headers(school=school))
        if response.status_code in (200, 201):
            data = response.json()
            return data.get('id')
        else:
            logger.error(f"Failed to create thread {name}: status={response.status_code}, response={response.text}")
    except Exception as e:
        logger.error(f"Error creating thread {name}: {e}")
    return None

def update_thread(thread_id, name, description="", is_channel=None, school=None):
    """Update an existing thread's name/description/is_channel on Hamro platform.
    If is_channel is provided (bool), the thread type will be changed in-place.
    """
    url = f"{get_base_url()}/api/v1/platform/threads/{thread_id}"
    payload = {
        'name': name,
        'description': description
    }
    if is_channel is not None:
        payload['is_channel'] = is_channel
    try:
        response = requests.put(url, json=payload, headers=get_headers(school=school))
        if response.status_code == 200:
            logger.info(f"Successfully updated thread {thread_id} name to '{name}' on platform.")
            return True
        else:
            logger.error(f"Failed to update thread {thread_id}: status={response.status_code}, response={response.text}")
    except Exception as e:
        logger.error(f"Error updating thread {thread_id}: {e}")
    return False

def thread_exists(thread_id, school=None):
    """Check if a thread exists on Hamro by making a lightweight GET request.
    Returns True if the thread exists (200), False if not (404).
    Returns None on transient errors (network, 5xx, etc.) — caller should NOT treat as deleted.
    """
    url = f"{get_base_url()}/api/v1/platform/threads/{thread_id}"
    try:
        response = _request_with_retry('get', url, headers=get_headers(school=school), max_retries=2, timeout=10)
        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            return False
        else:
            logger.warning(f"Unexpected status checking thread {thread_id}: {response.status_code}")
            return None
    except Exception as e:
        logger.warning(f"Transient error checking thread {thread_id}: {e}")
        return None

def delete_thread(thread_id, school=None):
    """Delete a thread on Hamro platform."""
    url = f"{get_base_url()}/api/v1/platform/threads/{thread_id}"
    try:
        response = _request_with_retry('delete', url, headers=get_headers(school=school), timeout=10)
        if response.status_code in (200, 204, 202):
            return True
        else:
            logger.error(f"Failed to delete thread {thread_id}: status={response.status_code}, response={response.text}")
    except Exception as e:
        logger.error(f"Error deleting thread {thread_id}: {e}")
    return False

def add_user_to_thread(thread_id, user_id, school=None):
    """Add a user to a thread in Hamro platform."""
    url = f"{get_base_url()}/api/v1/platform/threads/{thread_id}/users"
    payload = {
        'user_id': user_id
    }
    try:
        response = requests.post(url, json=payload, headers=get_headers(school=school))
        if response.status_code in (200, 201):
            return True
        else:
            logger.error(f"Failed to add user {user_id} to thread {thread_id}: status={response.status_code}, response={response.text}")
    except Exception as e:
        logger.error(f"Error adding user to thread: {e}")
    return False

def remove_user_from_thread(thread_id, user_id, school=None):
    """Remove a user from a thread in Hamro platform using DELETE /platform/threads/{id}/users."""
    url = f"{get_base_url()}/api/v1/platform/threads/{thread_id}/users"
    payload = {
        'user_id': str(user_id)
    }
    try:
        response = _request_with_retry('delete', url, json=payload, headers=get_headers(school=school), timeout=15)
        if response.status_code in (200, 204, 202):
            logger.info(f"Successfully removed user {user_id} from thread {thread_id}.")
            return True
        elif response.status_code == 403 and "business owner" in response.text.lower():
            logger.debug(f"User {user_id} is business owner; cannot remove from thread {thread_id}.")
            return False
        elif response.status_code == 404:
            # Already not in thread
            return True
        else:
            logger.error(f"Failed to remove user {user_id} from thread {thread_id}: status={response.status_code}, response={response.text}")
    except Exception as e:
        logger.error(f"Error removing user from thread: {e}")
    return False

def remove_users_from_thread_batch(thread_id, user_ids, school=None):
    """Remove multiple users from a thread using individual DELETE requests.
    Returns the set of user_ids that were successfully removed.
    """
    user_ids = list(set(user_ids))
    removed = set()
    owner_id = None
    
    # Exclude business owner from removal attempts
    try:
        if school and hasattr(school, 'owner') and school.owner:
            owner_id = school.owner.user.username
    except Exception:
        pass

    for uid in user_ids:
        if owner_id and str(uid) == str(owner_id):
            continue
        if remove_user_from_thread(thread_id, uid, school=school):
            removed.add(uid)

    return removed

def send_message_to_thread(thread_id, body, school=None):
    """Send a message to a thread in Hamro platform."""
    url = f"{get_base_url()}/api/v1/platform/threads/{thread_id}/messages"
    payload = {
        'body': body,
        'type': 'text'
    }
    try:
        response = requests.post(url, json=payload, headers=get_headers(school=school))
        if response.status_code in (200, 201):
            data = response.json()
            return data.get('id') or "success"
        else:
            logger.error(f"Failed to send message to thread {thread_id}: status={response.status_code}, response={response.text}")
    except Exception as e:
        logger.error(f"Error sending message to thread: {e}")
    return None

def lookup_hamro_user(email=None, phone=None, school=None):
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
        response = requests.get(url, params=params, headers=get_headers(school=school))
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

def lookup_hamro_users_batch(emails=None, phones=None, school=None):
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
        response = _request_with_retry('post', url, json=payload, headers=get_headers(school=school))
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

def add_users_to_thread_batch(thread_id, user_ids, school=None):
    """Add multiple users to a thread in Hamro platform using batch endpoint.
    If batch endpoint fails with 422 or any validation error, falls back to adding
    users individually so a single invalid user ID does not fail the entire batch.
    Returns the set of user_ids that were successfully added.
    """
    url = f"{get_base_url()}/api/v1/platform/threads/{thread_id}/users/batch"
    user_ids = list(set(user_ids))
    added = set()
    
    # Chunk the user_ids to avoid 413 errors
    for chunk in chunk_list(user_ids, 50):
        if not chunk: continue
        payload = {
            'user_ids': chunk
        }
        try:
            response = _request_with_retry('post', url, json=payload, headers=get_headers(school=school))
            if response.status_code in (200, 201):
                result = response.json()
                if isinstance(result, list):
                    added.update(result)
                elif isinstance(result, dict) and 'user_ids' in result:
                    added.update(result['user_ids'])
                else:
                    added.update(chunk)
            else:
                logger.warning(f"Batch add users returned status={response.status_code} for thread {thread_id}: {response.text}. Falling back to individual adds.")
                # Fallback: add one-by-one so one invalid user doesn't block the rest
                for uid in chunk:
                    if add_user_to_thread(thread_id, uid, school=school):
                        added.add(uid)
                    else:
                        logger.warning(f"Skipping invalid user {uid} in thread {thread_id}")
        except Exception as e:
            logger.warning(f"Batch add users error for thread {thread_id}: {e}. Falling back to individual adds.")
            for uid in chunk:
                try:
                    if add_user_to_thread(thread_id, uid, school=school):
                        added.add(uid)
                except Exception:
                    pass
            
    return added

def get_thread_participants(thread_id, school=None):
    """Fetch current participant details in a thread from Hamro platform.
    Paginates through all pages to ensure every single participant is fetched.
    Returns list of dicts containing 'user_id' and 'admin' on success, or None if 404.
    """
    url = f"{get_base_url()}/api/v1/platform/threads/{thread_id}/users"
    all_participants = []
    seen_user_ids = set()
    page = 1
    
    while True:
        try:
            params = {'per_page': 100, 'page': page}
            response = _request_with_retry('get', url, params=params, headers=get_headers(school=school), timeout=15)
            if response.status_code == 200:
                data = response.json()
                raw_list = []
                has_next = False
                
                if isinstance(data, list):
                    raw_list = data
                    has_next = False
                elif isinstance(data, dict):
                    raw_list = data.get('data') or data.get('users') or data.get('participants') or data.get('results') or []
                    current_page = data.get('current_page') or data.get('page') or page
                    last_page = data.get('last_page') or data.get('total_pages')
                    if last_page and current_page < last_page:
                        has_next = True
                    elif data.get('next_page_url'):
                        has_next = True
                        
                count_added = 0
                for u in raw_list:
                    if isinstance(u, dict):
                        uid = u.get('user_id') or u.get('id') or u.get('participant_id')
                        if uid and str(uid) not in seen_user_ids:
                            seen_user_ids.add(str(uid))
                            all_participants.append({
                                'user_id': str(uid),
                                'admin': bool(u.get('admin', False))
                            })
                            count_added += 1
                
                if not has_next or count_added == 0 or len(raw_list) == 0:
                    break
                page += 1
            elif response.status_code == 404:
                logger.warning(f"Thread {thread_id} not found on platform (404).")
                return None
            else:
                logger.error(f"Failed to fetch users for thread {thread_id}: status={response.status_code}, response={response.text}")
                break
        except Exception as e:
            logger.error(f"Error fetching participants for thread {thread_id}: {e}")
            break
            
    return all_participants

def get_thread_users(thread_id, school=None):
    """Fetch current user_ids in a thread from Hamro platform.
    Returns list of user_ids on success, or None if the thread does not exist (404).
    Raises requests.HTTPError or requests.RequestException on failure.
    """
    participants = get_thread_participants(thread_id, school=school)
    if participants is None:
        return None
    return [p['user_id'] for p in participants]

def update_user_role_in_thread(thread_id, user_id, role, school=None):
    """Update a user's role (admin or member) in a thread on Hamro platform."""
    url = f"{get_base_url()}/api/v1/platform/threads/{thread_id}/users/{user_id}/role"
    payload = {
        'role': role
    }
    try:
        response = requests.patch(url, json=payload, headers=get_headers(school=school))
        if response.status_code == 200:
            logger.info(f"Successfully updated role of user {user_id} to '{role}' in thread {thread_id}.")
            return True
        elif response.status_code == 403 and "business owner" in response.text.lower():
            # Business owner role is permanently fixed as admin on Hamro
            logger.debug(f"User {user_id} is business owner (role fixed on platform).")
            return True
        else:
            logger.error(f"Failed to update role of user {user_id} in thread {thread_id}: status={response.status_code}, response={response.text}")
    except Exception as e:
        logger.error(f"Error updating user role in thread: {e}")
    return False

def update_user_roles_batch(thread_id, admin_ids=None, member_ids=None, school=None):
    """Update roles of multiple users in bulk in a thread on Hamro platform.
    Tries batch endpoint first; if it fails, falls back to individual update_user_role_in_thread calls.
    Returns True if all roles were updated successfully.
    """
    url = f"{get_base_url()}/api/v1/platform/threads/{thread_id}/users/role/batch"
    payload = {}
    if admin_ids:
        payload['admin'] = list(admin_ids)
    if member_ids:
        payload['member'] = list(member_ids)
        
    if not payload:
        return True

    try:
        response = _request_with_retry('patch', url, json=payload, headers=get_headers(school=school))
        if response.status_code in (200, 201, 204):
            logger.info(f"Successfully batch updated roles in thread {thread_id}.")
            return True
        else:
            logger.warning(f"Batch role update failed for thread {thread_id}: status={response.status_code}, response={response.text}. Falling back to individual updates.")
    except Exception as e:
        logger.warning(f"Batch role update error for thread {thread_id}: {e}. Falling back to individual updates.")

    # Fallback: promote/demote individually
    all_ok = True
    if admin_ids:
        for uid in admin_ids:
            if not update_user_role_in_thread(thread_id, uid, 'admin', school=school):
                all_ok = False
    if member_ids:
        for uid in member_ids:
            if not update_user_role_in_thread(thread_id, uid, 'member', school=school):
                all_ok = False
    return all_ok
