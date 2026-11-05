"""
timetable/services.py — Service layer for the timetable grid UI.

resolve_week(school_id, section_id, week_start_ad) -> dict

Thin batch wrapper around timetable.resolver.resolve(). Does NOT
reimplement resolver logic — it loops resolve() once per date in the week.
Caches per (section_id, week_start) for the request only.
"""

from __future__ import annotations

import datetime

from .models import ScheduleProfilePeriod, TimetableEntry, TimetableException
from .resolver import resolve


def _ad_to_bs(ad_date: datetime.date) -> str:
    """Convert AD date to canonical BS 'YYYY-MM-DD' string via nepali_datetime."""
    import nepali_datetime

    bs = nepali_datetime.date.from_datetime_date(ad_date)
    return f"{bs.year:04d}-{bs.month:02d}-{bs.day:02d}"


def resolve_week(school_id: int, section_id: int, week_start_ad: datetime.date) -> dict:
    """
    Resolve a full week (Mon..Sat) for a section.

    Returns a dict keyed by (period_id, date_ad) with values:
      period_id, period_label, shift, start_time, end_time,
      subject_id, subject_name, teacher_id, teacher_name, room_id,
      source ('base'|'exception'|'cancelled'), reason,
      span_group_id, is_span_start, is_span_continued,
      span_start_time, span_end_time.

    Also returns 'week_start_bs' and 'week_end_bs' for display.
    """
    from .models import ScheduleProfilePeriod, TimetableEntry

    week_start_bs = _ad_to_bs(week_start_ad)
    week_end_ad = week_start_ad + datetime.timedelta(days=5)
    week_end_bs = _ad_to_bs(week_end_ad)

    # Cache per (section_id, week_start) — request-only, no cross-request cache.
    cache_key = (section_id, week_start_ad)

    grid: dict[tuple[int, datetime.date], dict] = {}
    errors: list = []

    # Load the profile once so we know the period list for all days.
    profile_periods = list(
        ScheduleProfilePeriod.objects
        .filter(period_type='class')
        .order_by('sequence')
    )
    period_by_id = {p.id: p for p in profile_periods}

    for offset in range(6):  # Mon..Sat
        day_ad = week_start_ad + datetime.timedelta(days=offset)
        day_bs = _ad_to_bs(day_ad)

        # Pass a nepali_datetime.date so resolve() gets both the BS string
        # (for lexicographic date-range comparison) and the accurate AD date
        # (for weekday bitmask matching).
        import nepali_datetime
        day_bs_date = nepali_datetime.date.from_datetime_date(day_ad)

        periods, day_errors = resolve(school_id, section_id, day_bs_date)
        errors.extend(day_errors)

        # Build a set of period_ids already resolved for this day.
        resolved_pids = {p.period_id for p in periods}

        # Add cancelled cells for periods cancelled by exception on this day.
        # The resolver skips cancelled periods entirely; we add them back as
        # source='cancelled' cells so the grid can show them.
        cancelled_excs = list(
            TimetableException.objects
            .filter(
                school_id=school_id,
                scope='section',
                scope_id=section_id,
                kind='cancel',
                archived_at__isnull=True,
                locked_at__isnull=True,
                date_from__lte=day_bs,
                date_to__gte=day_bs,
            )
        )
        for exc in cancelled_excs:
            if exc.period_id and exc.period_id not in resolved_pids:
                period = period_by_id.get(exc.period_id)
                resolved_pids.add(exc.period_id)
                grid[(exc.period_id, day_ad)] = {
                    'period_id': exc.period_id,
                    'period_label': period.label if period else str(exc.period_id),
                    'shift': period.shift if period else '',
                    'start_time': period.start_time if period else datetime.time(0, 0),
                    'end_time': period.end_time if period else datetime.time(0, 0),
                    'subject_id': 0,
                    'subject_name': '',
                    'teacher_id': 0,
                    'teacher_name': '',
                    'room_id': None,
                    'source': 'cancelled',
                    'reason': exc.reason,
                    'span_group_id': None,
                    'is_span_start': True,
                    'is_span_continued': False,
                    'span_start_time': None,
                    'span_end_time': None,
                }

        for p in periods:
            period = period_by_id.get(p.period_id)
            grid[(p.period_id, day_ad)] = {
                'period_id': p.period_id,
                'period_label': period.label if period else str(p.period_id),
                'shift': period.shift if period else '',
                'start_time': p.start_time,
                'end_time': p.end_time,
                'subject_id': p.subject_id,
                'subject_name': _subject_name(p.subject_id),
                'teacher_id': p.teacher_id,
                'teacher_name': _teacher_name(p.teacher_id),
                'room_id': p.room_id,
                'source': p.source,
                'reason': p.reason,
                'span_group_id': p.span_group_id,
                'is_span_start': p.is_span_start,
                'is_span_continued': p.is_span_continued,
                'span_start_time': p.span_start_time,
                'span_end_time': p.span_end_time,
            }

    return {
        'week_start_bs': week_start_bs,
        'week_end_bs': week_end_bs,
        'week_start_ad': week_start_ad,
        'week_end_ad': week_end_ad,
        'grid': grid,
        'errors': errors,
    }


def _subject_name(subject_id: int | None) -> str:
    if not subject_id:
        return ''
    from sms.models import Subject
    try:
        return Subject.objects.get(pk=subject_id).subject
    except Subject.DoesNotExist:
        return str(subject_id)


def _teacher_name(teacher_id: int | None) -> str:
    if not teacher_id:
        return ''
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        u = User.objects.get(pk=teacher_id)
        return u.get_full_name() or u.username
    except User.DoesNotExist:
        return str(teacher_id)


# ── Teacher workload service ───────────────────────────────────────────────

# Substitution semantics (documented for HRMS/payroll consumers):
#   Workload = "actually taught", not "scheduled".
#   - If a cancel exception covers a period, NO teacher is teaching it
#     → excluded from every teacher's workload.
#   - If a replace exception assigns a different teacher to a period,
#     the original teacher is NOT teaching it → excluded from their workload;
#     the substitute teacher IS teaching it → included in theirs.
#   - Whole-day exceptions cancel everything for that day/section → excluded.


def can_access_school(user, school_id: int) -> bool:
    """
    Check whether ``user`` can access timetable data for ``school_id``.

    Platform super-users can access any school. Other users require a
    BranchUser association linking them to the school. Staff status alone
    does not grant cross-school access (multi-tenant isolation).
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        from sms.models import BranchUser
        bu = BranchUser.objects.filter(user=user, status=True).first()
        if bu and bu.school_id == school_id:
            return True
    except Exception:
        pass
    return False


def _sections_for_teacher(school_id: int, teacher_id: int):
    """
    Return Section objects where ``teacher_id`` has a base entry or an
    exception (replace/cancel/add) scoped to that section in ``school_id``.
    """
    from sms.models import Section

    entry_section_ids = set(
        TimetableEntry.objects
        .filter(teacher_id=teacher_id, archived_at__isnull=True)
        .values_list('section_id', flat=True)
    )
    exc_section_ids = set(
        TimetableException.objects
        .filter(
            teacher_id=teacher_id, school_id=school_id,
            archived_at__isnull=True, locked_at__isnull=True,
            scope='section',
        )
        .values_list('scope_id', flat=True)
    )
    section_ids = entry_section_ids | exc_section_ids
    if not section_ids:
        return []
    return list(Section.objects.filter(id__in=section_ids))


def teacher_periods(
    teacher_id: int,
    from_ad: datetime.date,
    to_ad: datetime.date,
    school_id: int | None = None,
) -> list[dict]:
    """
    Return concrete periods this teacher teaches in [from_ad, to_ad].

    Each row is a dict with:
        date_ad, date_bs, period_id, period_label, section_id, section_name,
        subject_id, subject_name, start_time, end_time, source, reason,
        span_group_id, is_span_start, is_span_continued,
        span_start_time, span_end_time.

    Cancelled periods are excluded (workload = "actually taught").
    Exceptions/replacements are honored: a substitute teacher gets the
    period; the original teacher does not.

    Multi-tenant: ``school_id`` is required; the caller (request.user) must
    pass can_access_school(user, school_id).
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    try:
        teacher = User.objects.get(pk=teacher_id)
    except User.DoesNotExist:
        return []

    if school_id is not None and not can_access_school(teacher, school_id):
        return []

    sections = _sections_for_teacher(school_id, teacher_id)
    if school_id is not None:
        sections = [s for s in sections if s.school_id == school_id]
    if not sections:
        return []

    # Resolve each section for each week overlapping the range.
    # Cache by (section_id, week_start) to avoid recomputation.
    cache: dict[tuple[int, datetime.date], dict] = {}

    def _week_grid(section, week_start_ad):
        key = (section.id, week_start_ad)
        if key not in cache:
            cache[key] = resolve_week(section.school_id, section.id, week_start_ad)
        return cache[key]

    results: list[dict] = []

    current = from_ad
    while current <= to_ad:
        week_start = current - datetime.timedelta(days=current.weekday())

        for section in sections:
            result = _week_grid(section, week_start)
            grid = result['grid']

            for (period_id, day_ad), cell in grid.items():
                if day_ad < from_ad or day_ad > to_ad:
                    continue
                if cell.get('teacher_id') != teacher_id:
                    continue
                if cell.get('source') == 'cancelled':
                    continue

                results.append({
                    'date_ad': day_ad,
                    'date_bs': _ad_to_bs(day_ad),
                    'period_id': cell['period_id'],
                    'period_label': cell['period_label'],
                    'section_id': section.id,
                    'section_name': str(section),
                    'subject_id': cell['subject_id'],
                    'subject_name': cell['subject_name'],
                    'teacher_id': cell['teacher_id'],
                    'teacher_name': cell['teacher_name'],
                    'start_time': cell['start_time'],
                    'end_time': cell['end_time'],
                    'source': cell['source'],
                    'reason': cell['reason'],
                    'span_group_id': cell['span_group_id'],
                    'is_span_start': cell['is_span_start'],
                    'is_span_continued': cell['is_span_continued'],
                    'span_start_time': cell['span_start_time'],
                    'span_end_time': cell['span_end_time'],
                })

        current = week_start + datetime.timedelta(weeks=1)

    results.sort(key=lambda r: (r['date_ad'], r['period_id']))
    return results


def teacher_workload(
    teacher_id: int,
    from_ad: datetime.date,
    to_ad: datetime.date,
    school_id: int | None = None,
) -> dict:
    """
    Return aggregated workload counts for HRMS/payroll reports.

    Workload = "actually taught" (see teacher_periods docstring).

    Span counting rule: a span of N consecutive periods contributes N to
    total_periods and (span_end_time - span_start_time) minutes to
    total_minutes. A 2-period span from 10:00-11:30 counts as 2 periods,
    90 minutes.

    Returns:
        {
            total_periods: int,
            total_minutes: int,
            by_section: {section_id: {periods, minutes}},
            by_subject: {subject_id: {periods, minutes}},
        }
    """
    periods = teacher_periods(teacher_id, from_ad, to_ad, school_id)

    total_periods = 0
    total_minutes = 0
    by_section: dict[int, dict] = {}
    by_subject: dict[int, dict] = {}

    for p in periods:
        start = p['start_time']
        end = p['end_time']
        minutes = int(
            (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)
        )

        total_periods += 1
        total_minutes += minutes

        sid = p['section_id']
        if sid not in by_section:
            by_section[sid] = {'periods': 0, 'minutes': 0, 'section_name': p['section_name']}
        by_section[sid]['periods'] += 1
        by_section[sid]['minutes'] += minutes

        subj_id = p['subject_id']
        if subj_id not in by_subject:
            by_subject[subj_id] = {'periods': 0, 'minutes': 0, 'subject_name': p['subject_name']}
        by_subject[subj_id]['periods'] += 1
        by_subject[subj_id]['minutes'] += minutes

    return {
        'total_periods': total_periods,
        'total_minutes': total_minutes,
        'by_section': by_section,
        'by_subject': by_subject,
    }
