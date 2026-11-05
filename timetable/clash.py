"""
timetable/clash.py — Teacher clash detection.

detect_clashes(version) → list[Clash]

Uses TIME INTERVAL OVERLAP, not period_id equality (invariant #4).
For entries with period_span > 1, the interval is
  [period.start_time, period_{+span-1}.end_time]
i.e. the combined span interval — not just the first period.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Optional

from .models import TimetableEntry, TimetableVersion


@dataclass
class Clash:
    teacher_id:  int
    entry_a_id:  int
    entry_b_id:  int
    overlap_start: datetime.time
    overlap_end:   datetime.time
    detail:      str


def _get_span_interval(
    entry: TimetableEntry,
    sorted_class_periods: list,
) -> tuple[datetime.time, datetime.time]:
    """
    Return (start_time, end_time) for the full span of this entry.

    sorted_class_periods: list of ScheduleProfilePeriod ordered by sequence,
    filtered to period_type='class'.
    """
    period_index = {p.id: i for i, p in enumerate(sorted_class_periods)}
    start_idx = period_index.get(entry.period_id)

    if start_idx is None:
        # Fallback: use period's own times
        return entry.period.start_time, entry.period.end_time

    end_idx = min(start_idx + entry.period_span - 1, len(sorted_class_periods) - 1)
    # Stop early at a non-class period (same boundary rule as resolver)
    for i in range(start_idx, end_idx + 1):
        if sorted_class_periods[i].period_type != 'class':
            end_idx = i - 1
            break

    start = sorted_class_periods[start_idx].start_time
    end   = sorted_class_periods[end_idx].end_time
    return start, end


def _intervals_overlap(
    a_start: datetime.time, a_end: datetime.time,
    b_start: datetime.time, b_end: datetime.time,
) -> Optional[tuple[datetime.time, datetime.time]]:
    """Return (overlap_start, overlap_end) or None if no overlap."""
    lo = max(a_start, b_start)
    hi = min(a_end, b_end)
    if lo < hi:
        return lo, hi
    return None


def detect_clashes(version: TimetableVersion) -> list[Clash]:
    """
    Detect teacher clashes within a TimetableVersion.

    Two entries clash when:
      - same teacher
      - same recurrence day (days_of_week bitmasks share at least one bit,
        OR both are monthly/once and could land on the same day)
      - their combined span intervals overlap in time

    Returns a list of Clash objects. An empty list = no clashes detected.

    Note: this is a static analysis on the version. Runtime clash detection
    against exceptions is handled by the resolver.
    """
    entries = list(
        TimetableEntry.objects
        .filter(version=version, archived_at__isnull=True)
        .select_related('period', 'period__profile')
        .order_by('teacher_id', 'period__sequence')
    )
    if not entries:
        return []

    # Build sorted class-period list for span interval calculation
    profile = entries[0].period.profile
    sorted_class_periods = list(
        profile.periods.filter(period_type='class').order_by('sequence')
    )

    # Group by teacher
    by_teacher: dict[int, list[TimetableEntry]] = {}
    for e in entries:
        by_teacher.setdefault(e.teacher_id, []).append(e)

    clashes: list[Clash] = []

    for teacher_id, teacher_entries in by_teacher.items():
        n = len(teacher_entries)
        for i in range(n):
            for j in range(i + 1, n):
                a = teacher_entries[i]
                b = teacher_entries[j]

                # Quick check: could these two entries ever land on the same day?
                if not _could_coincide(a, b):
                    continue

                a_start, a_end = _get_span_interval(a, sorted_class_periods)
                b_start, b_end = _get_span_interval(b, sorted_class_periods)

                overlap = _intervals_overlap(a_start, a_end, b_start, b_end)
                if overlap:
                    clashes.append(Clash(
                        teacher_id=teacher_id,
                        entry_a_id=a.id,
                        entry_b_id=b.id,
                        overlap_start=overlap[0],
                        overlap_end=overlap[1],
                        detail=(
                            f"Teacher {teacher_id}: entry {a.id} "
                            f"({a_start}–{a_end}) overlaps entry {b.id} "
                            f"({b_start}–{b_end})"
                        ),
                    ))

    return clashes


def _could_coincide(a: TimetableEntry, b: TimetableEntry) -> bool:
    """
    Cheap heuristic: can entries a and b ever fall on the same calendar day?

    - weekly vs weekly: bitmasks must share at least one bit
    - everything else: assume possible (conservative — avoids false negatives)
    """
    if a.days_of_week is not None and b.days_of_week is not None:
        return bool(a.days_of_week & b.days_of_week)
    return True
