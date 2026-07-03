import logging
import time
from django.db import transaction
from django.db.models import Q
from sms.models import Group, Teacher, StudentSession, TeacherSubjectAccess, Section, SchoolGrade, PlatformSetting, PlatformUserMapping, GroupMembershipCache
from sms.hamro import create_thread, update_thread, add_users_to_thread_batch, lookup_hamro_users_batch, format_phone, get_thread_users, remove_user_from_thread, update_user_role_in_thread, get_thread_participants, update_user_roles_batch

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

def get_platform_users_map(emails, phones):
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
            api_results = lookup_hamro_users_batch(emails=lookup_emails, phones=lookup_phones)
            
            # Map of normalized looked up key -> external_id
            found_normalized = {}
            for raw_k, ext_id in api_results.items():
                if ext_id:
                    norm_k = normalize_lookup_key(raw_k)
                    found_normalized[norm_k] = ext_id
                    results[norm_k] = ext_id

            # Save/update cache records in DB
            with transaction.atomic():
                all_looked_up = set(lookup_emails + lookup_phones)
                for key in all_looked_up:
                    ext_id = found_normalized.get(key)
                    PlatformUserMapping.objects.update_or_create(
                        phone_or_email=key,
                        defaults={
                            'external_id': ext_id,
                            'last_checked': timezone.now()
                        }
                    )
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
        raw_map = lookup_hamro_users_batch(emails=emails, phones=phones)
        if raw_map:
            for val in raw_map.values():
                if val:
                    return val
    except Exception as e:
        logger.error(f"Error fetching owner platform ID: {e}")
    return None

def sync_group_membership_cached(group_obj, target_members, admin_ids, force_refresh=False):
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
            participants = get_thread_participants(group_id)
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
    # Add users
    if to_add:
        try:
            logger.info(f"Adding {len(to_add)} users to group {group_obj.name} on platform...")
            add_users_to_thread_batch(group_id, list(to_add))
            # Update cache
            bulk_objs = []
            for u_id in to_add:
                role = 'admin' if u_id in admin_ids else 'member'
                bulk_objs.append(GroupMembershipCache(group=group_obj, platform_user_id=u_id, role=role))
                # New members default to 'member' on addition. If their target role is 'admin', we must explicitly promote them.
                if role == 'admin':
                    to_promote.append(u_id)
            GroupMembershipCache.objects.bulk_create(bulk_objs)
        except Exception as e:
            logger.error(f"Failed to add users to group {group_obj.name}: {e}")

    # Remove users
    if to_remove:
        logger.info(f"Removing {len(to_remove)} users from group {group_obj.name} on platform...")
        removed_ids = []
        for u_id in to_remove:
            try:
                success = remove_user_from_thread(group_id, u_id)
                if success:
                    removed_ids.append(u_id)
            except Exception as e:
                logger.error(f"Failed to remove user {u_id} from group {group_obj.name}: {e}")
        if removed_ids:
            GroupMembershipCache.objects.filter(group=group_obj, platform_user_id__in=removed_ids).delete()

    # Update roles (promote/demote) in bulk
    if to_promote or to_demote:
        try:
            logger.info(f"Batch updating roles for {len(to_promote)} admins and {len(to_demote)} members in group {group_obj.name}...")
            success = update_user_roles_batch(group_id, admin_ids=to_promote, member_ids=to_demote)
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
    # Query by session and is_broadcast=True to uniquely identify the channel
    channel_group = Group.objects.filter(session=session, is_broadcast=True, name=channel_name).first()
    
    if not channel_group:
        ext_id = create_thread('channel', channel_name, f"School channel for {channel_name}")
        if ext_id:
            channel_group = Group.objects.create(
                name=channel_name,
                session=session,
                is_broadcast=True,
                external_id=ext_id
            )
        else:
            logger.error(f"Could not create school channel on platform for {channel_name}")
            return None
    else:
        # Check if name needs updating
        if channel_group.name != channel_name:
            if channel_group.external_id:
                update_thread(channel_group.external_id, channel_name)
            channel_group.name = channel_name
            channel_group.save()
            
        # Check if external_id actually exists on platform
        current_users = []
        if channel_group.external_id:
            try:
                current_users = get_thread_users(channel_group.external_id)
                if current_users is None:
                    channel_group.external_id = None
                    channel_group.save()
                    GroupMembershipCache.objects.filter(group=channel_group).delete()
                    current_users = []
            except Exception as e:
                logger.error(f"Failed to fetch thread users for school channel: {e}")
                return None

        # Recreate if external_id is missing or was reset above
        if not channel_group.external_id:
            try:
                ext_id = create_thread('channel', channel_name, f"School channel for {channel_name}")
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
        ).distinct()
    ]
    
    emails_to_lookup = [t.email for t in teacher_users if t.email]
    phones_to_lookup = [format_phone(t.username) for t in teacher_users if t.username and t.username.isdigit()]
    
    # Gather all parents of active students in the school
    student_sessions = StudentSession.objects.filter(session=session, student__school=school, status=True)
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
        users_map = get_platform_users_map(all_emails, all_phones)
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
    for t_user in teacher_users:
        teacher_obj = Teacher.objects.filter(teacher=t_user).first()
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
                teacher_obj.save()
                
        if ext_id:
            to_add_ids.append(ext_id)
            admin_ids.add(ext_id)

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
    sync_group_membership_cached(channel_group, to_add_ids, admin_ids)

    return channel_group

def sync_teachers_group(school, session):
    """Ensure a teachers-only discussion group exists and populate with all teachers (batch mode)."""
    group_name = f"{school.name} Teachers"
    # Query by session, grade=None, section=None, is_broadcast=False to uniquely identify teachers group
    group_obj = Group.objects.filter(session=session, is_broadcast=False, grade=None, section=None, name=group_name).first()
    
    if not group_obj:
        ext_id = create_thread('group', group_name, f"Teachers discussion group for {school.name}")
        if ext_id:
            group_obj = Group.objects.create(
                name=group_name,
                session=session,
                is_broadcast=False,
                external_id=ext_id
            )
        else:
            logger.error(f"Could not create teachers group on platform for {group_name}")
            return None
    else:
        # Check if name needs updating
        if group_obj.name != group_name:
            if group_obj.external_id:
                update_thread(group_obj.external_id, group_name)
            group_obj.name = group_name
            group_obj.save()
            
        # Check if external_id actually exists on platform
        current_users = []
        if group_obj.external_id:
            try:
                current_users = get_thread_users(group_obj.external_id)
                if current_users is None:
                    group_obj.external_id = None
                    group_obj.save()
                    GroupMembershipCache.objects.filter(group=group_obj).delete()
                    current_users = []
            except Exception as e:
                logger.error(f"Failed to fetch thread users for teachers group: {e}")
                return None

        # Recreate if external_id is missing or was reset above
        if not group_obj.external_id:
            try:
                ext_id = create_thread('group', group_name, f"Teachers discussion group for {school.name}")
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
        ).distinct()
    ]
    
    emails_to_lookup = [t.email for t in teacher_users if t.email]
    phones_to_lookup = [format_phone(t.username) for t in teacher_users if t.username and t.username.isdigit()]
    try:
        users_map = get_platform_users_map(emails_to_lookup, phones_to_lookup)
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
    for t_user in teacher_users:
        teacher_obj = Teacher.objects.filter(teacher=t_user).first()
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
                teacher_obj.save()
                
        if ext_id:
            to_add_ids.append(ext_id)
            admin_ids.add(ext_id)

    to_add_ids = list(set(to_add_ids))

    # Build admin ID set (owner + teachers)
    # admin_ids already contains owner and teacher IDs
    sync_group_membership_cached(group_obj, to_add_ids, admin_ids)

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
        ext_id = create_thread('group', group_name, f"Class group for {group_name}")
        if ext_id:
            group_obj = Group.objects.create(
                name=group_name,
                session=session,
                grade=grade,
                section=section,
                is_broadcast=False,
                external_id=ext_id
            )
        else:
            logger.error(f"Could not create class group on platform for {group_name}")
            return None
    else:
        # Check if name needs updating
        if group_obj.name != group_name:
            if group_obj.external_id:
                update_thread(group_obj.external_id, group_name)
            group_obj.name = group_name
            group_obj.save()
            
        # Check if external_id actually exists on platform
        current_users = []
        if group_obj.external_id:
            try:
                current_users = get_thread_users(group_obj.external_id)
                if current_users is None:
                    group_obj.external_id = None
                    group_obj.save()
                    GroupMembershipCache.objects.filter(group=group_obj).delete()
                    current_users = []
            except Exception as e:
                logger.error(f"Failed to fetch thread users for class group {group_name}: {e}")
                return None

        # Recreate if external_id is missing or was reset above
        if not group_obj.external_id:
            try:
                ext_id = create_thread('group', group_name, f"Class group for {group_name}")
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
    student_sessions = StudentSession.objects.filter(session=session, grade=grade, section=section, status=True)
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
        users_map = get_platform_users_map(all_emails, all_phones)
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
    for t_user in teaching_users:
        teacher_obj = Teacher.objects.filter(teacher=t_user).first()
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
                teacher_obj.save()
                
        if ext_id:
            to_add_ids.append(ext_id)
            admin_ids.add(ext_id)

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
    sync_group_membership_cached(group_obj, to_add_ids, admin_ids)

    return group_obj
