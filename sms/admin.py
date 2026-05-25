from django.contrib import admin
from sms.models import (
    Teacher,
    TeacherSubjectAccess,
    BranchUser,
    Student,
    StudentSession,
    Homework,
    MarkObtained,
    SchoolBranch,
    SchoolGrade,
    Section,
    Subject,
    SchoolTerm,
    EduSession,
    StudentComplain,
)

# Register core teacher related models
admin.site.register(Teacher)
admin.site.register(TeacherSubjectAccess)
admin.site.register(BranchUser)

# Register useful educational models for admin debugging
admin.site.register(Student)
admin.site.register(StudentSession)
admin.site.register(Homework)
admin.site.register(MarkObtained)
admin.site.register(StudentComplain)

# Register structural models
admin.site.register(SchoolBranch)
admin.site.register(SchoolGrade)
admin.site.register(Section)
admin.site.register(Subject)
admin.site.register(SchoolTerm)
admin.site.register(EduSession)
