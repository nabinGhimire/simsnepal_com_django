from django.db import models
from django.contrib.auth.models import User
from sms.models import Student, SchoolGrade, EduSession, Section, SchoolBranch, Subject
from nepali_datetime_field.models import NepaliDateField

class DailyAttendance(models.Model):
    reg_no = models.ForeignKey(Student, to_field='reg_no', db_column='reg_no', on_delete=models.CASCADE)
    school = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    session = models.ForeignKey(EduSession, on_delete=models.CASCADE)
    grade = models.ForeignKey(SchoolGrade, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE, blank=True, null=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, blank=True, null=True)
    
    date = models.DateField()
    nepali_date = NepaliDateField(blank=True, null=True)
    
    is_present = models.BooleanField(default=True)
    absent_informed = models.BooleanField(default=False)
    remarks = models.CharField(max_length=255, blank=True, null=True)
    
    taken_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='attendance_taken')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('reg_no', 'date', 'subject')

    def __str__(self):
        return f"{self.reg_no} - {self.date} - {'Present' if self.is_present else 'Absent'}"


class AttendanceAuditLog(models.Model):
    attendance = models.ForeignKey(DailyAttendance, on_delete=models.CASCADE, related_name='audit_logs')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    previous_status = models.BooleanField()
    new_status = models.BooleanField()
    previous_remarks = models.CharField(max_length=255, blank=True, null=True)
    new_remarks = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Audit: {self.attendance.reg_no} changed by {self.updated_by} on {self.created_at}"


class AttendanceSettings(models.Model):
    """Per-school attendance configuration."""

    CONFLICT_ABSENT_WINS = 'absent_wins'
    CONFLICT_PRESENT_WINS = 'present_wins'
    CONFLICT_CHOICES = [
        (CONFLICT_ABSENT_WINS, 'Absent wins — any absent subject = absent for the day'),
        (CONFLICT_PRESENT_WINS, 'Present wins — any present subject = present for the day'),
    ]

    school = models.OneToOneField(
        SchoolBranch, on_delete=models.CASCADE,
        related_name='attendance_settings'
    )

    # ── Group 1: Subject conflict rule ──────────────────────────────────────
    subject_conflict_rule = models.CharField(
        max_length=20, choices=CONFLICT_CHOICES,
        default=CONFLICT_ABSENT_WINS,
        help_text='How to resolve general attendance when subject records conflict.'
    )

    # ── Group 2: Notification channels (shared for all trigger types) ───────
    notify_sms = models.BooleanField(default=False, verbose_name='Send SMS')
    notify_push = models.BooleanField(default=False, verbose_name='Send Push Notification (HamroApp)')
    notify_class_group = models.BooleanField(default=False, verbose_name='Send message on Class Group')
    notify_student_channel = models.BooleanField(default=False, verbose_name='Send message on Student Channel')
    notify_student_group = models.BooleanField(default=False, verbose_name='Send message on Student Group')
    notify_sims_attendance = models.BooleanField(default=False, verbose_name='Send via SIMS Attendance')

    # ── Group 3: Notification triggers ──────────────────────────────────────
    notify_on_absent = models.BooleanField(
        default=False,
        verbose_name='Notify parents when student is marked absent'
    )
    notify_consecutive_only = models.BooleanField(
        default=False,
        verbose_name='Only notify after N consecutive absences'
    )
    consecutive_absence_threshold = models.PositiveSmallIntegerField(
        default=3,
        help_text='Notify parents only after this many consecutive absent days.'
    )
    notify_on_late_absence = models.BooleanField(
        default=False,
        verbose_name='Notify parents if student present then later absent on same day'
    )
    notify_on_manual_change = models.BooleanField(
        default=False,
        verbose_name='Notify parents when admin manually changes attendance status'
    )

    # ── Group 4: Monthly report ──────────────────────────────────────────────
    send_monthly_report = models.BooleanField(
        default=False,
        verbose_name='Send monthly attendance report to parents'
    )

    # ── Group 5: Record locking ──────────────────────────────────────────────
    lock_attendance = models.BooleanField(
        default=False,
        verbose_name='Lock attendance records after N hours'
    )
    lock_after_hours = models.PositiveSmallIntegerField(
        default=24,
        help_text='Number of hours after which attendance records are locked.'
    )
    admin_can_override_lock = models.BooleanField(
        default=True,
        verbose_name='Allow admin to override locked records'
    )

    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='attendance_settings_updated'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Attendance Settings'
        verbose_name_plural = 'Attendance Settings'

    def __str__(self):
        return f"Attendance Settings — {self.school}"
