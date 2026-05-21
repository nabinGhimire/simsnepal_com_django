import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from django.contrib.auth.models import User
from sms.models import (
    EduSession, SuperBranchUser, SchoolBranch, GradeLevel, SchoolGrade, Section,
    SubjectMaster, Subject, Student, StudentSession, SchoolTerm, SchoolTermStatus,
    GradeFullMarks, MarkObtained, BranchUser
)

# 1. Create sessions
s2081, _ = EduSession.objects.get_or_create(year="2081", defaults={"status": True})
s2082, _ = EduSession.objects.get_or_create(year="2082", defaults={"status": True})

# 2. Create admin/owner user
admin_user, _ = User.objects.get_or_create(username="admin", defaults={
    "email": "admin@hamroschool.com",
    "first_name": "Ecosystem",
    "last_name": "Admin",
    "is_staff": True,
    "is_superuser": True
})
admin_user.set_password("admin123")
admin_user.save()

# 3. Create SuperBranchUser
sbu, _ = SuperBranchUser.objects.get_or_create(user=admin_user, defaults={
    "range_start": 1000,
    "range_end": 9999
})

# 4. Create SchoolBranch
school, _ = SchoolBranch.objects.get_or_create(shortcode="hamro_kathmandu", defaults={
    "name": "Hamro Secondary School",
    "location": "Kathmandu",
    "phone": 9801234567,
    "email": "contact@hamroschool.com",
    "owner": sbu,
    "status": True,
    "min_reg": 1000,
    "max_reg": 9999,
})

# 5. Create BranchUser
BranchUser.objects.get_or_create(school=school, user=admin_user, defaults={
    "admin_status": True,
    "status": True,
    "added_by": sbu
})

# 6. Create Grade Level & Grades
level, _ = GradeLevel.objects.get_or_create(id=1, defaults={"name": "Secondary Level"})
# GRADE 10 is shared, pointing to the current active session
g10, _ = SchoolGrade.objects.get_or_create(school=school, grade_name="GRADE 10", defaults={
    "level": level,
    "active": True,
    "grade_weight": 10,
    "session": s2082
})

# 7. Create Section (distinct sections per session)
sec_a_2081, _ = Section.objects.get_or_create(grade=g10, section="A", session=s2081)
sec_a_2082, _ = Section.objects.get_or_create(grade=g10, section="A", session=s2082)

# 8. Create SubjectMaster
sm_math, _ = SubjectMaster.objects.get_or_create(code="MATH10", defaults={
    "canonical_name": "Mathematics",
    "description": "Core Mathematics"
})
sm_sci, _ = SubjectMaster.objects.get_or_create(code="SCI10", defaults={
    "canonical_name": "Science & Technology",
    "description": "General Science"
})

# 9. Create Subjects (distinct subjects per session/section/grade)
sub_math_2081, _ = Subject.objects.get_or_create(session=s2081, branch=school, grade=g10, subject="MATHEMATICS", defaults={
    "subject_master": sm_math,
    "section": sec_a_2081
})
sub_math_2082, _ = Subject.objects.get_or_create(session=s2082, branch=school, grade=g10, subject="MATHEMATICS", defaults={
    "subject_master": sm_math,
    "section": sec_a_2082
})

sub_sci_2081, _ = Subject.objects.get_or_create(session=s2081, branch=school, grade=g10, subject="SCIENCE", defaults={
    "subject_master": sm_sci,
    "section": sec_a_2081
})
sub_sci_2082, _ = Subject.objects.get_or_create(session=s2082, branch=school, grade=g10, subject="SCIENCE", defaults={
    "subject_master": sm_sci,
    "section": sec_a_2082
})

# 10. Terms
term_status, _ = SchoolTermStatus.objects.get_or_create(id=1, defaults={"value": "Active"})
term_2081, _ = SchoolTerm.objects.get_or_create(year=s2081, school=school, term_name="First Term", defaults={
    "name_in_short": "T1",
    "active": True,
    "status": term_status
})
term_2082, _ = SchoolTerm.objects.get_or_create(year=s2082, school=school, term_name="First Term", defaults={
    "name_in_short": "T1",
    "active": True,
    "status": term_status
})

# 11. Full Marks configurations
GradeFullMarks.objects.get_or_create(session=s2081, school=school, grade=g10, term=term_2081, subject=sub_math_2081, defaults={
    "th_fm": 75, "pr_fm": 25, "th_pm": 30, "pr_pm": 10
})
GradeFullMarks.objects.get_or_create(session=s2081, school=school, grade=g10, term=term_2081, subject=sub_sci_2081, defaults={
    "th_fm": 75, "pr_fm": 25, "th_pm": 30, "pr_pm": 10
})
GradeFullMarks.objects.get_or_create(session=s2082, school=school, grade=g10, term=term_2082, subject=sub_math_2082, defaults={
    "th_fm": 75, "pr_fm": 25, "th_pm": 30, "pr_pm": 10
})
GradeFullMarks.objects.get_or_create(session=s2082, school=school, grade=g10, term=term_2082, subject=sub_sci_2082, defaults={
    "th_fm": 75, "pr_fm": 25, "th_pm": 30, "pr_pm": 10
})

# 12. Create a Student
student, _ = Student.objects.get_or_create(reg_no="1001", defaults={
    "pin_code": 1234,
    "name": "Ram Bahadur",
    "gender": True,
    "dob": "2065-05-15",
    "school": school,
    "status": True
})

# Enroll in both sessions
StudentSession.objects.get_or_create(session=s2081, student=student, grade=g10, defaults={"section": sec_a_2081, "roll_no": 1})
StudentSession.objects.get_or_create(session=s2082, student=student, grade=g10, defaults={"section": sec_a_2082, "roll_no": 1})

# 13. Create Marks
# Year 2081 (Previous year): Ram got 50/75 in Math Theory, 20/25 in Math Practical. Science: 45/75, 18/25.
MarkObtained.objects.get_or_create(student=student, session=s2081, school=school, grade=g10, term=term_2081, subject=sub_math_2081, defaults={
    "th_mo": 50, "pr_mo": 20, "is_absent": False
})
MarkObtained.objects.get_or_create(student=student, session=s2081, school=school, grade=g10, term=term_2081, subject=sub_sci_2081, defaults={
    "th_mo": 45, "pr_mo": 18, "is_absent": False
})

# Year 2082 (Current year): Ram got 60/75 in Math, and was absent in Science!
MarkObtained.objects.get_or_create(student=student, session=s2082, school=school, grade=g10, term=term_2082, subject=sub_math_2082, defaults={
    "th_mo": 60, "pr_mo": 22, "is_absent": False
})
MarkObtained.objects.get_or_create(student=student, session=s2082, school=school, grade=g10, term=term_2082, subject=sub_sci_2082, defaults={
    "th_mo": 0, "pr_mo": 0, "is_absent": True
})

print("Database successfully seeded with testing profiles and multi-session marks history!")
