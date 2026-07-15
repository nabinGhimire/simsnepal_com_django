import logging
import time
from django.db import transaction
from django.db.models import Q
from sms.models import Group, Teacher, StudentSession, TeacherSubjectAccess, Section, SchoolGrade, PlatformSetting, PlatformUserMapping, GroupMembershipCache
from sms.hamro import create_thread, update_thread, add_users_to_thread_batch, lookup_hamro_users_batch, format_phone, get_thread_users, remove_user_from_thread, remove_users_from_thread_batch, update_user_role_in_thread, get_thread_participants, update_user_roles_batch, thread_exists, delete_thread, list_threads

logger = logging.getLogger(__name__)

def acquire_sync_lock():
    """Acquires a database-level sync lock. Returns True if acquired, False otherwise."""
    try:
        with transaction.atomic():
            # Get or create the lock setting
            lock, created = PlatformSetting.objects.get_or_create(
                key='SYNC_LOCK',
                defaults={'value': '0'}
            )
            
            # lock the row
            lock = PlatformSetting.objects.select_for_update().get(key='SYNC_LOCK')
            
            try:
                lock_val = float(lock.value)
            except (ValueError, TypeError):
                lock_val = 0.0
                
            current_time = time.time()
            # If lock was set less than 5 minutes (300 seconds) ago, it is active
            if lock_val > 0 and (current_time - lock_val) < 300:
                return False
                
            lock.value = str(current_time)
            lock.save()
            return True
    except Exception as e:
        logger.error(f"Error acquiring sync lock: {e}")
        return False

def release_sync_lock():
    """Releases the sync lock."""
    try:
        lock = PlatformSetting.objects.get(key='SYNC_LOCK')
        lock.value = '0'
        lock.save()
    except Exception as e:
        logger.error(f"Error releasing sync lock: {e}")

def normalize_lookup_key(key):
    """Normalize phone or email for robust lookup."""
    if not key:
        return ""
    key = str(key).strip().lower()
    if '@' not in key:
        # Consistently format phone numbers first
        key = format_phone(key)
    if key.startswith('+'):
        key = key[1:]
    return key

def get_platform_users_map(emails, phones, school=None):
    """Perform batch lookup for given list of emails and phones, returning a lookup map with normalized keys.
    Utilizes PlatformUserMapping cache to minimize API calls and rate-limits unregistered lookups.
    """
    from django.utils import timezone
    from datetime import timedelta

    # Normalize inputs
    normalized_emails = [normalize_lookup_key(e) for e in emails if e]
    normalized_phones = [normalize_lookup_key(p) for p in phones if p]

    all_keys = list(set(normalized_emails + normalized_phones))
    if not all_keys:
        return {}

    # Query existing cache
    cache_qs = PlatformUserMapping.objects.filter(phone_or_email__in=all_keys)
    cache_map = {c.phone_or_email: c for c in cache_qs}

    lookup_emails = []
    lookup_phones = []
    results = {}

    cutoff_time = timezone.now() - timedelta(hours=24)

    # Distinguish between found, unfound-recent, and needs-lookup
    for key in all_keys:
        cached = cache_map.get(key)
        if cached:
            if cached.external_id:
                # Cache hit - found previously
                results[key] = cached.external_id
            elif cached.last_checked >= cutoff_time:
                # Cache hit - checked recently and not found (within 24h)
                pass
            else:
                # Stale unregistered cache - needs check again
                if '@' in key:
                    lookup_emails.append(key)
                else:
                    lookup_phones.append(key)
        else:
            # Not in cache - needs lookup
            if '@' in key:
                lookup_emails.append(key)
            else:
                lookup_phones.append(key)

    if lookup_emails or lookup_phones:
        try:
            logger.info(f"Performing batch Hamro API lookup for {len(lookup_emails)} emails and {len(lookup_phones)} phones...")
            api_results = lookup_hamro_users_batch(emails=lookup_emails, phones=lookup_phones, school=school)
            
            # Map of normalized looked up key -> external_id
            found_normalized = {}
            for raw_k, ext_id in api_results.items():
                if ext_id:
                    norm_k = normalize_lookup_key(raw_k)
                    found_normalized[norm_k] = ext_id
                    results[norm_k] = ext_id

            # Save/update cache records in DB using bulk upsert (much faster than one-by-one)
            with transaction.atomic():
                all_looked_up = set(lookup_emails + lookup_phones)
                now = timezone.now()
                objs_to_create = []
                objs_to_update = []
                for key in all_looked_up:
                    ext_id = found_normalized.get(key)
                    existing = cache_map.get(key)
                    if existing:
                        existing.external_id = ext_id
                        existing.last_checked = now
                        objs_to_update.append(existing)
                    else:
                        objs_to_create.append(
                            PlatformUserMapping(phone_or_email=key, external_id=ext_id, last_checked=now)
                        )
                if objs_to_create:
                    PlatformUserMapping.objects.bulk_create(objs_to_create, ignore_conflicts=True)
                if objs_to_update:
                    PlatformUserMapping.objects.bulk_update(objs_to_update, ['external_id', 'last_checked'])
        except Exception as e:
            logger.error(f"Platform user lookup failed/timed out during cached lookup: {e}")

    return results

def get_owner_platform_id(school):
    """Retrieve the platform user ID for the school owner/admin."""
    owner_user = school.owner.user
    owner_teacher = Teacher.objects.filter(teacher=owner_user).first()
    if owner_teacher and owner_teacher.external_id:
        return owner_teacher.external_id
        
    emails = [owner_user.email] if owner_user.email else []
    phones = [format_phone(owner_user.username)] if owner_user.username and owner_user.username.isdigit() else []
    if not emails and not phones:
        return None
    try:
        raw_map = lookup_hamro_users_batch(emails=emails, phones=phones, school=school)
        if raw_map:
            for val in raw_map.values():
                if val:
                    return val
    except Exception as e:
        logger.error(f"Error fetching owner platform ID: {e}")
    return None

def setup_platform_integration(school):
    """
    Automates the business registration and delegated key setup on Hamro.
    Returns True if successfully set up (or already set up), False otherwise.
    """
    from sms.models import PlatformSetting
    from sms.hamro import sync_hamro_business, create_delegated_api_key
    
    # If this school already has a business_key, don't overwrite it.
    # Overwriting would create a new key that cannot access previously created threads.
    if school.business_key:
        return True

    owner_id = get_owner_platform_id(school)
    if not owner_id:
        logger.error("Cannot set up platform integration: School owner is not registered on Hamro.")
        return False
        
    # 1. Sync/Register Platform Business (if needed)
    platform_id_obj = PlatformSetting.objects.filter(key='PLATFORM_BUSINESS_ID').first()
    platform_id = platform_id_obj.value if platform_id_obj else None
    if not platform_id:
        platform_id = sync_hamro_business(owner_id, "SIMS Nepal Platform", "platform")
        if platform_id:
            PlatformSetting.objects.create(key='PLATFORM_BUSINESS_ID', value=platform_id)
        else:
            logger.error("Failed to register platform business.")
            return False

    # 2. Sync/Register Company Business (per-school)
    company_setting_key = f'COMPANY_BUSINESS_ID_{school.id}'
    company_id_obj = PlatformSetting.objects.filter(key=company_setting_key).first()
    company_id = company_id_obj.value if company_id_obj else None
    new_company_id = sync_hamro_business(owner_id, school.name, "company", existing_id=company_id)
    if new_company_id:
        if company_id_obj:
            company_id_obj.value = new_company_id
            company_id_obj.save()
        else:
            PlatformSetting.objects.create(key=company_setting_key, value=new_company_id)
        company_id = new_company_id
    else:
        logger.error("Failed to register company business.")
        return False

    # 3. Generate Delegated API Key for the Company (per-school)
    key_name = f"SIMS Nepal — {school.name}"
    service_name = f"simsnepal_{school.id}"
    new_key = create_delegated_api_key(company_id, platform_id, key_name, service_name)
    if new_key:
        # Save the business key on the school itself (per-school)
        school.business_key = new_key
        school.save(update_fields=['business_key'])
        return True
    
    logger.error("Failed to create delegated API key.")
    return False

def sync_group_membership_cached(group_obj, target_members, admin_ids, force_refresh=False, school=None):
    """
    Syncs the group membership with Hamro platform, utilizing a local GroupMembershipCache
    to minimize API requests.
    
    target_members: set of platform user IDs that should be in the group.
    admin_ids: set of platform user IDs that should have 'admin' role.
    """
    group_id = group_obj.external_id
    if not group_id:
        return
        
    # 1. Fetch cached members from database
    cached_qs = GroupMembershipCache.objects.filter(group=group_obj)
    cached_members = {
        m.platform_user_id: m.role
        for m in cached_qs
    }
    
    # If cache is empty or force_refresh is True, we fetch the actual participants from the platform
    # to populate/reset the cache.
    if not cached_members or force_refresh:
        try:
            logger.info(f"Cache miss or force refresh for group {group_obj.name}. Fetching participants from platform...")
            participants = get_thread_participants(group_id, school=school)
            if participants is not None:
                # Clear existing cache
                GroupMembershipCache.objects.filter(group=group_obj).delete()
                
                # Bulk create new cache
                bulk_objs = []
                cached_members = {}
                for p in participants:
                    u_id = p['user_id']
                    role = 'admin' if p['admin'] else 'member'
                    bulk_objs.append(GroupMembershipCache(group=group_obj, platform_user_id=u_id, role=role))
                    cached_members[u_id] = role
                GroupMembershipCache.objects.bulk_create(bulk_objs)
        except Exception as e:
            logger.error(f"Failed to fetch participants from platform for group {group_obj.name} to populate cache: {e}")
            # If we couldn't fetch from platform and we have no cache, we cannot sync reliably.
            if not cached_members:
                return

    # 2. Determine changes
    target_members = set(target_members)
    admin_ids = set(admin_ids)
    
    current_member_ids = set(cached_members.keys())
    
    to_add = target_members - current_member_ids
    to_remove = current_member_ids - target_members
    
    to_promote = []
    to_demote = []
    
    for u_id in target_members & current_member_ids:
        target_role = 'admin' if u_id in admin_ids else 'member'
        current_role = cached_members[u_id]
        if current_role != target_role:
            if target_role == 'admin':
                to_promote.append(u_id)
            else:
                to_demote.append(u_id)

    # 3. Apply changes via APIs and update local cache
    # Add users (batch — single API call for all adds)
    if to_add:
        try:
            logger.info(f"Adding {len(to_add)} users to group {group_obj.name} on platform...")
            add_users_to_thread_batch(group_id, list(to_add), school=school)
            # Update cache — default new users to 'member'; promote after API confirms
            bulk_objs = []
            for u_id in to_add:
                bulk_objs.append(GroupMembershipCache(group=group_obj, platform_user_id=u_id, role='member'))
                # New members default to 'member' on addition. If their target role is 'admin', we must explicitly promote them.
                if u_id in admin_ids:
                    to_promote.append(u_id)
            GroupMembershipCache.objects.bulk_create(bulk_objs)
        except Exception as e:
            logger.error(f"Failed to add users to group {group_obj.name}: {e}")

    # Remove users (batch — single API call for all removes instead of one-by-one)
    if to_remove:
        logger.info(f"Removing {len(to_remove)} users from group {group_obj.name} on platform...")
        try:
            removed_ids = remove_users_from_thread_batch(group_id, list(to_remove), school=school)
            if removed_ids:
                GroupMembershipCache.objects.filter(group=group_obj, platform_user_id__in=removed_ids).delete()
            # Log any that failed to remove
            failed = to_remove - removed_ids
            if failed:
                logger.warning(f"Failed to remove {len(failed)} users from group {group_obj.name}: {failed}")
        except Exception as e:
            logger.error(f"Failed to batch remove users from group {group_obj.name}: {e}")

    # Update roles (promote/demote) in bulk
    if to_promote or to_demote:
        try:
            logger.info(f"Batch updating roles for {len(to_promote)} admins and {len(to_demote)} members in group {group_obj.name}...")
            success = update_user_roles_batch(group_id, admin_ids=to_promote, member_ids=to_demote, school=school)
            if success:
                if to_promote:
                    GroupMembershipCache.objects.filter(group=group_obj, platform_user_id__in=to_promote).update(role='admin')
                if to_demote:
                    GroupMembershipCache.objects.filter(group=group_obj, platform_user_id__in=to_demote).update(role='member')
        except Exception as e:
            logger.error(f"Failed to bulk update roles in group {group_obj.name}: {e}")

def normalize_group_name(grade_name, section_name, session_year, section_count):
    """Format and normalize class/section group name to avoid duplicate prefixes."""
    grade_name = " ".join(grade_name.split())
    lower_grade = grade_name.lower()
    
    prefix = ""
    if not (lower_grade.startswith("class") or lower_grade.startswith("grade")):
        prefix = "Class "
        
    if section_count > 1 and section_name:
        return f"{prefix}{grade_name} {section_name} {session_year}"
    else:
        return f"{prefix}{grade_name} {session_year}"

def sync_school_channel(school, session):
    """Ensure a school-wide channel exists and add all teachers and parents (batch mode)."""
    channel_name = school.name
    # Query by name, session, school — ignore is_broadcast flag (it may have been set incorrectly)
    channel_group = Group.objects.filter(session=session, name=channel_name, school=school).first()
    
    if not channel_group:
        ext_id = create_thread('channel', channel_name, f"School channel for {channel_name}", school=school)
        if ext_id:
            channel_group = Group.objects.create(
                name=channel_name,
                session=session,
                is_broadcast=True,
                external_id=ext_id,
                school=school,
            )
        else:
            logger.error(f"Could not create school channel on platform for {channel_name}")
            return None
    else:
        # Check if external_id actually exists on platform FIRST
        if channel_group.external_id:
            try:
                exists = thread_exists(channel_group.external_id, school=school)
                if exists is False:
                    logger.warning(f"School channel thread {channel_group.external_id} confirmed deleted on platform. Recreating.")
                    channel_group.external_id = None
                    channel_group.save()
                    GroupMembershipCache.objects.filter(group=channel_group).delete()
            except Exception as e:
                logger.error(f"Failed to check school channel existence: {e}")
                return None

        # Now update name if needed (only if thread still exists)
        if channel_group.external_id and channel_group.name != channel_name:
            update_thread(channel_group.external_id, channel_name, school=school)
            channel_group.name = channel_name
            channel_group.save()

        # Recreate only if external_id is confirmed missing
        if not channel_group.external_id:
            try:
                ext_id = create_thread('channel', channel_name, f"School channel for {channel_name}", school=school)
                if ext_id:
                    channel_group.external_id = ext_id
                    channel_group.save()
                    GroupMembershipCache.objects.filter(group=channel_group).delete()
                else:
                    return None
            except Exception as e:
                logger.error(f"Failed to create school channel on platform: {e}")
                return None

    # Gather all teachers in the school
    teacher_users = [
        t.teacher for t in Teacher.objects.filter(
            Q(added_by__branchuser__school=school) | 
            Q(teacher__teachersubjectaccess__subject__branch=school)
        ).select_related('teacher').distinct()
    ]
    
    emails_to_lookup = [t.email for t in teacher_users if t.email]
    phones_to_lookup = [format_phone(t.username) for t in teacher_users if t.username and t.username.isdigit()]
    
    # Gather all parents of active students in the school
    student_sessions = StudentSession.objects.filter(
        session=session, student__school=school, status=True
    ).select_related('student')
    parent_emails = []
    parent_phones = []
    
    for ss in student_sessions:
        student = ss.student
        if student.fathers_email: parent_emails.append(student.fathers_email)
        if student.fathers_phone: parent_phones.append(format_phone(str(student.fathers_phone)))
        if student.mothers_email: parent_emails.append(student.mothers_email)
        if student.mothers_phone: parent_phones.append(format_phone(str(student.mothers_phone)))
        if student.guardian_email: parent_emails.append(student.guardian_email)
        if student.guardian_phone: parent_phones.append(format_phone(str(student.guardian_phone)))

    # Run batch lookup for all emails and phones
    all_emails = list(set(emails_to_lookup + parent_emails))
    all_phones = list(set(phones_to_lookup + parent_phones))
    
    try:
        users_map = get_platform_users_map(all_emails, all_phones, school=school)
    except Exception as e:
        logger.error(f"Platform user lookup failed/timed out: {e}")
        users_map = {}

    # Collect valid external IDs
    to_add_ids = []
    admin_ids = set()  # IDs that should be admins
    
    # Auto-add the school owner/admin to protect them from removal
    owner_platform_id = get_owner_platform_id(school)
    if owner_platform_id:
        to_add_ids.append(owner_platform_id)
        admin_ids.add(owner_platform_id)
    
    # Update teacher external IDs locally if looked up
    # Pre-fetch all Teacher objects for these users to avoid N+1 queries
    teacher_user_ids = [u.id for u in teacher_users]
    teacher_objs_map = {
        t.teacher_id: t for t in Teacher.objects.filter(teacher_id__in=teacher_user_ids)
    }
    teachers_to_save = []
    for t_user in teacher_users:
        teacher_obj = teacher_objs_map.get(t_user.id)
        ext_id = teacher_obj.external_id if teacher_obj else None
        
        if not ext_id:
            if t_user.email:
                norm_email = normalize_lookup_key(t_user.email)
                if norm_email in users_map:
                    ext_id = users_map[norm_email]
            if not ext_id and t_user.username and t_user.username.isdigit():
                norm_phone = normalize_lookup_key(format_phone(t_user.username))
                if norm_phone in users_map:
                    ext_id = users_map[norm_phone]
            if ext_id and teacher_obj:
                teacher_obj.external_id = ext_id
                teachers_to_save.append(teacher_obj)
                
        if ext_id:
            to_add_ids.append(ext_id)
            admin_ids.add(ext_id)
    
    # Bulk save teacher external IDs
    if teachers_to_save:
        Teacher.objects.bulk_update(teachers_to_save, ['external_id'])

    # Collect parent external IDs
    for email in parent_emails:
        norm = normalize_lookup_key(email)
        if norm in users_map:
            to_add_ids.append(users_map[norm])
    for phone in parent_phones:
        norm = normalize_lookup_key(phone)
        if norm in users_map:
            to_add_ids.append(users_map[norm])

    to_add_ids = list(set(to_add_ids))

    # Sync using our optimized membership cache helper
    sync_group_membership_cached(channel_group, to_add_ids, admin_ids, school=school)

    return channel_group

def sync_teachers_group(school, session):
    """Ensure a teachers-only discussion group exists and populate with all teachers (batch mode)."""
    group_name = f"{school.name} Teachers"
    # Query by name, session, school — ignore is_broadcast flag (it may have been set incorrectly)
    group_obj = Group.objects.filter(session=session, grade=None, section=None, name=group_name, school=school).first()
    
    if not group_obj:
        ext_id = create_thread('group', group_name, f"Teachers discussion group for {school.name}", school=school)
        if ext_id:
            group_obj = Group.objects.create(
                name=group_name,
                session=session,
                is_broadcast=False,
                external_id=ext_id,
                school=school,
            )
        else:
            logger.error(f"Could not create teachers group on platform for {group_name}")
            return None
    else:
        # Check if external_id actually exists on platform FIRST
        if group_obj.external_id:
            try:
                exists = thread_exists(group_obj.external_id, school=school)
                if exists is False:
                    logger.warning(f"Teachers group thread {group_obj.external_id} confirmed deleted on platform. Recreating.")
                    group_obj.external_id = None
                    group_obj.save()
                    GroupMembershipCache.objects.filter(group=group_obj).delete()
            except Exception as e:
                logger.error(f"Failed to check teachers group existence: {e}")
                return None

        # Now update name if needed (only if thread still exists)
        if group_obj.external_id and group_obj.name != group_name:
            update_thread(group_obj.external_id, group_name, school=school)
            group_obj.name = group_name
            group_obj.save()

        # Recreate only if external_id is confirmed missing
        if not group_obj.external_id:
            try:
                ext_id = create_thread('group', group_name, f"Teachers discussion group for {school.name}", school=school)
                if ext_id:
                    group_obj.external_id = ext_id
                    group_obj.save()
                    GroupMembershipCache.objects.filter(group=group_obj).delete()
                else:
                    return None
            except Exception as e:
                logger.error(f"Failed to create teachers group on platform: {e}")
                return None

    # Fetch all teachers
    teacher_users = [
        t.teacher for t in Teacher.objects.filter(
            Q(added_by__branchuser__school=school) | 
            Q(teacher__teachersubjectaccess__subject__branch=school)
        ).select_related('teacher').distinct()
    ]
    
    emails_to_lookup = [t.email for t in teacher_users if t.email]
    phones_to_lookup = [format_phone(t.username) for t in teacher_users if t.username and t.username.isdigit()]
    try:
        users_map = get_platform_users_map(emails_to_lookup, phones_to_lookup, school=school)
    except Exception as e:
        logger.error(f"Platform user lookup failed/timed out for teachers group: {e}")
        users_map = {}

    to_add_ids = []
    admin_ids = set()

    # Auto-add the school owner/admin to protect them from removal
    owner_platform_id = get_owner_platform_id(school)
    if owner_platform_id:
        to_add_ids.append(owner_platform_id)
        admin_ids.add(owner_platform_id)

    # Pre-fetch all Teacher objects to avoid N+1 queries
    teacher_user_ids = [u.id for u in teacher_users]
    teacher_objs_map = {
        t.teacher_id: t for t in Teacher.objects.filter(teacher_id__in=teacher_user_ids)
    }
    teachers_to_save = []
    for t_user in teacher_users:
        teacher_obj = teacher_objs_map.get(t_user.id)
        ext_id = teacher_obj.external_id if teacher_obj else None
        
        if not ext_id:
            if t_user.email:
                norm_email = normalize_lookup_key(t_user.email)
                if norm_email in users_map:
                    ext_id = users_map[norm_email]
            if not ext_id and t_user.username and t_user.username.isdigit():
                norm_phone = normalize_lookup_key(format_phone(t_user.username))
                if norm_phone in users_map:
                    ext_id = users_map[norm_phone]
            if ext_id and teacher_obj:
                teacher_obj.external_id = ext_id
                teachers_to_save.append(teacher_obj)
                
        if ext_id:
            to_add_ids.append(ext_id)
            admin_ids.add(ext_id)
    
    if teachers_to_save:
        Teacher.objects.bulk_update(teachers_to_save, ['external_id'])

    to_add_ids = list(set(to_add_ids))

    # Build admin ID set (owner + teachers)
    # admin_ids already contains owner and teacher IDs
    sync_group_membership_cached(group_obj, to_add_ids, admin_ids, school=school)

    return group_obj

def sync_grade_groups(school, session):
    """Create group for each grade and section, and populate with teachers and parents."""
    grades = SchoolGrade.objects.filter(school=school, active=True)
    sync_results = []
    
    for grade in grades:
        sections = Section.objects.filter(grade=grade, school=school, session=session)
        section_count = sections.count()
        
        if section_count == 0:
            continue
            
        if section_count == 1:
            sec = sections.first()
            group_name = normalize_group_name(grade.grade_name, sec.section, session.year, section_count)
            group_obj = sync_single_group(group_name, grade, sec, session, school)
            if group_obj:
                sync_results.append(group_obj)
        else:
            for sec in sections:
                group_name = normalize_group_name(grade.grade_name, sec.section, session.year, section_count)
                group_obj = sync_single_group(group_name, grade, sec, session, school)
                if group_obj:
                    sync_results.append(group_obj)
                    
    return sync_results

def sync_single_group(group_name, grade, section, session, school):
    """Sync a single group, adding section teachers and parents (batch mode)."""
    # Query by grade, section, session, is_broadcast=False to uniquely identify the section group
    group_obj = Group.objects.filter(
        grade=grade,
        section=section,
        session=session,
        is_broadcast=False
    ).first()
    
    if not group_obj:
        ext_id = create_thread('group', group_name, f"Class group for {group_name}", school=school)
        if ext_id:
            group_obj = Group.objects.create(
                name=group_name,
                session=session,
                grade=grade,
                section=section,
                is_broadcast=False,
                external_id=ext_id,
                school=school,
            )
        else:
            logger.error(f"Could not create class group on platform for {group_name}")
            return None
    else:
        # Check if external_id actually exists on platform FIRST
        # Use thread_exists (safe) instead of get_thread_users (destructive).
        if group_obj.external_id:
            try:
                exists = thread_exists(group_obj.external_id, school=school)
                if exists is False:
                    logger.warning(f"Class group thread {group_obj.external_id} confirmed deleted on platform. Recreating.")
                    group_obj.external_id = None
                    group_obj.save()
                    GroupMembershipCache.objects.filter(group=group_obj).delete()
            except Exception as e:
                logger.error(f"Failed to check class group {group_name} existence: {e}")
                return None

        # Now update name if needed (only if thread still exists)
        if group_obj.external_id and group_obj.name != group_name:
            update_thread(group_obj.external_id, group_name, school=school)
            group_obj.name = group_name
            group_obj.save()

        # Recreate only if external_id is confirmed missing
        if not group_obj.external_id:
            try:
                ext_id = create_thread('group', group_name, f"Class group for {group_name}", school=school)
                if ext_id:
                    group_obj.external_id = ext_id
                    group_obj.save()
                    GroupMembershipCache.objects.filter(group=group_obj).delete()
                else:
                    return None
            except Exception as e:
                logger.error(f"Failed to create class group {group_name} on platform: {e}")
                return None

    # Get section teachers
    teaching_users = [
        access.teacher for access in TeacherSubjectAccess.objects.filter(
            session=session,
            grade=grade,
            section=section,
            status=True
        ).select_related('teacher')
    ]
    
    teacher_emails = [t.email for t in teaching_users if t.email]
    teacher_phones = [format_phone(t.username) for t in teaching_users if t.username and t.username.isdigit()]

    # Get section parents
    student_sessions = StudentSession.objects.filter(
        session=session, grade=grade, section=section, status=True
    ).select_related('student')
    parent_emails = []
    parent_phones = []
    
    for ss in student_sessions:
        student = ss.student
        if student.fathers_email: parent_emails.append(student.fathers_email)
        if student.fathers_phone: parent_phones.append(format_phone(str(student.fathers_phone)))
        if student.mothers_email: parent_emails.append(student.mothers_email)
        if student.mothers_phone: parent_phones.append(format_phone(str(student.mothers_phone)))
        if student.guardian_email: parent_emails.append(student.guardian_email)
        if student.guardian_phone: parent_phones.append(format_phone(str(student.guardian_phone)))

    # Batch lookup
    all_emails = list(set(teacher_emails + parent_emails))
    all_phones = list(set(parent_phones + teacher_phones))
    try:
        users_map = get_platform_users_map(all_emails, all_phones, school=school)
    except Exception as e:
        logger.error(f"Platform user lookup failed/timed out for class group {group_name}: {e}")
        users_map = {}

    # Collect members
    to_add_ids = []
    admin_ids = set()
    
    # Auto-add the school owner/admin to protect them from removal
    owner_platform_id = get_owner_platform_id(school)
    if owner_platform_id:
        to_add_ids.append(owner_platform_id)
        admin_ids.add(owner_platform_id)
    
    # Section teachers
    # Pre-fetch Teacher objects to avoid N+1 queries
    teaching_user_ids = [u.id for u in teaching_users]
    teacher_objs_map = {
        t.teacher_id: t for t in Teacher.objects.filter(teacher_id__in=teaching_user_ids)
    }
    teachers_to_save = []
    for t_user in teaching_users:
        teacher_obj = teacher_objs_map.get(t_user.id)
        ext_id = teacher_obj.external_id if teacher_obj else None
        
        if not ext_id:
            if t_user.email:
                norm_email = normalize_lookup_key(t_user.email)
                if norm_email in users_map:
                    ext_id = users_map[norm_email]
            if not ext_id and t_user.username and t_user.username.isdigit():
                norm_phone = normalize_lookup_key(format_phone(t_user.username))
                if norm_phone in users_map:
                    ext_id = users_map[norm_phone]
            if ext_id and teacher_obj:
                teacher_obj.external_id = ext_id
                teachers_to_save.append(teacher_obj)
                
        if ext_id:
            to_add_ids.append(ext_id)
            admin_ids.add(ext_id)
    
    if teachers_to_save:
        Teacher.objects.bulk_update(teachers_to_save, ['external_id'])

    # Section parents
    for email in parent_emails:
        norm = normalize_lookup_key(email)
        if norm in users_map:
            to_add_ids.append(users_map[norm])
    for phone in parent_phones:
        norm = normalize_lookup_key(phone)
        if norm in users_map:
            to_add_ids.append(users_map[norm])

    to_add_ids = list(set(to_add_ids))

    # Sync using our optimized membership cache helper
    sync_group_membership_cached(group_obj, to_add_ids, admin_ids, school=school)

    return group_obj

def cleanup_duplicate_threads(school, session, dry_run=False):
    """Find and clean up duplicate Group records for the same school+session.
    
    Duplicate groups are identified by matching (name, session, school, is_broadcast).
    When duplicates exist, the one with the valid external_id (confirmed on platform)
    is kept. Others are deleted from DB (and their Hamro threads deleted if possible).
    
    Returns a list of dicts describing what was cleaned up.
    """
    actions = []
    
    # Find duplicates among broadcast channels (school channels)
    broadcast_groups = Group.objects.filter(
        school=school, session=session, is_broadcast=True
    ).order_by('id')
    
    seen_broadcasts = {}
    for g in broadcast_groups:
        key = g.name
        if key in seen_broadcasts:
            # Duplicate found — decide which to keep
            existing = seen_broadcasts[key]
            keep, discard = (existing, g) if existing.external_id else (g, existing)
            
            if not dry_run:
                # Delete the Hamro thread for the discard group (if it has one)
                if discard.external_id:
                    try:
                        delete_thread(discard.external_id, school=school)
                    except Exception as e:
                        logger.warning(f"Could not delete duplicate thread {discard.external_id}: {e}")
                    GroupMembershipCache.objects.filter(group=discard).delete()
                discard.delete()
            
            actions.append({
                'type': 'broadcast_channel',
                'name': key,
                'kept_id': keep.external_id,
                'removed_id': discard.external_id,
            })
        else:
            # Validate existing external_id
            if g.external_id:
                try:
                    exists = thread_exists(g.external_id, school=school)
                    if exists is False:
                        if not dry_run:
                            g.external_id = None
                            g.save()
                            GroupMembershipCache.objects.filter(group=g).delete()
                        actions.append({
                            'type': 'broadcast_channel',
                            'name': key,
                            'action': 'cleared_stale_external_id',
                            'old_id': g.external_id,
                        })
                except Exception:
                    pass  # transient error, skip validation
            seen_broadcasts[key] = g

    # Find duplicates among non-broadcast groups (teachers group, class groups)
    non_broadcast_groups = Group.objects.filter(
        school=school, session=session, is_broadcast=False
    ).order_by('id')
    
    seen_groups = {}
    for g in non_broadcast_groups:
        # Key by (name, grade, section) to identify true duplicates
        key = (g.name, g.grade_id, g.section_id)
        if key in seen_groups:
            existing = seen_groups[key]
            keep, discard = (existing, g) if existing.external_id else (g, existing)
            
            if not dry_run:
                if discard.external_id:
                    try:
                        delete_thread(discard.external_id, school=school)
                    except Exception as e:
                        logger.warning(f"Could not delete duplicate thread {discard.external_id}: {e}")
                    GroupMembershipCache.objects.filter(group=discard).delete()
                discard.delete()
            
            actions.append({
                'type': 'group',
                'name': g.name,
                'kept_id': keep.external_id,
                'removed_id': discard.external_id,
            })
        else:
            if g.external_id:
                try:
                    exists = thread_exists(g.external_id, school=school)
                    if exists is False:
                        if not dry_run:
                            g.external_id = None
                            g.save()
                            GroupMembershipCache.objects.filter(group=g).delete()
                        actions.append({
                            'type': 'group',
                            'name': g.name,
                            'action': 'cleared_stale_external_id',
                            'old_id': g.external_id,
                        })
                except Exception:
                    pass
            seen_groups[key] = g

    return actions


def cleanup_hamro_orphans(session, dry_run=False):
    """Find and delete orphaned threads on Hamro that have no matching DB record.
    Also finds duplicate threads on Hamro (same name) and deletes extras.
    
    Runs GLOBALLY for the session (not per-school) since Hamro threads are platform-wide.
    
    Returns a list of dicts describing what was cleaned up.
    """
    actions = []
    
    # 1. Fetch all threads from Hamro platform (single API call)
    hamro_threads = list_threads()
    if hamro_threads is None:
        logger.error("Could not list threads from Hamro platform. Skipping orphan cleanup.")
        return actions
    
    # 2. Build set of ALL known external_ids in our DB for this session (all schools)
    all_db_ext_ids = set(
        Group.objects.filter(session=session)
        .exclude(external_id=None)
        .exclude(external_id='')
        .values_list('external_id', flat=True)
    )
    
    # 3. Categorize Hamro threads
    tracked_threads = []    # in our DB
    orphan_threads = []     # NOT in our DB
    seen_names = {}         # name -> first thread with that name
    
    for thread in hamro_threads:
        ext_id = thread.get('id')
        name = thread.get('name', '')
        ttype = thread.get('type', '')
        
        if not ext_id:
            continue
        
        if ext_id in all_db_ext_ids:
            tracked_threads.append(thread)
            # Track first occurrence of each name for duplicate detection
            if name not in seen_names:
                seen_names[name] = thread
        else:
            orphan_threads.append(thread)
    
    # 4. Delete orphan threads (not in our DB at all)
    for thread in orphan_threads:
        ext_id = thread.get('id')
        name = thread.get('name', '')
        ttype = thread.get('type', '')
        
        if not dry_run:
            try:
                delete_thread(ext_id)
            except Exception as e:
                logger.warning(f"Could not delete orphan Hamro thread {ext_id} ({name}): {e}")
        actions.append({
            'type': 'hamro_orphan',
            'name': name,
            'deleted_id': ext_id,
            'thread_type': ttype,
        })
    
    return actions
