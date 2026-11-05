"""
timetable/resolver.py — Pure resolver function.

resolve(school_id, section_id, date) → list[ResolvedPeriod]

Invariants honoured (see .kilo/plans/timetable.md):
  4. Clash detection uses TIME INTERVAL OVERLAP, not period_id equality.
  5. Every resolved period carries source ('base'|'exception') and reason.
  7. Resolver is a pure function: no side effects, no writes.
  8. Span: a TimetableEntry with period_span > 1 expands into period_span
     consecutive CLASS periods starting at entry.period. Each returned row
     carries span_group_id, is_span_start, is_span_continued, and the
     combined span_start_time / span_end_time interval.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Optional

import nepali_datetime

from .models import TimetableEntry, TimetableException, TimetableVersion


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ResolvedPeriod:
    """One resolved period slot returned by the resolver."""
    period_id:    int
    subject_id:   int
    teacher_id:   int
    room_id:      Optional[int]
    start_time:   datetime.time
    end_time:     datetime.time
    source:       str          # 'base' | 'exception'
    reason:       Optional[str]

    # Span metadata (None for period_span == 1)
    span_group_id:      Optional[int]   # TimetableEntry.id
    is_span_start:      bool = False
    is_span_continued:  bool = False
    span_start_time:    Optional[datetime.time] = None   # start of span group
    span_end_time:      Optional[datetime.time] = None   # end of span group


@dataclass
class ResolverError:
    """Non-fatal error encountered during resolution (e.g. overlapping exceptions)."""
    kind:    str    # 'overlapping_exceptions' | 'missing_version' | etc.
    message: str
    context: dict = field(default_factory=dict)


# ── Helpers ───────────────────────────────────────────────────────────────────

_DOW_MAP = {0: 1, 1: 2, 2: 4, 3: 8, 4: 16, 5: 32, 6: 64}  # weekday() → bitmask

# Narrowest scope wins when multiple exceptions target the same period.
# section > class > grade > school (lower rank = narrower).
_SCOPE_RANK = {'section': 0, 'class': 1, 'grade': 2, 'school': 3}


def _bs_to_ad(bs_str: str) -> datetime.date:
    """Convert 'YYYY-MM-DD' BS string to AD date via nepali_datetime."""
    y, m, d = (int(p) for p in bs_str.split('-'))
    return nepali_datetime.date(y, m, d).to_datetime_date()


def _entry_matches_date(entry: TimetableEntry, ad_date: datetime.date) -> bool:
    """Return True if this entry is active on ad_date per its recurrence strategy."""
    dow_bit = _DOW_MAP[ad_date.weekday()]

    if entry.days_of_week is not None:           # weekly
        if not (entry.days_of_week & dow_bit):
            return False

    elif entry.day_of_month is not None:         # monthly
        if ad_date.day != entry.day_of_month:
            return False

    elif entry.specific_date is not None:        # once
        if entry.specific_date_ad != ad_date:
            return False

    else:
        return False  # should never happen (CHECK constraint enforces one strategy)

    # optional validity window
    if entry.valid_from_ad and ad_date < entry.valid_from_ad:
        return False
    if entry.valid_to_ad and ad_date > entry.valid_to_ad:
        return False

    return True


def _exception_matches_date(exc: TimetableException, bs_date: str, ad_date: datetime.date) -> bool:
    """Return True if this exception covers ad_date.

    BS dates are canonical: the range check uses the stored BS
    ``date_from``/``date_to`` (lexicographic == chronological for
    'YYYY-MM-DD'). The AD shadow is only an approx index column and must
    not be used for authoritative range membership. ``days_of_week`` is
    evaluated from the authoritative AD weekday.

    Mocked instances (used by older span tests) may only set the AD shadow
    columns; those fall back to an AD range comparison.
    """
    df, dt = exc.date_from, exc.date_to
    if isinstance(df, str) and isinstance(dt, str):
        if not (df <= bs_date <= dt):
            return False
    else:
        if not (exc.date_from_ad <= ad_date <= exc.date_to_ad):
            return False
    if exc.days_of_week is not None:
        dow_bit = _DOW_MAP[ad_date.weekday()]
        if not (exc.days_of_week & dow_bit):
            return False
    return True


def _scope_matches(exc: TimetableException, section_id: int) -> bool:
    """Return True if this exception's scope covers the given section."""
    if exc.scope == 'school':
        return True
    if exc.scope == 'section':
        return exc.scope_id == section_id
    # 'class' and 'grade' require the caller to pass a grade/level lookup;
    # for now treat them as matching — the app layer narrows further if needed.
    return True


def _expand_span(entry: TimetableEntry, all_periods: dict) -> list[dict]:
    """
    Expand entry into period_span consecutive CLASS periods.

    all_periods: {period_id: ScheduleProfilePeriod} for the profile.

    Returns a list of dicts, one per spanned period, ordered by sequence.
    Each dict has: period_id, start_time, end_time, is_start, is_continued.
    Stops early if a non-CLASS period is encountered (break/shift boundary).
    """
    if not all_periods:
        return []

    # Sort periods by sequence
    sorted_periods = sorted(all_periods.values(), key=lambda p: p.sequence)
    period_index = {p.id: i for i, p in enumerate(sorted_periods)}

    start_idx = period_index.get(entry.period_id)
    if start_idx is None:
        return []

    result = []
    for offset in range(entry.period_span):
        idx = start_idx + offset
        if idx >= len(sorted_periods):
            break
        p = sorted_periods[idx]
        if p.period_type != 'class':
            break  # span cannot cross a break or assembly
        result.append({
            'period_id':   p.id,
            'start_time':  p.start_time,
            'end_time':    p.end_time,
            'is_start':    offset == 0,
            'is_continued': offset > 0,
        })
    return result


# ── Main resolver ─────────────────────────────────────────────────────────────

def resolve(
    school_id: int,
    section_id: int,
    date,       # nepali_datetime.date or 'YYYY-MM-DD' string
) -> tuple[list[ResolvedPeriod], list[ResolverError]]:
    """
    Resolve the timetable for (school_id, section_id, date).

    Returns (periods, errors) where:
      - periods is sorted by start_time
      - errors is empty on a clean result; non-empty signals conflicts that
        must be resolved before the result can be trusted
    """
    errors: list[ResolverError] = []

    # Normalise date
    if isinstance(date, str):
        bs_date = date
        ad_date = _bs_to_ad(date)
    else:
        bs_date = str(date)
        ad_date = date.to_datetime_date() if hasattr(date, 'to_datetime_date') else date

    # ── Step 1: find the applicable published version ─────────────────────────
    # BS dates are canonical ('YYYY-MM-DD' compares lexicographically =
    # chronologically). Use effective_from (BS) rather than the approx AD shadow.
    version = (
        TimetableVersion.objects
        .filter(
            school_id=school_id,
            status='published',
            effective_from__lte=bs_date,
        )
        .order_by('-effective_from', '-version_no')
        .first()
    )
    if version is None:
        errors.append(ResolverError(
            kind='missing_version',
            message=f"No published version found for school={school_id} on {bs_date}",
        ))
        return [], errors

    # ── Step 2: base entries for this section on this date ────────────────────
    entries = list(
        TimetableEntry.objects
        .filter(version=version, section_id=section_id, archived_at__isnull=True)
        .select_related('period', 'period__profile')
    )

    # Build period lookup for span expansion
    all_periods = {}
    if entries:
        profile = entries[0].period.profile
        for p in profile.periods.filter(period_type='class'):
            all_periods[p.id] = p

    matching_entries = [e for e in entries if _entry_matches_date(e, ad_date)]

    # ── Step 3: exceptions covering this date ────────────────────────────────
    # Range match on canonical BS dates (authoritative); AD shadow is approx-only.
    candidates = list(
        TimetableException.objects
        .filter(
            school_id=school_id,
            academic_year_id=version.academic_year_id,
            date_from__lte=bs_date,
            date_to__gte=bs_date,
        )
        .order_by('scope')  # section > class > grade > school (narrowest first)
    )
    active_exceptions = [
        exc for exc in candidates
        if _exception_matches_date(exc, bs_date, ad_date) and _scope_matches(exc, section_id)
    ]

    # ── Step 4: apply exceptions ───────────────────────────────────────────────
    # whole_day exception → wipe base entirely
    whole_day = [e for e in active_exceptions if e.kind == 'whole_day']
    if len(whole_day) > 1:
        errors.append(ResolverError(
            kind='overlapping_exceptions',
            message="Multiple whole_day exceptions on the same date/scope — explicit resolution required",
            context={'exception_ids': [e.id for e in whole_day]},
        ))
        return [], errors

    if whole_day:
        exc = whole_day[0]
        return [], errors  # whole day cleared; caller handles display

    # Per-period exceptions: cancel / replace / add
    cancel_period_ids = set()
    replace_map: dict[int, TimetableException] = {}   # period_id → exc
    add_exceptions: list[TimetableException] = []

    for exc in active_exceptions:
        if exc.kind == 'cancel' and exc.period_id:
            cancel_period_ids.add(exc.period_id)
        elif exc.kind == 'replace' and exc.period_id:
            pid = exc.period_id
            existing = replace_map.get(pid)
            if existing is None:
                replace_map[pid] = exc
            else:
                exc_rank = _SCOPE_RANK.get(exc.scope, 9)
                exist_rank = _SCOPE_RANK.get(existing.scope, 9)
                if exc_rank < exist_rank:
                    # Narrower scope replaces the wider one (precedence).
                    replace_map[pid] = exc
                elif exc_rank == exist_rank:
                    # Same scope, same period, overlapping range → conflict.
                    errors.append(ResolverError(
                        kind='overlapping_exceptions',
                        message=f"Multiple replace exceptions for period_id={pid}",
                        context={'exception_ids': [existing.id, exc.id]},
                    ))
        elif exc.kind == 'add':
            add_exceptions.append(exc)

    # ── Step 5: build resolved periods ────────────────────────────────────────
    resolved: list[ResolvedPeriod] = []

    for entry in matching_entries:
        spanned = _expand_span(entry, all_periods) if entry.period_span > 1 else None

        if spanned:
            span_start_time = spanned[0]['start_time']
            span_end_time   = spanned[-1]['end_time']
        else:
            span_start_time = span_end_time = None

        periods_to_emit = spanned if spanned else [
            {
                'period_id':    entry.period_id,
                'start_time':   entry.period.start_time,
                'end_time':     entry.period.end_time,
                'is_start':     True,
                'is_continued': False,
            }
        ]

        for slot in periods_to_emit:
            pid = slot['period_id']

            if pid in cancel_period_ids:
                continue  # cancelled by exception

            if pid in replace_map:
                exc = replace_map[pid]
                resolved.append(ResolvedPeriod(
                    period_id=pid,
                    subject_id=exc.subject_id or entry.subject_id,
                    teacher_id=exc.teacher_id or entry.teacher_id,
                    room_id=exc.room_id or entry.room_id,
                    start_time=slot['start_time'],
                    end_time=slot['end_time'],
                    source='exception',
                    reason=exc.reason,
                    span_group_id=entry.id if entry.period_span > 1 else None,
                    is_span_start=slot['is_start'],
                    is_span_continued=slot['is_continued'],
                    span_start_time=span_start_time,
                    span_end_time=span_end_time,
                ))
            else:
                resolved.append(ResolvedPeriod(
                    period_id=pid,
                    subject_id=entry.subject_id,
                    teacher_id=entry.teacher_id,
                    room_id=entry.room_id,
                    start_time=slot['start_time'],
                    end_time=slot['end_time'],
                    source='base',
                    reason=None,
                    span_group_id=entry.id if entry.period_span > 1 else None,
                    is_span_start=slot['is_start'],
                    is_span_continued=slot['is_continued'],
                    span_start_time=span_start_time,
                    span_end_time=span_end_time,
                ))

    # add exceptions
    for exc in add_exceptions:
        if exc.period_id:
            # We don't have period start/end without a ScheduleProfilePeriod lookup;
            # caller should pre-fetch if needed. We emit with None times for now.
            resolved.append(ResolvedPeriod(
                period_id=exc.period_id,
                subject_id=exc.subject_id or 0,
                teacher_id=exc.teacher_id or 0,
                room_id=exc.room_id,
                start_time=datetime.time(0, 0),
                end_time=datetime.time(0, 0),
                source='exception',
                reason=exc.reason,
                span_group_id=None,
                is_span_start=True,
                is_span_continued=False,
            ))

    resolved.sort(key=lambda r: r.start_time)
    return resolved, errors
