from django.db import models
from django.contrib.auth.models import User

from sms.models import Homework, Subject, SchoolGrade, Section


class HomeworkEntry(models.Model):
    """Normalized, subject-wise homework entry linked to an sms.Homework record."""
    homework = models.ForeignKey(Homework, on_delete=models.CASCADE, related_name='entries')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    homework_text = models.TextField()
    added_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hw_entries_added',
    )
    teacher_name = models.CharField(max_length=255, blank=True, default='')
    is_impersonated = models.BooleanField(default=False)

    class Meta:
        unique_together = (('homework', 'subject'),)
        ordering = ['subject__subject']

    def __str__(self):
        return f"{self.homework} / {self.subject.subject}: {self.homework_text[:40]}"


class HomeworkEntryAuditLog(models.Model):
    """Tracks every edit to a HomeworkEntry — stores old/new text, who changed it, and from where."""
    SOURCE_CHOICES = [
        ('admin',   'Admin Dashboard'),
        ('webview', 'Teacher Webview'),
    ]
    entry      = models.ForeignKey(HomeworkEntry, on_delete=models.CASCADE, related_name='audit_logs')
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='hw_audit_logs')
    old_text   = models.TextField()
    new_text   = models.TextField()
    changed_at = models.DateTimeField(auto_now_add=True)
    source     = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='admin')

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f"AuditLog #{self.pk} — {self.entry} by {self.changed_by} at {self.changed_at:%Y-%m-%d %H:%M}"



class HomeworkTemplate(models.Model):
    """Reusable subject->text homework template per grade."""
    grade = models.ForeignKey(SchoolGrade, on_delete=models.CASCADE, related_name='hw_templates')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    template_text = models.TextField()

    class Meta:
        unique_together = (('grade', 'subject'),)
        ordering = ['grade__grade_name', 'subject__subject']

    def __str__(self):
        return f"Template {self.grade.grade_name} / {self.subject.subject}"


class HomeworkComplain(models.Model):
    """Complaint raised by a teacher about a homework (or missing homework)."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]

    homework = models.ForeignKey(Homework, on_delete=models.CASCADE, null=True, blank=True, related_name='complains')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hw_complains')
    grade = models.ForeignKey(SchoolGrade, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE, null=True, blank=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, null=True, blank=True)
    complaint_text = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_response = models.TextField(blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_hw_complains')
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Complain by {self.teacher.username} - {self.status}"
