"""Managers for SMS app.

Provides SafeBranchUserManager for branch-scoped queries.
"""

from django.db import models
from .utils import get_current_school
from .utils import get_current_school

class SafeBranchUserManager(models.Manager):
    """Manager that limits BranchUser queries to the current school.

    It retrieves the school identifier from the session via ``get_current_school``
    and automatically filters the queryset accordingly. This mirrors the behaviour
    of ``SchoolScopedManager`` used for other multi‑tenant models.
    """

    def get_queryset(self):
        school = get_current_school()
        if school:
            return super().get_queryset().filter(school=school)
        # Fallback: return unfiltered queryset if no school in session (e.g., admin shell)
        return super().get_queryset()
