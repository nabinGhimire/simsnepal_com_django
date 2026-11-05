"""
timetable/validators.py — Save-time validation for TimetableEntry.

Called before saving a TimetableEntry to reject invalid configurations
that the DB CHECK constraints cannot catch (e.g. span crossing a break).

Usage:
    from timetable.validators import validate_entry
    errors = validate_entry(entry)
    if errors:
        raise ValidationError(errors)
"""

from __future__ import annotations

from django.core.exceptions import ValidationError


def validate_entry(entry) -> list[str]:
    """
    Validate a TimetableEntry instance before save.

    Returns a list of error strings (empty = valid).
    Raises nothing — caller decides whether to raise ValidationError.
    """
    errors: list[str] = []

    # ── period_span >= 1 (belt-and-suspenders; DB CHECK also enforces this) ──
    if entry.period_span is None or entry.period_span < 1:
        errors.append("period_span must be >= 1.")
        return errors  # further checks are meaningless without a valid span

    if entry.period_span == 1:
        return errors  # single period: nothing more to check

    # ── span > 1: verify the span does not cross a break or shift boundary ───
    if not hasattr(entry, 'period') or entry.period is None:
        # Can't validate without period relation loaded
        return errors

    profile = entry.period.profile
    # All periods in this profile ordered by sequence
    all_periods = list(profile.periods.order_by('sequence'))
    if not all_periods:
        return errors

    period_index = {p.id: i for i, p in enumerate(all_periods)}
    start_idx = period_index.get(entry.period_id)
    if start_idx is None:
        errors.append(
            f"period_id={entry.period_id} not found in profile {profile.id}."
        )
        return errors

    end_idx = start_idx + entry.period_span - 1
    if end_idx >= len(all_periods):
        errors.append(
            f"period_span={entry.period_span} extends beyond the last period "
            f"in profile {profile.id} (only {len(all_periods) - start_idx} "
            f"periods available from position {start_idx})."
        )
        return errors

    # Check every period in the span is a CLASS period and in the same shift
    start_shift = all_periods[start_idx].shift
    for offset in range(entry.period_span):
        p = all_periods[start_idx + offset]

        if p.period_type != 'class':
            errors.append(
                f"Span of {entry.period_span} crosses a non-class period "
                f"(period_id={p.id}, type='{p.period_type}') at position "
                f"{start_idx + offset} in profile {profile.id}. "
                f"Spans must consist entirely of CLASS periods."
            )
            break  # one error is enough

        if p.shift != start_shift:
            errors.append(
                f"Span of {entry.period_span} crosses a shift boundary at "
                f"period_id={p.id} (shift='{p.shift}', expected '{start_shift}'). "
                f"Spans must not cross shift boundaries."
            )
            break

    return errors


def validate_entry_raise(entry) -> None:
    """Validate and raise ValidationError if invalid."""
    errors = validate_entry(entry)
    if errors:
        raise ValidationError(errors)
