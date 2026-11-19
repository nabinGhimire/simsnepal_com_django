"""
Exam app models.

Migration shim: re-exports exam-domain models from sms.models, plus defines
exam-specific models that belong in this app.

Shared academic models (EduSession, GradeLevel, SchoolGrade, Section, Subject)
continue to import from sms.models directly in the views.
"""

from django.db import models
from sms.models import (
    SchoolBranch,
    EduSession,
    SchoolGrade,
    GradeFullMarks,
    LiveResult,
    ResultManagement,
    SchoolResultType,
    SchoolTerm,
    SchoolTermStatus,
    SchoolTerminology,
    WeightedResultManagement,
)


class GradeResultConfig(models.Model):
    """
    Per-grade result configuration for one academic session.

    Keyed by (school, year, grade) so:
    - Changing settings next year (new year row) does NOT alter how
      previous years' results are displayed.
    - Class 7 can use CAS while Class 8-10 use Exam in the same session.
    - When no row exists for a grade/session, the system falls back to
      the school-wide LiveResult / SchoolResultType defaults (old way).
    """

    SOURCE_CHOICES = [
        ("exam", "Exam"),
        ("cas", "CAS"),
    ]

    GRADING_TYPE_CHOICES = [
        (0, "LEGACY"),
        (1, "NON GRADE SYSTEM"),
        (2, "NEW GRADING SYSTEM"),
    ]

    LEDGER_TYPE_CHOICES = [
        (1, "MARKS"),
        (2, "GRADE"),
    ]

    CALCULATION_TYPE_CHOICES = [
        ("legacy", "LEGACY"),
        ("weighted", "WEIGHTED"),
    ]

    school = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    year = models.ForeignKey(EduSession, on_delete=models.CASCADE)
    grade = models.ForeignKey(SchoolGrade, on_delete=models.CASCADE)

    assessment_source = models.CharField(
        max_length=10,
        choices=SOURCE_CHOICES,
        default="exam",
        help_text="Which system produces the result for this grade.",
    )
    grading_type = models.IntegerField(
        choices=GRADING_TYPE_CHOICES,
        default=0,
        help_text="0=LEGACY, 1=NON GRADE SYSTEM, 2=NEW GRADING SYSTEM",
    )
    ledger_type = models.IntegerField(
        choices=LEDGER_TYPE_CHOICES,
        default=1,
        help_text="1=MARKS, 2=GRADE",
    )
    calculation_type = models.CharField(
        max_length=20,
        choices=CALCULATION_TYPE_CHOICES,
        default="legacy",
        help_text="legacy | weighted",
    )
    
    # Separate pass logic for Theory and Practical
    PASS_TYPE_CHOICES = [
        ("percentage", "Percentage"),
        ("gpa", "GPA"),
        ("marks", "Absolute Marks"),
    ]
    
    th_pass_type = models.CharField(
        max_length=15,
        choices=PASS_TYPE_CHOICES,
        default="percentage",
        help_text="Pass logic type for Theory",
    )
    th_pass_value = models.DecimalField(
        max_digits=5, decimal_places=2, default=35.00,
        help_text="Pass threshold for Theory (35% = 35.00, GPA 1.6 = 1.60, marks = absolute)"
    )
    
    pr_pass_type = models.CharField(
        max_length=15,
        choices=PASS_TYPE_CHOICES,
        default="percentage",
        help_text="Pass logic type for Practical",
    )
    pr_pass_value = models.DecimalField(
        max_digits=5, decimal_places=2, default=35.00,
        help_text="Pass threshold for Practical"
    )
    
    is_published = models.BooleanField(default=False)

    class Meta:
        unique_together = (("school", "year", "grade"),)
        verbose_name = "Grade Result Config"
        verbose_name_plural = "Grade Result Configs"

    def __str__(self):
        return f"{self.school.name} · {self.year.year} · {self.grade} · {self.assessment_source}"


# Re-export SMS models so existing exam.views imports keep working.
__all__ = [
    "GradeResultConfig",
    "GradeFullMarks",
    "LiveResult",
    "ResultManagement",
    "SchoolResultType",
    "SchoolTerm",
    "SchoolTermStatus",
    "SchoolTerminology",
    "WeightedResultManagement",
]
