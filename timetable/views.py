"""
timetable/views.py — Read-only timetable grid views.
"""

from __future__ import annotations

import datetime

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from sms.models import Section

from .models import TimetableVersion, TimetableEntry, TimetableException
from .services import resolve_week


def can_view_section(user, section_id: int) -> bool:
    """
    Permission helper for reading a section timetable.

    Staff (is_staff) can view any section (subject to school scoping in the view).
    Teachers (is_staff=False) — stub returns False until webview teacher
    identity is wired later.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    # Stub: teachers cannot yet view via webview identity.
    return False


def _user_school_id(user) -> int | None:
    """Return the school_id associated with a staff user via BranchUser, or None."""
    if not user or not user.is_authenticated:
        return None
    try:
        from sms.models import BranchUser
        bu = BranchUser.objects.filter(user=user, status=True).first()
        if bu:
            return bu.school_id
    except Exception:
        pass
    return None


def timetable_dashboard(request):
    """
    Timetable dashboard - entry point for the Timetable module.
    Shows a summary and links to section/teacher views.
    """
    from django.shortcuts import render
    return render(request, 'timetable/dashboard.html')


def section_grid(request, section_id: int):
    """
    Week-view grid for a section.

    GET /timetable/section/<int:section_id/?week=YYYY-MM-DD (BS)
    """
    section = get_object_or_404(Section, pk=section_id)

    # Permission guard.
    if not can_view_section(request.user, section_id):
        raise PermissionDenied

    # Multi-tenant isolation: staff of school A cannot view school B's section
    # (G8: return 404, not 403, to not leak existence).
    if request.user.is_staff:
        user_school_id = _user_school_id(request.user)
        if user_school_id is not None and section.school_id != user_school_id:
            raise Http404

    school_id = section.school_id

    # Determine week start (Monday) from ?week= param (BS string) or current week.
    week_start_ad = _resolve_week_start(request)

    result = resolve_week(school_id, section_id, week_start_ad)

    # Build per-period row data with cells first.
    profile = _get_profile(section)
    periods = list(profile.periods.filter(period_type='class').order_by('sequence'))
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
    }
    return render(request, 'timetable/grid.html', context)


def teacher_grid(request, teacher_id: int):
    """
    Week-view grid grouped by section for a teacher.

    GET /timetable/teacher/<int:teacher_id>/?week=YYYY-MM-DD (BS)
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    teacher = get_object_or_404(User, pk=teacher_id)

    if not request.user.is_staff and request.user.pk != teacher_id:
        raise PermissionDenied

    week_start_ad = _resolve_week_start(request)

    # Find all sections this teacher appears in (via TimetableEntry).
    sections = list(
        Section.objects.filter(
            timetable_entries__teacher_id=teacher_id,
            timetable_entries__archived_at__isnull=True,
        ).distinct()
    )

    section_grids = []
    for section in sections:
        school_id = section.school_id
        result = resolve_week(school_id, section_id=section.id, week_start_ad=week_start_ad)

        profile = _get_profile(section)
        periods = list(profile.periods.filter(period_type='class').order_by('sequence'))
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
