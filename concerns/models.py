from django.db import models
from django.contrib.auth.models import User
from nepali_datetime_field.models import NepaliDateField

from sms.models import (
    EduSession,
    SchoolBranch,
    SchoolGrade,
    Section,
    Subject,
    Student,
    Homework,
)


class Remark(models.Model):
    """A teacher's private observation about a student — sparse (one row per flagged student only).

    Two orthogonal axes:
      - visibility: PRIVATE (teacher + admin only) | PARENT_VISIBLE (parent can see via token)
      - status:     OPEN | ESCALATED | DISMISSED

    Unflagged students never get a row. Toggling off = active=False (soft delete, preserves audit trail).
    """

    CATEGORY_CHOICES = [
        ('homework',    'Homework'),
        ('behavior',    'Behavior'),
        ('cleanliness', 'Cleanliness'),
        ('regularity',  'Regularity'),
        ('other',       'Other'),
    ]

    SEVERITY_CHOICES = [
        ('low',      'Low'),
        ('medium',   'Medium'),
        ('high',     'High'),
    ]

    VISIBILITY_CHOICES = [
        ('private',        'Private'),
        ('parent_visible', 'Parent Visible'),
    ]

    STATUS_CHOICES = [
        ('open',      'Open'),
        ('escalated', 'Escalated'),
        ('dismissed', 'Dismissed'),
    ]

    # ── Identity & scoping ──────────────────────────────────────────────
    school    = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE, related_name='remarks')
    session   = models.ForeignKey(EduSession,  on_delete=models.CASCADE, related_name='remarks')
    student   = models.ForeignKey(Student,      on_delete=models.CASCADE, related_name='remarks')
    teacher   = models.ForeignKey(User,         on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='remarks_made')

    # ── Context ──────────────────────────────────────────────────────────
    category     = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='homework')
    grade        = models.ForeignKey(SchoolGrade, on_delete=models.CASCADE, related_name='remarks')
    section      = models.ForeignKey(Section,     on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='remarks')
    subject      = models.ForeignKey(Subject,     on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='remarks')
    homework     = models.ForeignKey(Homework,   on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='remarks')
    remark_date  = NepaliDateField(help_text="Date the observation was made — always set, even without homework FK")

    # ── Content ─────────────────────────────────────────────────────────
    reason      = models.CharField(max_length=255, blank=True, default='',
                                   help_text="Quick-pick reason or short label (e.g. 'not done', 'incomplete')")
    note        = models.TextField(blank=True, default='', help_text="Free-text detail from the teacher")
    severity    = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='low')

    # ── Two axes ────────────────────────────────────────────────────────
    visibility  = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='private')
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')

    # ── Soft delete ─────────────────────────────────────────────────────
    active       = models.BooleanField(default=True, help_text="False = un-flagged (soft deleted)")

    # ── Timestamps ──────────────────────────────────────────────────────
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-remark_date', '-created_at']
        # Prevent duplicate active remarks for same student/date/category/subject
        unique_together = (('student', 'remark_date', 'category', 'subject', 'active'),)

    def __str__(self):
        return f"{self.student.name} — {self.category} — {self.remark_date}"


class RemarkEditLog(models.Model):
    """Audit trail for Remark edits — who changed what, when, old vs new values."""
    remark       = models.ForeignKey(Remark, on_delete=models.CASCADE, related_name='edit_logs')
    changed_by   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='remark_edits')
    field        = models.CharField(max_length=30, help_text="Which field changed")
    old_value    = models.TextField(blank=True, default='')
    new_value    = models.TextField(blank=True, default='')
    changed_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f"EditLog #{self.pk} — {self.remark} — {self.field} at {self.changed_at:%Y-%m-%d %H:%M}"


class Concern(models.Model):
    """A formal, parent-facing case escalated from a Remark (or created directly by admin)."""

    CONCERN_STATUS_CHOICES = [
        ('open',            'Open'),
        ('in_progress',     'In Progress'),
        ('awaiting_parent',  'Awaiting Parent'),
        ('resolved',         'Resolved'),
        ('closed',          'Closed'),
        ('dismissed',       'Dismissed'),
    ]

    school     = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE, related_name='concerns')
    session    = models.ForeignKey(EduSession,  on_delete=models.CASCADE, related_name='concerns')
    student    = models.ForeignKey(Student,     on_delete=models.CASCADE, related_name='concerns')
    grade      = models.ForeignKey(SchoolGrade, on_delete=models.CASCADE, related_name='concerns')
    section    = models.ForeignKey(Section,     on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='concerns')

    source_remark = models.ForeignKey(Remark, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='concerns', help_text="Remark that triggered this concern, if any")

    title       = models.CharField(max_length=255, help_text="Short summary of the concern")
    description = models.TextField(blank=True, default='')
    category    = models.CharField(max_length=20, choices=Remark.CATEGORY_CHOICES, default='homework')

    status      = models.CharField(max_length=20, choices=CONCERN_STATUS_CHOICES, default='open')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='assigned_concerns', help_text="Admin assigned to handle this")

    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='concerns_created')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Concern #{self.pk} — {self.student.name} — {self.status}"


class CommunicationLog(models.Model):
    """One row per interaction on a concern — outbound (admin → parent) for now, inbound later (V3)."""

    DIRECTION_CHOICES = [
        ('outbound', 'Outbound'),
        ('inbound',  'Inbound'),
    ]
    CHANNEL_CHOICES = [
        ('app',      'App Notification'),
        ('sms',      'SMS'),
        ('phone',    'Phone Call'),
        ('email',    'Email'),
        ('in_person','In Person'),
        ('other',    'Other'),
    ]

    concern    = models.ForeignKey(Concern, on_delete=models.CASCADE, related_name='communications')
    author     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='concern_communications')
    direction  = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default='outbound')
    channel    = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='app')
    message    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.direction} — {self.concern} — {self.channel}"


class RemarkTemplate(models.Model):
    """Canned quick-pick reason texts, scoped by category and school."""
    school    = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE, related_name='remark_templates')
    category  = models.CharField(max_length=20, choices=Remark.CATEGORY_CHOICES, default='homework')
    text      = models.CharField(max_length=255, help_text="Canned reason text (e.g. 'Not done')")
    sort_order = models.IntegerField(default=0)
    active    = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'text']
        unique_together = (('school', 'category', 'text'),)

    def __str__(self):
        return f"{self.category}: {self.text}"


class GuardianToken(models.Model):
    """Per-student token for parent-facing webview URLs. Rotatable.

    Parent identity is phone-based (Student.fathers_phone / mothers_phone / guardian_phone).
    This model stores a stable token per student so we can generate a link without re-signing
    every time. Rotation replaces the token (old links stop working).
    """
    student   = models.OneToOneField(Student, on_delete=models.CASCADE, to_field='reg_no',
                                      related_name='guardian_token')
    token     = models.CharField(max_length=255, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rotated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Token for {self.student.name}"
