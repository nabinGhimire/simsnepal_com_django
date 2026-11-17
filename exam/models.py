"""
Exam app models.

Migration shim: re-exports only the *exam-domain* models that
``exam/views.py`` reads from ``sms.models``. Shared academic models
(``EduSession``, ``GradeLevel``, ``SchoolGrade``, ``Section``, ``Subject``)
continue to import from ``sms.models`` directly in the views.

When you are ready to move a real model definition into this app, define it
here (or import it from its new home) under the same name. No view code needs
to change.
"""

from sms.models import (
    GradeFullMarks,
    LiveResult,
    ResultManagement,
    SchoolResultType,
    SchoolTerm,
    SchoolTermStatus,
    SchoolTerminology,
    WeightedResultManagement,
)

__all__ = [
    "GradeFullMarks",
    "LiveResult",
    "ResultManagement",
    "SchoolResultType",
    "SchoolTerm",
    "SchoolTermStatus",
    "SchoolTerminology",
    "WeightedResultManagement",
]
