import logging
import time
from django.db import transaction
from django.db.models import Q
from sms.models import Group, Teacher, StudentSession, TeacherSubjectAccess, Section, SchoolGrade, PlatformSetting
from sms.hamro import create_thread, add_users_to_thread_batch, lookup_hamro_users_batch, format_phone, get_thread_users, remove_user_from_thread

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
    if key.startswith('+'):
        key = key[1:]
    return key

def get_platform_users_map(emails, phones):
    """Perform batch lookup for given list of emails and phones, returning a lookup map with normalized keys."""
    emails = list(filter(None, set(emails)))
    phones = list(filter(None, set(phones)))
    
    if not emails and not phones:
        return {}
        
    raw_map = lookup_hamro_users_batch(emails=emails, phones=phones)
    normalized_map = {}
    for key, val in raw_map.items():
        if val:
            normalized_map[normalize_lookup_key(key)] = val
    return normalized_map

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
    channel_group = Group.objects.filter(session=session, is_broadcast=True).first()
    
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
            channel_group.name = channel_name
            channel_group.save()
            
        # Check if external_id actually exists on platform
        if channel_group.external_id:
            current_users = get_thread_users(channel_group.external_id)
            if current_users is None:
                channel_group.external_id = None
                channel_group.save()
                
        # Recreate if external_id is missing or was reset above
        if not channel_group.external_id:
            ext_id = create_thread('channel', channel_name, f"School channel for {channel_name}")
            if ext_id:
                channel_group.external_id = ext_id
                channel_group.save()
            else:
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
    users_map = get_platform_users_map(all_emails, all_phones)

    # Collect valid external IDs
    to_add_ids = []
    
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

    # Batch add all to channel
    if to_add_ids:
        add_users_to_thread_batch(channel_group.external_id, to_add_ids)
        
    # Remove stale users
    current_users = get_thread_users(channel_group.external_id)
    for u_id in current_users:
        if u_id not in to_add_ids:
            remove_user_from_thread(channel_group.external_id, u_id)
            
    return channel_group

def sync_teachers_group(school, session):
    """Ensure a teachers-only discussion group exists and populate with all teachers (batch mode)."""
    group_name = f"{school.name} Teachers"
    # Query by session, grade=None, section=None, is_broadcast=False to uniquely identify teachers group
    group_obj = Group.objects.filter(session=session, is_broadcast=False, grade=None, section=None).first()
    
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
            group_obj.name = group_name
            group_obj.save()
            
        # Check if external_id actually exists on platform
        if group_obj.external_id:
            current_users = get_thread_users(group_obj.external_id)
            if current_users is None:
                group_obj.external_id = None
                group_obj.save()
                
        # Recreate if external_id is missing or was reset above
        if not group_obj.external_id:
            ext_id = create_thread('group', group_name, f"Teachers discussion group for {school.name}")
            if ext_id:
                group_obj.external_id = ext_id
                group_obj.save()
            else:
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
    users_map = get_platform_users_map(emails_to_lookup, phones_to_lookup)

    to_add_ids = []
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

    to_add_ids = list(set(to_add_ids))

    if to_add_ids:
        add_users_to_thread_batch(group_obj.external_id, to_add_ids)
        
    # Remove stale users
    current_users = get_thread_users(group_obj.external_id)
    for u_id in current_users:
        if u_id not in to_add_ids:
            remove_user_from_thread(group_obj.external_id, u_id)
            
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
            group_obj.name = group_name
            group_obj.save()
            
        # Check if external_id actually exists on platform
        if group_obj.external_id:
            current_users = get_thread_users(group_obj.external_id)
            if current_users is None:
                group_obj.external_id = None
                group_obj.save()
                
        # Recreate if external_id is missing or was reset above
        if not group_obj.external_id:
            ext_id = create_thread('group', group_name, f"Class group for {group_name}")
            if ext_id:
                group_obj.external_id = ext_id
                group_obj.save()
            else:
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
    users_map = get_platform_users_map(all_emails, all_phones)

    # Collect members
    to_add_ids = []
    
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

    if to_add_ids:
        add_users_to_thread_batch(group_obj.external_id, to_add_ids)
        
    # Remove stale users
    current_users = get_thread_users(group_obj.external_id)
    for u_id in current_users:
        if u_id not in to_add_ids:
            remove_user_from_thread(group_obj.external_id, u_id)
            
    return group_obj
