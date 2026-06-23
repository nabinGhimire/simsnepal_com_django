import logging
from django.db.models import Q
from sms.models import Group, Teacher, StudentSession, TeacherSubjectAccess, Section, SchoolGrade
from sms.hamro import create_thread, add_users_to_thread_batch, lookup_hamro_users_batch

logger = logging.getLogger(__name__)

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

def get_platform_users_map(emails, phones):
    """Perform batch lookup for given list of emails and phones, returning a lookup map."""
    emails = list(filter(None, set(emails)))
    phones = list(filter(None, set(phones)))
    
    if not emails and not phones:
        return {}
        
    return lookup_hamro_users_batch(emails=emails, phones=phones)

def sync_school_channel(school, session):
    """Ensure a school-wide channel exists and add all teachers and parents (batch mode)."""
    channel_name = school.name
    channel_group = Group.objects.filter(name=channel_name, session=session, is_broadcast=True).first()
    
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
    elif not channel_group.external_id:
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
    phones_to_lookup = [] # teacher model doesn't store phone directly on User usually, but we check if we have it
    
    # Gather all parents of active students in the school
    student_sessions = StudentSession.objects.filter(session=session, student__school=school, status=True)
    parent_emails = []
    parent_phones = []
    
    for ss in student_sessions:
        student = ss.student
        if student.fathers_email: parent_emails.append(student.fathers_email)
        if student.fathers_phone: parent_phones.append(str(student.fathers_phone))
        if student.mothers_email: parent_emails.append(student.mothers_email)
        if student.mothers_phone: parent_phones.append(str(student.mothers_phone))
        if student.guardian_email: parent_emails.append(student.guardian_email)
        if student.guardian_phone: parent_phones.append(str(student.guardian_phone))

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
        
        if not ext_id and t_user.email in users_map:
            ext_id = users_map[t_user.email]
            if teacher_obj:
                teacher_obj.external_id = ext_id
                teacher_obj.save()
                
        if ext_id:
            to_add_ids.append(ext_id)

    # Collect parent external IDs
    for email in parent_emails:
        if email in users_map:
            to_add_ids.append(users_map[email])
    for phone in parent_phones:
        if phone in users_map:
            to_add_ids.append(users_map[phone])

    # Batch add all to channel
    if to_add_ids:
        add_users_to_thread_batch(channel_group.external_id, to_add_ids)
        
    return channel_group

def sync_teachers_group(school, session):
    """Ensure a teachers-only discussion group exists and populate with all teachers (batch mode)."""
    group_name = f"{school.name} Teachers {session.year}"
    group_obj = Group.objects.filter(name=group_name, session=session, is_broadcast=False, grade=None, section=None).first()
    
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
    elif not group_obj.external_id:
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
    users_map = get_platform_users_map(emails_to_lookup, [])

    to_add_ids = []
    for t_user in teacher_users:
        teacher_obj = Teacher.objects.filter(teacher=t_user).first()
        ext_id = teacher_obj.external_id if teacher_obj else None
        
        if not ext_id and t_user.email in users_map:
            ext_id = users_map[t_user.email]
            if teacher_obj:
                teacher_obj.external_id = ext_id
                teacher_obj.save()
                
        if ext_id:
            to_add_ids.append(ext_id)

    if to_add_ids:
        add_users_to_thread_batch(group_obj.external_id, to_add_ids)
        
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
    group_obj = Group.objects.filter(name=group_name, session=session).first()
    
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
            return None
    elif not group_obj.external_id:
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

    # Get section parents
    student_sessions = StudentSession.objects.filter(session=session, grade=grade, section=section, status=True)
    parent_emails = []
    parent_phones = []
    
    for ss in student_sessions:
        student = ss.student
        if student.fathers_email: parent_emails.append(student.fathers_email)
        if student.fathers_phone: parent_phones.append(str(student.fathers_phone))
        if student.mothers_email: parent_emails.append(student.mothers_email)
        if student.mothers_phone: parent_phones.append(str(student.mothers_phone))
        if student.guardian_email: parent_emails.append(student.guardian_email)
        if student.guardian_phone: parent_phones.append(str(student.guardian_phone))

    # Batch lookup
    all_emails = list(set(teacher_emails + parent_emails))
    all_phones = list(set(parent_phones))
    users_map = get_platform_users_map(all_emails, all_phones)

    # Collect members
    to_add_ids = []
    
    # Section teachers
    for t_user in teaching_users:
        teacher_obj = Teacher.objects.filter(teacher=t_user).first()
        ext_id = teacher_obj.external_id if teacher_obj else None
        
        if not ext_id and t_user.email in users_map:
            ext_id = users_map[t_user.email]
            if teacher_obj:
                teacher_obj.external_id = ext_id
                teacher_obj.save()
                
        if ext_id:
            to_add_ids.append(ext_id)

    # Section parents
    for email in parent_emails:
        if email in users_map:
            to_add_ids.append(users_map[email])
    for phone in parent_phones:
        if phone in users_map:
            to_add_ids.append(users_map[phone])

    if to_add_ids:
        add_users_to_thread_batch(group_obj.external_id, to_add_ids)
        
    return group_obj
