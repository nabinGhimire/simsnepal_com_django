from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Student
from sms.hamro import ensure_group, add_user_to_group, get_base_url, get_headers
# get_current_session will be imported lazily inside the signal handler to avoid circular imports
import requests, logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Student)
def sync_parent_to_hamro(sender, instance, **kwargs):
    """Sync parent contacts to Hamro after a Student is saved.
    Creates/updates the group ``Student_<reg_no>_Parents`` and adds any
    registered Hamro users for the current contacts.
    """
    school = instance.school
    contacts = []
    if getattr(instance, "fathers_phone", None):
        contacts.append(("phone", instance.fathers_phone))
    if getattr(instance, "fathers_email", None):
        contacts.append(("email", instance.fathers_email))
    if getattr(instance, "mothers_phone", None):
        contacts.append(("phone", instance.mothers_phone))
    if getattr(instance, "mothers_email", None):
        contacts.append(("email", instance.mothers_email))

    parent_ids = []
    def lookup_external_id(kind, val):
        base = get_base_url()
        url = f"{base}/users?{kind}={val}"
        try:
            resp = requests.get(url, headers=get_headers(school=school))
            resp.raise_for_status()
            data = resp.json()
            if data and isinstance(data, list) and data:
                return data[0].get('id')
        except Exception as e:
            logger.error(f"Hamro lookup failed for {kind}={val}: {e}")
        return None

    for kind, val in contacts:
        ext_id = lookup_external_id(kind, val)
        if ext_id:
            parent_ids.append(ext_id)

    if not parent_ids:
        return  # nothing to sync

    group_name = f"Student_{instance.reg_no}_Parents"
    session = get_current_session()
    group = ensure_group(group_name, session.id, school=school)
    if not group:
        logger.error(f"Failed to create/retrieve Hamro group {group_name}")
        return

    for pid in set(parent_ids):
        add_user_to_group(pid, group.external_id, school=school)
