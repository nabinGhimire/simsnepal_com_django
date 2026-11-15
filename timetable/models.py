"""
Timetable module models.

Constitution: .kilo/plans/timetable.md

INVARIANTS (enforced here and in migrations):
  1. TimetableVersion is immutable once published — no updated_at.
  2. Exceptions never mutate versions — use TimetableException.
  3. BS dates are canonical (CharField 'YYYY-MM-DD'). AD shadow columns
     are plain writable DateFields computed in model.save() via
     nepali_datetime (accurate BS→AD conversion). Do NOT bulk_create()
     these models — AD computation and validation happen in save().
  4. Clash detection uses TIME INTERVAL OVERLAP, not period_id equality.
  5. days_of_week is a SMALLINT bitmask: Mon=1, Tue=2, Wed=4, Thu=8,
     Fri=16, Sat=32, Sun=64.
  6. No hard deletes — use archived_at / locked_at.
  7. Resolver is a pure function: no side effects, no writes.
"""

from __future__ import annotations

import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

import nepali_datetime

from sms.models import EduSession, SchoolBranch, SchoolGrade, Section, Subject

from .exceptions import LockedError, OverlapError


def _bs_to_ad(bs_str: str) -> datetime.date:
    """Convert canonical BS 'YYYY-MM-DD' to AD date via nepali_datetime."""
    y, m, d = (int(p) for p in bs_str.split('-'))
    return nepali_datetime.date(y, m, d).to_datetime_date()


class _NoBulkCreateManager(models.Manager):
    """Manager that forbids bulk_create().

    AD shadow columns and model-layer validation are computed in save().
    bulk_create() bypasses save(), so it would leave AD shadows stale and
    skip validation. Use individual .save() calls instead.
    """

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False):
        raise NotImplementedError(
            f"{self.model.__name__} does not support bulk_create(). "
            f"AD shadow columns and validation are computed in save(); "
            f"call .save() on each instance instead."
        )


# ── 1. ScheduleProfile ────────────────────────────────────────────────────────

class ScheduleProfile(models.Model):
    """
    A named period grid (e.g. "Morning Shift") belonging to a school.

    DB table: timetable_schedule_profile
    Columns:  id · school_id · name · is_active
    """
    school    = models.ForeignKey(
        SchoolBranch,
        on_delete=models.PROTECT,
        db_column="school_id",
        related_name="schedule_profiles",
    )
    name      = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "timetable_schedule_profile"
        indexes  = [
            models.Index(fields=["school"], name="tt_sprofile_school_idx"),
        ]

    def __str__(self):
        return f"{self.school_id} — {self.name}"


# ── 2. ScheduleProfilePeriod ──────────────────────────────────────────────────

class ScheduleProfilePeriod(models.Model):
    """
    One ordered time slot within a ScheduleProfile.

    DB table: timetable_schedule_profile_period
    Columns:  id · profile_id · sequence · shift · start_time · end_time
              · period_type · label
    """
    SHIFT_CHOICES = [
        ("morning", "Morning"),
        ("day",     "Day"),
        ("evening", "Evening"),
    ]
    TYPE_CHOICES = [
        ("class",    "Class"),
        ("break",    "Break"),
        ("assembly", "Assembly"),
        ("lunch",    "Lunch"),
    ]

    profile     = models.ForeignKey(
        ScheduleProfile,
        on_delete=models.CASCADE,
        db_column="profile_id",
        related_name="periods",
    )
    sequence    = models.PositiveSmallIntegerField()
    shift       = models.CharField(max_length=10, choices=SHIFT_CHOICES)
    start_time  = models.TimeField()
    end_time    = models.TimeField()
    period_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    label       = models.CharField(max_length=60, blank=True)

    class Meta:
        db_table = "timetable_schedule_profile_period"
        ordering = ["profile", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "sequence"],
                name="tt_spp_profile_seq_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.profile_id} · {self.sequence} · {self.label or self.period_type}"


class GradeStructure(models.Model):
    """
    Standard daily schedule structure for a grade within a shift.

    Defines the template schedule (e.g., "Class 10 Morning Regular",
    "PG Day 1-hour periods") that TimetableVersion entries instantiate.
    """
    SHIFT_CHOICES = [
        ("morning", "Morning"),
        ("day",     "Day"),
        ("evening", "Evening"),
    ]

    school      = models.ForeignKey(
        SchoolBranch, on_delete=models.CASCADE, db_column="school_id",
        related_name="grade_structures",
    )
    grade       = models.ForeignKey(
        SchoolGrade, on_delete=models.CASCADE, db_column="grade_id",
        related_name="grade_structures",
    )
    section     = models.ForeignKey(
        Section, on_delete=models.CASCADE, db_column="section_id",
        related_name="grade_structures", null=True, blank=True,
        help_text="Leave empty for grade-level default; set for section-specific override",
    )
    shift       = models.CharField(max_length=10, choices=SHIFT_CHOICES)
    name        = models.CharField(max_length=120, blank=True,
        help_text="e.g. 'Regular Day', 'Morning Extra', 'Morning Tuition'")
    period_duration = models.PositiveSmallIntegerField(
        default=40, help_text="Default period length in minutes (40, 60, etc.)"
    )
    break_after_periods = models.PositiveSmallIntegerField(
        default=4, help_text="Insert a break after this many periods (4 or 5)"
    )
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "timetable_grade_structure"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "grade", "shift", "name", "section"],
                name="tt_grade_structure_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["school", "grade"], name="tt_gs_school_grade_idx"),
            models.Index(fields=["school", "section"], name="tt_gs_school_section_idx"),
        ]

    def __str__(self):
        section_part = f" · {self.section.section}" if self.section else ""
        return f"{self.grade.grade_name}{section_part} · {self.shift} · {self.name or self.shift}"


class GradeStructurePeriod(models.Model):
    """
    One period slot within a GradeStructure.
    """
    structure     = models.ForeignKey(
        GradeStructure, on_delete=models.CASCADE, db_column="structure_id",
        related_name="structure_periods",
    )
    sequence      = models.PositiveSmallIntegerField()
    period_type   = models.CharField(max_length=10, choices=[
        ("class",    "Class"),
        ("break",    "Break"),
        ("assembly", "Assembly"),
        ("lunch",    "Lunch"),
    ], default="class")
    label         = models.CharField(max_length=120, blank=True,
        help_text="e.g. 'Nepali', 'Math', 'Break', 'Assembly'")
    duration_minutes = models.PositiveSmallIntegerField(
        help_text="Duration in minutes (overrides structure default)"
    )
    days_of_week  = models.SmallIntegerField(null=True, blank=True,
        help_text="Bitmask: Mon=1..Sun=64. NULL = every day")
    is_active     = models.BooleanField(default=True)

    class Meta:
        db_table = "timetable_grade_structure_period"
        constraints = [
            models.UniqueConstraint(
                fields=["structure", "sequence"],
                name="tt_gsp_structure_seq_uniq",
            ),
        ]
        ordering = ["structure", "sequence"]

    def __str__(self):
        return f"{self.structure} · {self.sequence} · {self.label or self.period_type}"


# ── 3. TimetableVersion ───────────────────────────────────────────────────────

class TimetableVersion(models.Model):
    """
    Immutable snapshot of a school's timetable for an academic year.

    DO NOT add updated_at — versions are append-only (invariant #1).
    Once published, no field may change; create a new version instead.

    DO NOT bulk_create(). AD computation and validation happen in save().

    DB table: timetable_version
    Columns:  id · school_id · academic_year_id · version_no
              · effective_from (BS VARCHAR) · effective_from_ad (DATE shadow)
              · status · published_at · published_by · change_note
              · archived_at · created_at · created_by
    """
    objects = _NoBulkCreateManager()

    STATUS_CHOICES = [
        ("draft",     "Draft"),
        ("published", "Published"),
        ("archived",  "Archived"),
    ]

    school        = models.ForeignKey(
        SchoolBranch,
        on_delete=models.PROTECT,
        db_column="school_id",
        related_name="timetable_versions",
    )
    academic_year = models.ForeignKey(
        EduSession,
        on_delete=models.PROTECT,
        db_column="academic_year_id",
        related_name="timetable_versions",
    )
    version_no    = models.PositiveSmallIntegerField()

    # BS canonical date 'YYYY-MM-DD'
    effective_from    = models.CharField(max_length=10)

    # AD shadow computed from effective_from in save() (BS→AD via nepali_datetime).
    # Plain writable DateField — NOT NULL because effective_from is always set.
    effective_from_ad = models.DateField(
        help_text="AD shadow of effective_from, computed in save().",
    )

    status       = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default="draft"
    )
    published_at  = models.DateTimeField(null=True, blank=True)
    published_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_column="published_by",
        related_name="published_timetable_versions",
    )
    change_note   = models.TextField(blank=True)
    archived_at   = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    created_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_column="created_by",
        related_name="created_timetable_versions",
    )
    # NOTE: no updated_at — invariant #1

    class Meta:
        db_table = "timetable_version"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "academic_year", "version_no"],
                name="tt_version_school_year_no_uniq",
            ),
        ]
        indexes = [
            # DB has this as (school_id ASC, academic_year_id ASC, effective_from DESC).
            # Django Index doesn't model DESC; the DB-level DDL is in 0002.
            # This entry exists only so makemigrations stays silent.
            models.Index(
                fields=["school", "academic_year", "effective_from"],
                name="tt_version_school_year_eff_idx",
            ),
        ]

    def __str__(self):
        return f"v{self.version_no} ({self.school_id}/{self.academic_year_id})"

    def save(self, *args, **kwargs):
        """Compute effective_from_ad from effective_from before saving."""
        if self.effective_from:
            self.effective_from_ad = _bs_to_ad(self.effective_from)
        super().save(*args, **kwargs)


# ── 4. TimetableEntry ─────────────────────────────────────────────────────────

class TimetableEntry(models.Model):
    """
    One period assignment inside a TimetableVersion.

    Recurrence strategy: exactly ONE of (days_of_week, day_of_month,
    specific_date) must be non-null. Enforced by DB CHECK constraint
    tt_entry_exactly_one_strategy.

    DO NOT bulk_create(). AD computation and validation happen in save().

    DB table: timetable_entry
    Columns:  id · version_id · section_id · period_id · subject_id
              · teacher_id · room_id · recurrence · days_of_week
              · day_of_month · specific_date (BS) · valid_from (BS)
              · valid_to (BS) · entry_type · period_span · created_at · created_by
              · specific_date_ad (DATE shadow, nullable) · valid_from_ad (DATE shadow, nullable)
              · valid_to_ad (DATE shadow, nullable) · archived_at
    """
    objects = _NoBulkCreateManager()

    RECURRENCE_CHOICES = [
        ("daily",   "Daily"),
        ("weekly",  "Weekly"),
        ("monthly", "Monthly"),
        ("once",    "Once"),
    ]
    TYPE_CHOICES = [
        ("regular", "Regular"),
        ("special", "Special"),
    ]

    version = models.ForeignKey(
        TimetableVersion,
        on_delete=models.CASCADE,
        db_column="version_id",
        related_name="entries",
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.PROTECT,
        db_column="section_id",
        related_name="timetable_entries",
    )
    period = models.ForeignKey(
        ScheduleProfilePeriod,
        on_delete=models.PROTECT,
        db_column="period_id",
        related_name="timetable_entries",
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        db_column="subject_id",
        related_name="timetable_entries",
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="teacher_id",
        related_name="timetable_entries",
    )
    # TODO: replace with ForeignKey to Room model once that table is created
    room_id     = models.IntegerField(null=True, blank=True)

    recurrence  = models.CharField(max_length=10, choices=RECURRENCE_CHOICES)

    # Bitmask: Mon=1, Tue=2, Wed=4, Thu=8, Fri=16, Sat=32, Sun=64
    days_of_week  = models.SmallIntegerField(null=True, blank=True)
    day_of_month  = models.PositiveSmallIntegerField(null=True, blank=True)

    # BS canonical dates 'YYYY-MM-DD'
    specific_date = models.CharField(max_length=10, null=True, blank=True)
    valid_from    = models.CharField(max_length=10, null=True, blank=True)
    valid_to      = models.CharField(max_length=10, null=True, blank=True)

    # AD shadows computed from BS columns in save() (BS→AD via nepali_datetime).
    # specific_date / valid_from / valid_to are nullable, so their shadows are too.
    specific_date_ad = models.DateField(
        null=True, blank=True,
        help_text="AD shadow of specific_date, computed in save().",
    )
    valid_from_ad = models.DateField(
        null=True, blank=True,
        help_text="AD shadow of valid_from, computed in save().",
    )
    valid_to_ad = models.DateField(
        null=True, blank=True,
        help_text="AD shadow of valid_to, computed in save().",
    )

    entry_type  = models.CharField(max_length=10, choices=TYPE_CHOICES, default="regular")
    # Consecutive CLASS periods this entry occupies (default 1 = single period).
    # Must not cross a break or shift boundary — enforced at save time by the app.
    period_span = models.PositiveSmallIntegerField(default=1)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_column="created_by",
        related_name="created_timetable_entries",
    )

    class Meta:
        db_table = "timetable_entry"
        constraints = [
            # Exactly one of (days_of_week, day_of_month, specific_date) non-null
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(days_of_week__isnull=False)
                        & models.Q(day_of_month__isnull=True)
                        & models.Q(specific_date__isnull=True)
                    ) | (
                        models.Q(days_of_week__isnull=True)
                        & models.Q(day_of_month__isnull=False)
                        & models.Q(specific_date__isnull=True)
                    ) | (
                        models.Q(days_of_week__isnull=True)
                        & models.Q(day_of_month__isnull=True)
                        & models.Q(specific_date__isnull=False)
                    )
                ),
                name="tt_entry_exactly_one_strategy",
            ),
            models.CheckConstraint(
                condition=models.Q(period_span__gte=1),
                name="tt_entry_period_span_gte_1",
            ),
        ]
        indexes = [
            # Primary resolver lookup: version + section
            models.Index(
                fields=["version", "section"],
                name="tt_entry_version_section_idx",
            ),
            # Clash detection across teachers
            models.Index(fields=["teacher"], name="tt_entry_teacher_idx"),
            # Once-off entries by AD date (partial on SQLite, full on MySQL — see 0002)
            models.Index(
                fields=["specific_date_ad"],
                name="tt_entry_specific_date_idx",
            ),
        ]

    def clean(self):
        """Validate span boundary at the model layer (called by full_clean)."""
        from .validators import validate_entry_raise
        validate_entry_raise(self)

    def save(self, *args, **kwargs):
        """Compute AD shadows from BS columns, then full_clean and save."""
        if self.specific_date:
            self.specific_date_ad = _bs_to_ad(self.specific_date)
        else:
            self.specific_date_ad = None
        if self.valid_from:
            self.valid_from_ad = _bs_to_ad(self.valid_from)
        else:
            self.valid_from_ad = None
        if self.valid_to:
            self.valid_to_ad = _bs_to_ad(self.valid_to)
        else:
            self.valid_to_ad = None
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Entry {self.id} v{self.version_id} §{self.section_id}"


# ── 5. TimetableException ─────────────────────────────────────────────────────

class TimetableException(models.Model):
    """
    A date-range override. Never mutates a TimetableVersion (invariant #2).

    scope + scope_id identify the organisational unit affected. The scope_id
    is a generic integer because the target model depends on scope value:
      section → sms.Section.id
      class   → sms.SchoolGrade.id   (a "class" = grade in this codebase)
      grade   → sms.GradeLevel.id
      school  → sms.SchoolBranch.id
    Using a bare IntegerField avoids a polymorphic FK mess; the resolver
    handles the join.

    period_id and subject_id on exception are also bare integers because
    the DB has no FK constraint on them (exceptions can reference any
    period/subject, including ones from other versions).

    DO NOT bulk_create(). AD computation and validation happen in save().

    DB table: timetable_exception
    Columns:  id · school_id · academic_year_id · date_from (BS)
              · date_to (BS) · date_from_ad (DATE shadow) · date_to_ad (DATE shadow)
              · days_of_week · kind · scope · scope_id · period_id
              · subject_id · teacher_id · room_id · reason
              · created_at · created_by · locked_at · archived_at
    """
    objects = _NoBulkCreateManager()

    KIND_CHOICES = [
        ("whole_day", "Whole Day"),
        ("replace",   "Replace"),
        ("cancel",    "Cancel"),
        ("add",       "Add"),
    ]
    SCOPE_CHOICES = [
        ("section", "Section"),
        ("class",   "Class"),
        ("grade",   "Grade"),
        ("school",  "School"),
    ]

    school = models.ForeignKey(
        SchoolBranch,
        on_delete=models.PROTECT,
        db_column="school_id",
        related_name="timetable_exceptions",
    )
    academic_year = models.ForeignKey(
        EduSession,
        on_delete=models.PROTECT,
        db_column="academic_year_id",
        related_name="timetable_exceptions",
    )

    # BS canonical date range 'YYYY-MM-DD'
    date_from = models.CharField(max_length=10)
    date_to   = models.CharField(max_length=10)

    # AD shadows computed from BS columns in save() (BS→AD via nepali_datetime).
    # NOT NULL because date_from/date_to are always set.
    date_from_ad = models.DateField(
        help_text="AD shadow of date_from, computed in save().",
    )
    date_to_ad = models.DateField(
        help_text="AD shadow of date_to, computed in save().",
    )

    # Bitmask: Mon=1..Sun=64; NULL means every day in the range
    days_of_week = models.SmallIntegerField(null=True, blank=True)

    kind  = models.CharField(max_length=10, choices=KIND_CHOICES)
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES)

    # TODO: replace with a GenericForeignKey or a typed FK once scope is stable
    scope_id = models.IntegerField()

    # Bare integers — no FK in DB; resolver resolves to the correct period/subject
    # TODO: period_id → FK to ScheduleProfilePeriod once FK is added to DB
    period_id  = models.IntegerField(null=True, blank=True)
    # TODO: subject_id → FK to Subject once FK is added to DB
    subject_id = models.IntegerField(null=True, blank=True)
    # teacher_id has no DB FK on timetable_exception (bare int in DB)
    # TODO: add FK to AUTH_USER_MODEL once DB column type is aligned (currently int vs bigint)
    teacher_id = models.IntegerField(null=True, blank=True)
    # TODO: replace with ForeignKey to Room model once that table is created
    room_id    = models.IntegerField(null=True, blank=True)

    # Mandatory on all exceptions (invariant #6)
    reason     = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="created_by",
        related_name="created_timetable_exceptions",
    )
    # Read-only once locked (invariant #7: past dates lock)
    locked_at  = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "timetable_exception"
        constraints = [
            # date_to >= date_from (YYYY-MM-DD lexicographic ≡ chronological)
            models.CheckConstraint(
                condition=models.Q(date_to__gte=models.F("date_from")),
                name="tt_exc_date_to_gte_date_from",
            ),
        ]
        indexes = [
            # Primary resolver lookup: school + date range start
            models.Index(
                fields=["school", "date_from_ad"],
                name="tt_exc_school_date_from_idx",
            ),
            models.Index(
                fields=["school", "academic_year"],
                name="tt_exc_school_year_idx",
            ),
            models.Index(fields=["teacher_id"], name="tt_exc_teacher_idx"),
        ]

    def __str__(self):
        return f"Exception {self.id} {self.scope}/{self.scope_id} {self.date_from}→{self.date_to}"

    def clean(self):
        """Validate AD shadows and enforce no-overlap invariant (#9)."""
        from .exceptions import OverlapError

        # Compute AD shadows from BS columns if not already set
        if self.date_from and not self.date_from_ad:
            self.date_from_ad = _bs_to_ad(self.date_from)
        if self.date_to and not self.date_to_ad:
            self.date_to_ad = _bs_to_ad(self.date_to)

        # Enforce no-overlap: same (school, scope, scope_id, period_id)
        # with overlapping date ranges conflicts.
        qs = TimetableException.objects.filter(
            school_id=self.school_id,
            scope=self.scope,
            scope_id=self.scope_id,
            period_id=self.period_id,
            archived_at__isnull=True,
            locked_at__isnull=True,
        )
        if self.pk is not None:
            qs = qs.exclude(pk=self.pk)

        from_ad = self.date_from_ad
        to_ad = self.date_to_ad

        conflicting = list(
            qs.filter(date_from_ad__lte=to_ad, date_to_ad__gte=from_ad)
        )

        # If the new exception is day-scoped, only conflicting exceptions that
        # could land on a shared weekday matter.
        if self.days_of_week is not None:
            conflicting = [
                exc for exc in conflicting
                if exc.days_of_week is None or (exc.days_of_week & self.days_of_week)
            ]

        if conflicting:
            raise OverlapError(
                f"Exception overlaps existing exception(s) on "
                f"{self.scope}/{self.scope_id} period {self.period_id} "
                f"{self.date_from}→{self.date_to}",
                conflicting_ids=[exc.id for exc in conflicting],
            )

    def save(self, *args, **kwargs):
        """Compute AD shadows from BS columns, full_clean (overlap check),
        enforce lock, then save. Emits exception_created on new rows."""
        # Compute AD shadows from BS columns
        if self.date_from:
            self.date_from_ad = _bs_to_ad(self.date_from)
        if self.date_to:
            self.date_to_ad = _bs_to_ad(self.date_to)

        # Full clean validates fields and calls clean() (overlap check).
        self.full_clean()

        # Locked exceptions are read-only once locked_at is set (invariant #7).
        # The save that first sets locked_at (transition None -> set) is
        # allowed; any later modification of an already-locked row is blocked.
        if self.pk is not None and self.locked_at is not None:
            try:
                original = TimetableException.objects.only('locked_at').get(pk=self.pk)
                if original.locked_at is not None:
                    raise LockedError(
                        f"Exception {self.pk} is locked and cannot be modified."
                    )
            except TimetableException.DoesNotExist:
                pass

        adding = self._state.adding
        super().save(*args, **kwargs)

        if adding:
            from .exceptions import exception_created
            exception_created.send(sender=TimetableException, exception=self)

    def delete(self, *args, **kwargs):
        """Locked exceptions cannot be hard-deleted (invariant #7, #10)."""
        if self.locked_at and self.pk is not None:
            raise LockedError(
                f"Exception {self.pk} is locked and cannot be deleted."
            )
        super().delete(*args, **kwargs)


# ── School-Level Timetable Settings ──────────────────────────────────────────

class TimetableSchoolSettings(models.Model):
    """
    Global per-school timetable settings.

    Defines the school-wide shift times, default class duration, weekend
    configuration, and break rules that apply across all grades.
    """
    SHIFT_CHOICES = [
        ("morning", "Morning"),
        ("day",     "Day"),
        ("evening", "Evening"),
    ]

    school      = models.OneToOneField(
        SchoolBranch, on_delete=models.CASCADE, db_column="school_id",
        related_name="timetable_settings",
    )

    # Shift time ranges (defines when each shift starts/ends)
    shift_morning_start = models.TimeField(null=True, blank=True,
        help_text="Morning shift start time")
    shift_morning_end   = models.TimeField(null=True, blank=True,
        help_text="Morning shift end time")
    shift_day_start     = models.TimeField(null=True, blank=True,
        help_text="Day shift start time")
    shift_day_end       = models.TimeField(null=True, blank=True,
        help_text="Day shift end time")
    shift_evening_start = models.TimeField(null=True, blank=True,
        help_text="Evening shift start time")
    shift_evening_end   = models.TimeField(null=True, blank=True,
        help_text="Evening shift end time")

    # Default period duration in minutes (overridable per grade structure)
    default_period_duration = models.PositiveSmallIntegerField(
        default=40, help_text="Default period length in minutes"
    )

    # Weekend configuration (bitmask: Mon=1..Sun=64)
    # Days with these bits set are weekends (no regular classes)
    weekend_days = models.SmallIntegerField(
        default=64,  # Sunday only by default
        help_text="Weekend days bitmask (Mon=1, Tue=2, Wed=4, Thu=8, Fri=16, Sat=32, Sun=64)"
    )

    # Break rules
    break_after_periods = models.PositiveSmallIntegerField(
        default=4, help_text="Insert break after this many periods"
    )
    break_duration_minutes = models.PositiveSmallIntegerField(
        default=15, help_text="Break duration in minutes"
    )

    is_active = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "timetable_school_settings"
        verbose_name = "Timetable School Settings"
        verbose_name_plural = "Timetable School Settings"

    def __str__(self):
        return f"Timetable Settings — {self.school.name}"
