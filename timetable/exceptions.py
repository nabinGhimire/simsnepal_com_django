"""
timetable/exceptions.py — Domain exceptions for the timetable module.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.dispatch import Signal


class TimetableError(ValidationError):
    """Base class for all timetable domain errors."""


class OverlapError(TimetableError):
    """
    Raised when creating or updating a TimetableException would produce an
    overlapping exception on the same (scope, period, date-range).

    Invariant #9: Never silently merge overlapping exceptions.
    """
    def __init__(self, message: str, conflicting_ids: list[int] = None):
        super().__init__(message)
        self.conflicting_ids = conflicting_ids or []


class LockedError(TimetableError):
    """
    Raised when attempting to modify or delete a locked TimetableException.

    Invariant #7: Once date_to < today, exceptions become read-only.
    """


# ── Signal ──────────────────────────────────────────────────────────────────────

# Emitted whenever a new TimetableException is successfully created.
# Carries the created instance as ``exception``.
exception_created = Signal()
