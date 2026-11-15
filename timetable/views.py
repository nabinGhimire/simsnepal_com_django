"""
timetable/views.py — Read-only timetable grid views.
"""

from __future__ import annotations

import datetime

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone

from sms.models import Section, SchoolBranch, EduSession, Subject

from .models import ScheduleProfile, TimetableVersion, TimetableEntry, TimetableException, GradeStructure, GradeStructurePeriod
from .services import resolve_week


def _user_branchuser(user):
    """Return the BranchUser for a Django user, following panel pattern."""
    if not user or not user.is_authenticated:
        return None
    try:
        from sms.models import BranchUser
        return BranchUser.objects.select_related('school').get(user=user)
    except BranchUser.DoesNotExist:
        return None
    except Exception:
        return None

def _user_sbu(user):
    """Return the SuperBranchUser for a Django user, or None."""
    if not user or not user.is_authenticated:
        return None
    try:
        from sms.models import SuperBranchUser
        return SuperBranchUser.objects.filter(user=user).first()
    except Exception:
        return None

def _is_school_admin(user, school) -> bool:
    """
    Return True if the user is an admin of the given school.

    Follows panel pattern: uses branchuser.admin_status for role management,
    not user.is_staff flag.

    Admin means:
      1. BranchUser.admin_status == True for this school
      2. SuperBranchUser owns the school (SchoolBranch.owner)
      3. SuperBranchUser added a BranchUser for that school (BranchUser.added_by)
    """
    if not user or not user.is_authenticated or school is None:
        return False
    try:
        from sms.models import BranchUser, SuperBranchUser

        # 1. BranchUser.admin_status for this school (panel pattern)
        bu = BranchUser.objects.filter(user=user, school=school).first()
        if bu and bu.admin_status:
            return True

        sbu = SuperBranchUser.objects.filter(user=user).first()

        # 2. SBU owns the school
        if sbu and school.owner_id == sbu.id:
            return True

        # 3. SBU added a BranchUser for this school
        if sbu and BranchUser.objects.filter(school=school, added_by=sbu).exists():
            return True
    except Exception:
        pass
    return False

def can_view_section(user, section_id: int) -> bool:
    """
    Permission helper for reading a section timetable.

    Follows panel pattern: uses branchuser.admin_status, not user.is_staff.
    """
    if not user or not user.is_authenticated:
        return False
    from sms.models import Section
    section = Section.objects.filter(pk=section_id).first()
    if not section:
        return False
    return _is_school_admin(user, section.school)


def can_view_section(user, section_id: int) -> bool:
    """
    Permission helper for reading a section timetable.

    Staff (is_staff) can view any section. Non-staff users can view sections
    in their own school — admin means the user's SuperBranchUser owns the
    school or added a BranchUser for it (i.e. the school was added by the user).
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    from sms.models import Section
    section = Section.objects.filter(pk=section_id).first()
    if not section:
        return False
    return _is_school_admin(user, section.school)


def _user_school_id(user) -> int | None:
    """Return the school_id associated with a user.

    Checks BranchUser first (staff/teacher), then falls back to
    SuperBranchUser school ownership (school owner/admin).
    """
    if not user or not user.is_authenticated:
        return None
    try:
        from sms.models import BranchUser, SchoolBranch, SuperBranchUser
        # 1. BranchUser association (staff / teacher)
        bu = BranchUser.objects.filter(user=user, status=True).first()
        if bu:
            return bu.school_id
        # 2. SuperBranchUser who owns a school (school owner / admin)
        sbu = SuperBranchUser.objects.filter(user=user).first()
        if sbu:
            owned = SchoolBranch.objects.filter(owner=sbu, status=True).first()
            if owned:
                return owned.id
    except Exception:
        pass
    return None


@login_required
def timetable_dashboard(request):
    """
    Timetable dashboard - entry point for the Timetable module.
    Shows a summary and links to section/teacher views.
    """
    user_school_id = _user_school_id(request.user)

    # Get school for display
    school = None
    if user_school_id:
        from sms.models import SchoolBranch
        school = SchoolBranch.objects.filter(pk=user_school_id).first()

    # Build base querysets scoped to the user's school
    version_qs = TimetableVersion.objects.all()
    entry_qs = TimetableEntry.objects.all()
    exception_qs = TimetableException.objects.all()
    if user_school_id:
        version_qs = version_qs.filter(school_id=user_school_id)
        entry_qs = entry_qs.filter(section__school_id=user_school_id)
        exception_qs = exception_qs.filter(school_id=user_school_id)

    version_count = version_qs.count()
    entry_count = entry_qs.count()
    exception_count = exception_qs.filter(archived_at__isnull=True).count()

    # Sections for quick access cards
    sections = Section.objects.none()
    if user_school_id:
        sections = Section.objects.filter(
            school_id=user_school_id
        ).order_by('section')[:10]

    # Teachers who have timetable entries (for quick access cards)
    from django.contrib.auth import get_user_model
    User = get_user_model()

    teachers_qs = User.objects.filter(
        timetable_entries__archived_at__isnull=True
    ).distinct()

    # Scope to teachers in the user's school
    if user_school_id:
        teachers_qs = teachers_qs.filter(
            timetable_entries__section__school_id=user_school_id
        )

    teachers = teachers_qs.order_by('username')[:10]

    # Today's timetable for each section (today's BS date)
    import nepali_datetime
    today_ad = timezone.now().date()
    today_bs = nepali_datetime.date.from_datetime_date(today_ad)
    today_bs_str = f"{today_bs.year:04d}-{today_bs.month:02d}-{today_bs.day:02d}"

    today_timetables = []
    if user_school_id:
        for section in sections:
            result = resolve_week(user_school_id, section.id, today_ad)
            # Get today's column (offset 0 = Monday of week, but we need today's specific day)
            today_offset = today_ad.weekday()  # 0=Mon, 6=Sun
            if today_offset >= 6:  # Sunday
                today_offset = 0  # Treat Sunday as first day for grid purposes
            today_cells = []
            grid = result['grid']
            for period_key, cell in grid.items():
                pid, day_ad = period_key
                if day_ad == today_ad:
                    if cell and not cell.get('is_span_continued'):
                        today_cells.append(cell)
            today_cells.sort(key=lambda c: c.get('period_id', 0))
            today_timetables.append({
                'section': section,
                'cells': today_cells,
            })

    context = {
        'school': school,
        'school_id': user_school_id,
        'version_count': version_count,
        'entry_count': entry_count,
        'exception_count': exception_count,
        'sections': sections,
        'teachers': teachers,
        'today_timetables': today_timetables,
        'today_bs_str': today_bs_str,
        'today_ad': today_ad.isoformat(),
    }
    return render(request, 'timetable/dashboard.html', context)


@login_required
def section_list(request):
    """
    List of sections for the user's school, with links to their timetable grids.
    """
    user_school_id = _user_school_id(request.user)

    sections_qs = Section.objects.select_related('grade', 'school').all()
    if user_school_id:
        sections_qs = sections_qs.filter(school_id=user_school_id)

    sections = sections_qs.order_by('grade__grade_name', 'section')

    context = {
        'school_id': user_school_id,
        'sections': sections,
    }
    return render(request, 'timetable/section_list.html', context)


@login_required
def teacher_list(request):
    """
    List of teachers in the user's school who can have timetable grids.

    Follows the same school-scoping pattern as panel/print_teachers:
    teachers are filtered by their BranchUser's school.
    """
    user_school_id = _user_school_id(request.user)

    from sms.models import Teacher, BranchUser

    # Get user IDs for this school's BranchUsers
    school_user_ids = BranchUser.objects.filter(
        school_id=user_school_id, status=True
    ).values_list('user_id', flat=True) if user_school_id else []

    teachers_qs = Teacher.objects.select_related('teacher').filter(
        teacher_id__in=school_user_ids
    ) if school_user_ids else Teacher.objects.none()

    teachers = teachers_qs.order_by('teacher__username')

    context = {
        'school_id': user_school_id,
        'teachers': teachers,
    }
    return render(request, 'timetable/teacher_list.html', context)


def section_grid(request, section_id: int):
    """
    Week-view grid for a section.

    GET /timetable/section/<int:section_id/?week=YYYY-MM-DD (BS)
    """
    section = get_object_or_404(Section, pk=section_id)

    # Permission guard.
    if not can_view_section(request.user, section_id):
        raise PermissionDenied

    # Multi-tenant isolation: users cannot view sections outside their own school
    # (G8: return 404, not 403, to not leak existence).
    # Staff bypass school scoping; non-staff must be school admin of the section's school.
    if not request.user.is_staff and not _is_school_admin(request.user, section.school):
        raise Http404

    school_id = section.school_id

    # Determine week start (Monday) from ?week= param (BS string) or current week.
    week_start_ad = _resolve_week_start(request)

    result = resolve_week(school_id, section_id, week_start_ad)

    # Build per-period row data with cells first.
    profile = _get_profile(section)
    if profile is not None:
        periods = list(
            profile.periods.filter(period_type='class').order_by('sequence')
        )
    else:
        periods = []
    period_list = []
    for p in periods:
        row = {
            'period': p,
            'cells': [],
        }
        for offset in range(6):
            day_ad = week_start_ad + datetime.timedelta(days=offset)
            cell = result['grid'].get((p.id, day_ad))
            if cell:
                cell = dict(cell)  # copy to avoid mutating cached grid
                cell['day_ad'] = day_ad
            row['cells'].append(cell)
        period_list.append(row)

    # Compute rowspans for span_continued cells (template renders rowspan attr).
    span_rowspans = _compute_span_rowspans(period_list, week_start_ad)

    # Apply rowspans to cells.
    for row in period_list:
        period = row['period']
        for offset in range(6):
            day_ad = week_start_ad + datetime.timedelta(days=offset)
            cell = row['cells'][offset]
            if cell:
                cell['rowspan'] = span_rowspans.get((period.id, day_ad), 1)

    # Exceptions affecting this section this week (for "Changes this week" list).
    exceptions_in_week = _exceptions_in_week(school_id, section_id, week_start_ad)

    # Summary card counts
    base_count = 0
    exception_count = 0
    for row in period_list:
        for cell in row['cells']:
            if cell and not cell.get('is_span_continued'):
                if cell.get('source') == 'exception':
                    exception_count += 1
                elif cell.get('source') != 'cancelled':
                    base_count += 1
    exception_count = len(exceptions_in_week)

    context = {
        'section': section,
        'school_id': school_id,
        'profile': profile,
        'period_list': period_list,
        'span_rowspans': span_rowspans,
        'week_start_bs': result['week_start_bs'],
        'week_end_bs': result['week_end_bs'],
        'week_start_ad': result['week_start_ad'],
        'week_end_ad': result['week_end_ad'],
        'days': _build_days(week_start_ad),
        'prev_week_bs': _bs_offset(week_start_ad, -7),
        'next_week_bs': _bs_offset(week_start_ad, 7),
        'errors': result['errors'],
        'exceptions_in_week': exceptions_in_week,
        'base_count': base_count,
        'exception_count': exception_count,
    }
    return render(request, 'timetable/grid.html', context)


@login_required
def teacher_grid(request, teacher_id: int):
    """
    Week-view grid grouped by section for a teacher.

    GET /timetable/teacher/<int:teacher_id>/?week=YYYY-MM-DD (BS)

    ``teacher_id`` is the ``sms.Teacher`` primary key.
    """
    from sms.models import Teacher
    teacher_obj = get_object_or_404(Teacher, pk=teacher_id)
    teacher = teacher_obj.teacher  # the Django User

    # Find all sections this teacher appears in (via TimetableEntry).
    teacher_sections = Section.objects.filter(
        timetable_entries__teacher_id=teacher.id,
        timetable_entries__archived_at__isnull=True,
    ).distinct()

    # Permission: staff can view any teacher. Non-staff can view their own
    # grid, or school admins can view teachers in their school.
    if not request.user.is_staff and request.user.pk != teacher.id:
        # Get user's school for school-scoping check
        user_school_id = _user_school_id(request.user)
        teacher_school_ids = set(s.school_id for s in teacher_sections)
        
        # If teacher has no sections, no school data to leak — allow access.
        if not teacher_sections:
            pass
        else:
            # Allow if user is school admin of any section's school
            is_admin_of_section_school = any(
                _is_school_admin(request.user, s.school) for s in teacher_sections
            )
            
            # Allow if user's school matches any section's school (school-scoping)
            is_in_same_school = bool(
                user_school_id and user_school_id in teacher_school_ids
            )
            
            if not is_admin_of_section_school and not is_in_same_school:
                raise PermissionDenied

    week_start_ad = _resolve_week_start(request)

    sections = list(teacher_sections)

    section_grids = []
    for section in sections:
        school_id = section.school_id
        result = resolve_week(school_id, section_id=section.id, week_start_ad=week_start_ad)

        profile = _get_profile(section)
        if profile is not None:
            periods = list(
                profile.periods.filter(period_type='class').order_by('sequence')
            )
        else:
            periods = []
        period_list = []
        for p in periods:
            row = {'period': p, 'cells': []}
            for offset in range(6):
                day_ad = week_start_ad + datetime.timedelta(days=offset)
                cell = result['grid'].get((p.id, day_ad))
                if cell:
                    cell = dict(cell)
                    cell['day_ad'] = day_ad
                row['cells'].append(cell)
            period_list.append(row)

        span_rowspans = _compute_span_rowspans(period_list, week_start_ad)

        # Apply rowspans to cells.
        for row in period_list:
            period = row['period']
            for offset in range(6):
                day_ad = week_start_ad + datetime.timedelta(days=offset)
                cell = row['cells'][offset]
                if cell:
                    cell['rowspan'] = span_rowspans.get((period.id, day_ad), 1)

        section_grids.append({
            'section': section,
            'school_id': school_id,
            'profile': profile,
            'period_list': period_list,
            'span_rowspans': span_rowspans,
            'week_start_bs': result['week_start_bs'],
            'week_end_bs': result['week_end_bs'],
        })

    context = {
        'teacher': teacher,
        'section_grids': section_grids,
        'week_start_bs': section_grids[0]['week_start_bs'] if section_grids else '',
        'week_end_bs': section_grids[0]['week_end_bs'] if section_grids else '',
        'days': _build_days(week_start_ad),
        'prev_week_bs': _bs_offset(week_start_ad, -7),
        'next_week_bs': _bs_offset(week_start_ad, 7),
        'errors': [],
    }
    return render(request, 'timetable/teacher_grid.html', context)


# ── Management views ──────────────────────────────────────────────────────────

def _require_school_admin(request):
    """Return the user's school_id if they are a school admin, else None.

    Follows panel pattern: uses branchuser.admin_status for role management.
    """
    if not request.user.is_authenticated:
        return None
    from sms.models import BranchUser, SuperBranchUser, SchoolBranch

    # Panel pattern: check branchuser.admin_status
    bu = BranchUser.objects.select_related('school').filter(user=request.user).first()
    if bu and bu.admin_status:
        return bu.school_id

    sbu = SuperBranchUser.objects.filter(user=request.user).first()
    if sbu:
        # SBU owns the school
        owned = SchoolBranch.objects.filter(owner=sbu, status=True).first()
        if owned:
            return owned.id
        # SBU added a BranchUser for this school
        bu2 = BranchUser.objects.filter(added_by=sbu).first()
        if bu2:
            return bu2.school_id
    return None


@login_required
def timetable_management(request):
    """
    Timetable management dashboard — configure periods, versions, entries.
    """
    school_id = _require_school_admin(request)
    if school_id is None:
        return HttpResponse('Admin access required. <a href="/">Home</a>')

    from sms.models import SchoolBranch, EduSession
    school = SchoolBranch.objects.filter(pk=school_id).first()

    profiles = ScheduleProfile.objects.filter(school_id=school_id)
    versions = TimetableVersion.objects.filter(school_id=school_id).order_by('-version_no')
    sections = Section.objects.filter(school_id=school_id).order_by('grade__grade_name', 'section')[:20]
    current_session = EduSession.objects.filter(status=True).order_by('-year').first()

    context = {
        'school': school,
        'school_id': school_id,
        'profiles': profiles,
        'versions': versions,
        'sections': sections,
        'current_session': current_session,
    }
    return render(request, 'timetable/management.html', context)


@login_required
def profile_list(request):
    """List schedule profiles for the user's school."""
    school_id = _require_school_admin(request)
    if school_id is None:
        return HttpResponse('Admin access required. <a href="/">Home</a>')

    profiles = ScheduleProfile.objects.filter(school_id=school_id).prefetch_related('periods')
    context = {
        'school_id': school_id,
        'profiles': profiles,
    }
    return render(request, 'timetable/profile_list.html', context)


@login_required
def profile_add(request):
    """Add a new schedule profile (period grid) for the school."""
    school_id = _require_school_admin(request)
    if school_id is None:
        return HttpResponse('Admin access required. <a href="/">Home</a>')

    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        if name:
            ScheduleProfile.objects.create(school_id=school_id, name=name, is_active=True)
            from django.contrib import messages
            messages.success(request, f'Schedule profile "{name}" created.')
            return redirect('timetable:profile_list')
        from django.contrib import messages
        messages.error(request, 'Profile name is required.')

    context = {'school_id': school_id}
    return render(request, 'timetable/profile_add.html', context)


@login_required
def profile_periods(request, profile_id):
    """View and manage periods within a schedule profile."""
    school_id = _require_school_admin(request)
    if school_id is None:
        return HttpResponse('Admin access required. <a href="/">Home</a>')

    profile = get_object_or_404(ScheduleProfile, pk=profile_id, school_id=school_id)
    periods = profile.periods.order_by('sequence')

    context = {
        'school_id': school_id,
        'profile': profile,
        'periods': periods,
    }
    return render(request, 'timetable/profile_periods.html', context)


@login_required
def version_list(request):
    """List timetable versions for the user's school."""
    school_id = _require_school_admin(request)
    if school_id is None:
        return HttpResponse('Admin access required. <a href="/">Home</a>')

    versions = TimetableVersion.objects.filter(school_id=school_id).order_by('-version_no')
    context = {
        'school_id': school_id,
        'versions': versions,
    }
    return render(request, 'timetable/version_list.html', context)


@login_required
def version_add(request):
    """Create a new timetable version for the school."""
    school_id = _require_school_admin(request)
    if school_id is None:
        return HttpResponse('Admin access required. <a href="/">Home</a>')

    from sms.models import EduSession
    sessions = EduSession.objects.all().order_by('-year')

    if request.method == 'POST':
        version_no = request.POST.get('version_no')
        academic_year_id = request.POST.get('academic_year')
        effective_from = request.POST.get('effective_from')
        status = request.POST.get('status', 'draft')
        change_note = (request.POST.get('change_note') or '').strip()

        if not version_no or not academic_year_id or not effective_from:
            from django.contrib import messages
            messages.error(request, 'All required fields must be filled.')
        else:
            try:
                version_no = int(version_no)
                version = TimetableVersion(
                    school_id=school_id,
                    academic_year_id=academic_year_id,
                    version_no=version_no,
                    effective_from=effective_from,
                    status=status,
                    created_by=request.user,
                    change_note=change_note,
                )
                version.save()
                if status == 'published':
                    version.published_at = datetime.datetime.now()
                    version.published_by = request.user
                    version.save()
                from django.contrib import messages
                messages.success(request, f'Timetable version v{version_no} created.')
                return redirect('timetable:version_list')
            except (ValueError, Exception) as e:
                from django.contrib import messages
                messages.error(request, f'Error creating version: {e}')

    context = {
        'school_id': school_id,
        'sessions': sessions,
    }
    return render(request, 'timetable/version_add.html', context)


@login_required
def entry_list(request, section_id):
    """List timetable entries for a section."""
    school_id = _require_school_admin(request)
    if school_id is None:
        return HttpResponse('Admin access required. <a href="/">Home</a>')

    section = get_object_or_404(Section, pk=section_id)
    if section.school_id != school_id and not request.user.is_staff:
        return HttpResponse('Section not in your school. <a href="/">Home</a>')

    versions = TimetableVersion.objects.filter(school_id=school_id, status='published')
    entries = TimetableEntry.objects.filter(section=section, archived_at__isnull=True).select_related(
        'version', 'period', 'subject', 'teacher'
    ).order_by('-created_at')

    context = {
        'school_id': school_id,
        'section': section,
        'versions': versions,
        'entries': entries,
    }
    return render(request, 'timetable/entry_list.html', context)


@login_required
def entry_add(request, section_id):
    """Add a timetable entry for a section."""
    school_id = _require_school_admin(request)
    if school_id is None:
        return HttpResponse('Admin access required. <a href="/">Home</a>')

    section = get_object_or_404(Section, pk=section_id)
    if section.school_id != school_id and not request.user.is_staff:
        return HttpResponse('Section not in your school. <a href="/">Home</a>')

    from sms.models import Subject

    versions = TimetableVersion.objects.filter(school_id=school_id, status='published')
    profile = _get_profile(section)
    periods = profile.periods.filter(period_type='class').order_by('sequence') if profile else []
    subjects = Subject.objects.filter(branch_id=school_id, grade=section.grade)

    if request.method == 'POST':
        version_id = request.POST.get('version')
        period_id = request.POST.get('period')
        subject_id = request.POST.get('subject')
        teacher_id = request.POST.get('teacher')
        recurrence = request.POST.get('recurrence', 'weekly')
        days_of_week = request.POST.get('days_of_week')
        period_span = int(request.POST.get('period_span', 1) or 1)
        room_id = request.POST.get('room_id') or None

        if not version_id or not period_id or not subject_id or not teacher_id:
            from django.contrib import messages
            messages.error(request, 'All required fields must be filled.')
        else:
            try:
                entry = TimetableEntry(
                    version_id=version_id,
                    section=section,
                    period_id=period_id,
                    subject_id=subject_id,
                    teacher_id=teacher_id,
                    recurrence=recurrence,
                    days_of_week=int(days_of_week) if days_of_week else None,
                    period_span=period_span,
                    room_id=room_id,
                    created_by=request.user,
                )
                entry.save()
                from django.contrib import messages
                messages.success(request, 'Timetable entry created.')
                return redirect('timetable:entry_list', section_id=section_id)
            except Exception as e:
                from django.contrib import messages
                messages.error(request, f'Error creating entry: {e}')

    from sms.models import Teacher, BranchUser

    # Get user IDs for this school's BranchUsers
    school_user_ids = BranchUser.objects.filter(
        school_id=school_id, status=True
    ).values_list('user_id', flat=True)

    teachers_qs = Teacher.objects.select_related('teacher').filter(
        teacher_id__in=school_user_ids
    ) if school_user_ids else Teacher.objects.none()

    teachers = teachers_qs.order_by('teacher__username')[:50]

    context = {
        'school_id': school_id,
        'section': section,
        'versions': versions,
        'periods': periods,
        'subjects': subjects,
        'teachers': teachers,
        'profile': profile,
    }
    return render(request, 'timetable/entry_add.html', context)


@login_required
def exception_list(request):
    """List timetable exceptions for the user's school."""
    school_id = _require_school_admin(request)
    if school_id is None:
        return HttpResponse('Admin access required. <a href="/">Home</a>')

    exceptions = TimetableException.objects.filter(
        school_id=school_id, archived_at__isnull=True
    ).select_related('created_by').order_by('-created_at')

    context = {
        'school_id': school_id,
        'exceptions': exceptions,
    }
    return render(request, 'timetable/exception_list.html', context)


@login_required
def exception_add(request):
    """Create a new timetable exception."""
    school_id = _require_school_admin(request)
    if school_id is None:
        return HttpResponse('Admin access required. <a href="/">Home</a>')

    from sms.models import Section

    sections = Section.objects.filter(school_id=school_id)

    if request.method == 'POST':
        kind = request.POST.get('kind')
        scope = request.POST.get('scope', 'section')
        scope_id = request.POST.get('scope_id')
        date_from = request.POST.get('date_from')
        date_to = request.POST.get('date_to')
        period_id = request.POST.get('period_id') or None
        subject_id = request.POST.get('subject_id') or None
        teacher_id = request.POST.get('teacher_id') or None
        room_id = request.POST.get('room_id') or None
        reason = request.POST.get('reason', '').strip()
        days_of_week = request.POST.get('days_of_week') or None

        if not kind or not date_from or not date_to or not reason:
            from django.contrib import messages
            messages.error(request, 'Kind, date range, and reason are required.')
        else:
            try:
                exc = TimetableException(
                    school_id=school_id,
                    academic_year_id=EduSession.objects.filter(status=True).order_by('-year').first().id,
                    date_from=date_from,
                    date_to=date_to,
                    kind=kind,
                    scope=scope,
                    scope_id=int(scope_id) if scope_id else 0,
                    period_id=int(period_id) if period_id else None,
                    subject_id=int(subject_id) if subject_id else None,
                    teacher_id=int(teacher_id) if teacher_id else None,
                    room_id=int(room_id) if room_id else None,
                    reason=reason,
                    days_of_week=int(days_of_week) if days_of_week else None,
                    created_by=request.user,
                )
                exc.save()
                from django.contrib import messages
                messages.success(request, f'Exception "{kind}" created.')
                return redirect('timetable:exception_list')
            except Exception as e:
                from django.contrib import messages
                messages.error(request, f'Error creating exception: {e}')

    from sms.models import EduSession
    current_session = EduSession.objects.filter(status=True).order_by('-year').first()

    context = {
        'school_id': school_id,
        'sections': sections,
        'current_session': current_session,
    }
    return render(request, 'timetable/exception_add.html', context)


@login_required
def period_add(request, profile_id):
    """Add a period (time slot) to a schedule profile."""
    school_id = _require_school_admin(request)
    if school_id is None:
        return HttpResponse('Admin access required. <a href="/">Home</a>')

    profile = get_object_or_404(ScheduleProfile, pk=profile_id, school_id=school_id)

    if request.method == 'POST':
        label = (request.POST.get('label') or '').strip()
        sequence = int(request.POST.get('sequence') or 0)
        shift = request.POST.get('shift', 'morning')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        period_type = request.POST.get('period_type', 'class')

        if not label or not start_time or not end_time:
            from django.contrib import messages
            messages.error(request, 'Label, start time, and end time are required.')
        else:
            try:
                ScheduleProfilePeriod.objects.create(
                    profile=profile,
                    sequence=sequence,
                    shift=shift,
                    start_time=start_time,
                    end_time=end_time,
                    period_type=period_type,
                    label=label,
                )
                from django.contrib import messages
                messages.success(request, f'Period "{label}" added to {profile.name}.')
                return redirect('timetable:profile_periods', profile_id=profile_id)
            except Exception as e:
                from django.contrib import messages
                messages.error(request, f'Error creating period: {e}')

    context = {
        'school_id': school_id,
        'profile': profile,
    }
    return render(request, 'timetable/period_add.html', context)


@login_required
def holiday_list(request):
    """List whole-day exceptions (holidays) for the user's school."""
    school_id = _require_school_admin(request)
    if school_id is None:
        return HttpResponse('Admin access required. <a href="/">Home</a>')

    holidays = TimetableException.objects.filter(
        school_id=school_id, kind='whole_day', archived_at__isnull=True
    ).select_related('created_by').order_by('-date_from')

    context = {
        'school_id': school_id,
        'holidays': holidays,
    }
    return render(request, 'timetable/holiday_list.html', context)


@login_required
def holiday_add(request):
    """Create a whole-day holiday exception for the school."""
    school_id = _require_school_admin(request)
    if school_id is None:
        return HttpResponse('Admin access required. <a href="/">Home</a>')

    from sms.models import EduSession

    current_session = EduSession.objects.filter(status=True).order_by('-year').first()

    if request.method == 'POST':
        date_from = request.POST.get('date_from')
        date_to = request.POST.get('date_to')
        reason = request.POST.get('reason', '').strip()
        scope = request.POST.get('scope', 'school')
        scope_id = request.POST.get('scope_id') or school_id

        if not date_from or not date_to or not reason:
            from django.contrib import messages
            messages.error(request, 'Date range and reason are required.')
        else:
            try:
                exc = TimetableException(
                    school_id=school_id,
                    academic_year_id=current_session.id if current_session else 1,
                    date_from=date_from,
                    date_to=date_to,
                    kind='whole_day',
                    scope=scope,
                    scope_id=int(scope_id),
                    reason=reason,
                    days_of_week=None,
                    created_by=request.user,
                )
                exc.save()
                from django.contrib import messages
                messages.success(request, f'Holiday "{reason}" created.')
                return redirect('timetable:holiday_list')
            except Exception as e:
                from django.contrib import messages
                messages.error(request, f'Error creating holiday: {e}')

    from sms.models import Section
    sections = Section.objects.filter(school_id=school_id)

    context = {
        'school_id': school_id,
        'sections': sections,
        'current_session': current_session,
    }
    return render(request, 'timetable/holiday_add.html', context)


# ── Grade Structure views ──────────────────────────────────────────────────

@login_required
def grade_structure_list(request):
    """List grade structures for the user's school."""
    school_id = _require_school_admin(request)
    if school_id is None:
        return HttpResponse('Admin access required. <a href="/">Home</a>')

    from sms.models import SchoolGrade
    grades = SchoolGrade.objects.filter(school_id=school_id, active=True).order_by('grade_weight')
    structures = GradeStructure.objects.filter(school_id=school_id).select_related('grade')

    # Group structures by grade
    grade_structures = {}
    for grade in grades:
        grade_structures[grade.id] = {
            'grade': grade,
            'structures': [s for s in structures if s.grade_id == grade.id],
        }

    context = {
        'school_id': school_id,
        'grade_structures': grade_structures,
    }
    return render(request, 'timetable/grade_structure_list.html', context)


@login_required
def grade_structure_add(request):
    """Add a new grade structure (standard daily schedule template)."""
    school_id = _require_school_admin(request)
    if school_id is None:
        return HttpResponse('Admin access required. <a href="/">Home</a>')

    from sms.models import SchoolGrade, Section
    grades = SchoolGrade.objects.filter(school_id=school_id, active=True).order_by('grade_weight')
    sections = Section.objects.filter(school_id=school_id).order_by('grade__grade_name', 'section')

    if request.method == 'POST':
        grade_id = request.POST.get('grade')
        section_id = request.POST.get('section') or None
        shift = request.POST.get('shift')
        name = (request.POST.get('name') or '').strip()
        period_duration = int(request.POST.get('period_duration', 40) or 40)
        break_after_periods = int(request.POST.get('break_after_periods', 4) or 4)

        if not grade_id or not shift:
            from django.contrib import messages
            messages.error(request, 'Grade and shift are required.')
        else:
            try:
                gs = GradeStructure.objects.create(
                    school_id=school_id,
                    grade_id=grade_id,
                    section_id=section_id,
                    shift=shift,
                    name=name,
                    period_duration=period_duration,
                    break_after_periods=break_after_periods,
                )
                from django.contrib import messages
                messages.success(request, f'Structure "{gs}" created. Now add periods to it.')
                return redirect('timetable:grade_structure_periods', structure_id=gs.id)
            except Exception as e:
                from django.contrib import messages
                messages.error(request, f'Error creating structure: {e}')

    context = {
        'school_id': school_id,
        'grades': grades,
        'sections': sections,
    }
    return render(request, 'timetable/grade_structure_add.html', context)


@login_required
def grade_structure_periods(request, structure_id):
    """View and manage periods within a grade structure."""
    school_id = _require_school_admin(request)
    if school_id is None:
        return HttpResponse('Admin access required. <a href="/">Home</a>')

    structure = get_object_or_404(GradeStructure, pk=structure_id, school_id=school_id)
    periods = structure.structure_periods.filter(is_active=True).order_by('sequence')

    context = {
        'school_id': school_id,
        'structure': structure,
        'periods': periods,
    }
    return render(request, 'timetable/grade_structure_periods.html', context)


@login_required
def grade_structure_period_add(request, structure_id):
    """Add a period to a grade structure."""
    school_id = _require_school_admin(request)
    if school_id is None:
        return HttpResponse('Admin access required. <a href="/">Home</a>')

    structure = get_object_or_404(GradeStructure, pk=structure_id, school_id=school_id)

    if request.method == 'POST':
        sequence = int(request.POST.get('sequence') or 0)
        period_type = request.POST.get('period_type', 'class')
        label = (request.POST.get('label') or '').strip()
        duration_minutes = int(request.POST.get('duration_minutes', structure.period_duration) or structure.period_duration)
        days_of_week = request.POST.get('days_of_week') or None

        if not label:
            from django.contrib import messages
            messages.error(request, 'Label is required.')
        else:
            try:
                GradeStructurePeriod.objects.create(
                    structure=structure,
                    sequence=sequence,
                    period_type=period_type,
                    label=label,
                    duration_minutes=duration_minutes,
                    days_of_week=int(days_of_week) if days_of_week else None,
                )
                from django.contrib import messages
                messages.success(request, f'Period "{label}" added to {structure}.')
                return redirect('timetable:grade_structure_periods', structure_id=structure_id)
            except Exception as e:
                from django.contrib import messages
                messages.error(request, f'Error creating period: {e}')

    context = {
        'school_id': school_id,
        'structure': structure,
    }
    return render(request, 'timetable/grade_structure_period_add.html', context)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_week_start(request) -> datetime.date:
    """Parse ?week= (BS 'YYYY-MM-DD') and return Monday of that week as AD date.

    Falls back to current week's Monday if param missing or invalid.
    """
    week_bs = request.GET.get('week')
    if week_bs:
        try:
            import nepali_datetime
            y, m, d = (int(p) for p in week_bs.split('-'))
            bs_date = nepali_datetime.date(y, m, d)
            ad_date = bs_date.to_datetime_date()
            # Roll back to Monday
            monday_ad = ad_date - datetime.timedelta(days=ad_date.weekday())
            return monday_ad
        except (ValueError, TypeError):
            pass
    today = timezone.now().date()
    return today - datetime.timedelta(days=today.weekday())


def _bs_offset(ad_date: datetime.date, days: int) -> str:
    """Return BS string for ad_date + days offset (for prev/next week links)."""
    import nepali_datetime
    target = ad_date + datetime.timedelta(days=days)
    bs = nepali_datetime.date.from_datetime_date(target)
    return f"{bs.year:04d}-{bs.month:02d}-{bs.day:02d}"


def _build_days(week_start_ad: datetime.date) -> list:
    """Build day header info for Mon..Sat."""
    import nepali_datetime
    days = []
    for offset in range(6):
        day_ad = week_start_ad + datetime.timedelta(days=offset)
        bs = nepali_datetime.date.from_datetime_date(day_ad)
        days.append({
            'ad': day_ad,
            'bs': f"{bs.year:04d}-{bs.month:02d}-{bs.day:02d}",
            'name': day_ad.strftime('%a'),
            'is_weekend': day_ad.weekday() >= 5,
        })
    return days


def _get_profile(section: Section):
    """Return the ScheduleProfile for the section's school, or None."""
    from .models import ScheduleProfile
    return (
        ScheduleProfile.objects
        .filter(school_id=section.school_id, is_active=True)
        .first()
    )


def _compute_span_rowspans(period_list: list, week_start_ad: datetime.date) -> dict:
    """
    Compute rowspan for span cells.

    Returns dict keyed by (period_id, date_ad) → rowspan int.
    For a span_group occupying consecutive periods on one day, only the
    first cell (is_span_start) gets the rowspan; continued cells are
    hidden by the template.
    """
    # Build index: (period_id, date_ad) -> cell
    cell_index: dict[tuple[int, datetime.date], dict] = {}
    for row in period_list:
        period = row['period']
        for offset in range(6):
            day_ad = week_start_ad + datetime.timedelta(days=offset)
            cell = row['cells'][offset]
            if cell:
                cell_index[(period.id, day_ad)] = cell

    rowspans: dict[tuple[int, datetime.date], int] = {}
    for (period_id, day_ad), cell in cell_index.items():
        if cell.get('is_span_start') and cell.get('span_group_id'):
            span_group_id = cell['span_group_id']
            rowspan = 1
            # Count continued cells with same span_group_id on the SAME day,
            # in subsequent period rows (periods are ordered by sequence).
            next_offset = None
            # Find this period's sequence position to know "next" periods.
            # Simpler: iterate all cells with same day_ad and higher period.
            for (pid, d_ad), c in cell_index.items():
                if d_ad == day_ad and c.get('is_span_continued') and c.get('span_group_id') == span_group_id:
                    rowspan += 1
            rowspans[(period_id, day_ad)] = rowspan
    return rowspans


def _exceptions_in_week(school_id: int, section_id: int, week_start_ad: datetime.date):
    """List exceptions affecting this section in the week, for 'Changes this week'."""
    from .services import _ad_to_bs
    week_start_bs = _ad_to_bs(week_start_ad)
    week_end_ad = week_start_ad + datetime.timedelta(days=5)
    week_end_bs = _ad_to_bs(week_end_ad)

    return list(
        TimetableException.objects
        .filter(
            school_id=school_id,
            archived_at__isnull=True,
            locked_at__isnull=True,
            date_from__lte=week_end_bs,
            date_to__gte=week_start_bs,
        )
        .filter(scope='section', scope_id=section_id)
        .select_related('created_by')
        .order_by('date_from', 'kind')
    )


# ── School-Level Timetable Settings Views ────────────────────────────────────

@login_required
def school_settings(request):
    """View school-level timetable settings (shifts, class times, etc.)."""
    school_id = _require_school_admin(request)
    if school_id is None:
        return HttpResponse('Admin access required. <a href="/">Home</a>')

    from sms.models import SchoolBranch
    school = SchoolBranch.objects.filter(pk=school_id).first()

    settings_obj, created = TimetableSchoolSettings.objects.get_or_create(
        school_id=school_id,
        defaults={
            'shift_morning_start': '06:00',
            'shift_morning_end': '09:00',
            'shift_day_start': '10:00',
            'shift_day_end': '15:20',
            'shift_evening_start': '17:00',
            'shift_evening_end': '19:00',
            'default_period_duration': 40,
            'break_after_periods': 4,
            'break_duration_minutes': 15,
            'weekend_days': 64,  # Sunday
        }
    )

    context = {
        'school': school,
        'school_id': school_id,
        'settings': settings_obj,
    }
    return render(request, 'timetable/school_settings.html', context)


@login_required
def school_settings_edit(request):
    """Edit school-level timetable settings."""
    school_id = _require_school_admin(request)
    if school_id is None:
        return HttpResponse('Admin access required. <a href="/">Home</a>')

    from sms.models import SchoolBranch
    school = SchoolBranch.objects.filter(pk=school_id).first()

    settings_obj, created = TimetableSchoolSettings.objects.get_or_create(
        school_id=school_id,
        defaults={
            'shift_morning_start': '06:00',
            'shift_morning_end': '09:00',
            'shift_day_start': '10:00',
            'shift_day_end': '15:20',
            'shift_evening_start': '17:00',
            'shift_evening_end': '19:00',
            'default_period_duration': 40,
            'break_after_periods': 4,
            'break_duration_minutes': 15,
            'weekend_days': 64,
        }
    )

    if request.method == 'POST':
        shift_morning_start = request.POST.get('shift_morning_start') or None
        shift_morning_end = request.POST.get('shift_morning_end') or None
        shift_day_start = request.POST.get('shift_day_start') or None
        shift_day_end = request.POST.get('shift_day_end') or None
        shift_evening_start = request.POST.get('shift_evening_start') or None
        shift_evening_end = request.POST.get('shift_evening_end') or None
        default_period_duration = int(request.POST.get('default_period_duration') or 40)
        break_after_periods = int(request.POST.get('break_after_periods') or 4)
        break_duration_minutes = int(request.POST.get('break_duration_minutes') or 15)
        weekend_days = int(request.POST.get('weekend_days') or 64)

        try:
            settings_obj.shift_morning_start = shift_morning_start
            settings_obj.shift_morning_end = shift_morning_end
            settings_obj.shift_day_start = shift_day_start
            settings_obj.shift_day_end = shift_day_end
            settings_obj.shift_evening_start = shift_evening_start
            settings_obj.shift_evening_end = shift_evening_end
            settings_obj.default_period_duration = default_period_duration
            settings_obj.break_after_periods = break_after_periods
            settings_obj.break_duration_minutes = break_duration_minutes
            settings_obj.weekend_days = weekend_days
            settings_obj.save()
            from django.contrib import messages
            messages.success(request, 'School timetable settings updated.')
            return redirect('timetable:school_settings')
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Error updating settings: {e}')

    context = {
        'school': school,
        'school_id': school_id,
        'settings': settings_obj,
    }
    return render(request, 'timetable/school_settings_edit.html', context)
