# old models

from django.contrib.auth.models import User
from django.db import models
from datetime import datetime
from nepali_datetime_field.models import NepaliDateField


# Create your models here.


class EduSession(models.Model):
    year = models.CharField(max_length=4)
    status = models.BooleanField(default=True)

    def __str__(self):
        return str(self.year)


class SuperBranchUser(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    range_start = models.BigIntegerField()
    range_end = models.BigIntegerField()

    def __str__(self):
        return self.user.username


class SchoolBranch(models.Model):
    name = models.CharField(max_length=200)
    city_id = models.CharField(max_length=200, blank=True, null=True)
    # models.ForeignKey(City, on_delete=models.CASCADE)
    location = models.CharField(max_length=200)
    phone = models.BigIntegerField()
    website = models.URLField(max_length=250, blank=True)
    email = models.EmailField(max_length=50)

    logo = models.FileField(upload_to='school/', blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    shortcode = models.CharField(
        max_length=20, unique=True, blank=True, null=True)

    status = models.BooleanField(default=True)
    is_branch = models.BooleanField(default=False)
    school = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True)

    min_reg = models.BigIntegerField(blank=True, null=True)
    max_reg = models.BigIntegerField(blank=True, null=True)
    owner = models.ForeignKey(SuperBranchUser, on_delete=models.CASCADE)
    slogan = models.CharField(max_length=250, blank=True, null=True)

    # def __str__(self):
    #     return '%s %s' % (self.name, self.location)

    def __str__(self):
        name_location = str(self.name) + ',' + str(self.location)
        return name_location


# class Grade(models.Model):
#     grade_name = models.CharField(max_length=200)
#     grade_value = models.CharField(max_length=5)
#     grade_weight = models.IntegerField()


class GradeLevel(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class SchoolGrade(models.Model):
    session = models.ForeignKey(EduSession, on_delete=models.CASCADE)
    school = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    level = models.ForeignKey(GradeLevel, on_delete=models.CASCADE)
    grade_name = models.CharField(max_length=200)
    active = models.BooleanField(default=True)
    grade_weight = models.IntegerField()

    class Meta:
        unique_together = (('school', 'grade_name'),)

    def __str__(self):
        return self.grade_name


class Section(models.Model):
    session = models.ForeignKey(EduSession, on_delete=models.CASCADE)
    grade = models.ForeignKey(SchoolGrade, on_delete=models.CASCADE)
    section = models.CharField(max_length=200)

    class Meta:
        unique_together = (('grade', 'section', 'session'),)

    def __str__(self):
        return self.section


class Subject(models.Model):
    session = models.ForeignKey(EduSession, on_delete=models.CASCADE)
    branch = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    grade = models.ForeignKey(SchoolGrade, on_delete=models.CASCADE)
    subject = models.CharField(max_length=200)
    status = models.BooleanField(default=True)
    heavy_weight = models.BooleanField(default=True)

    class Meta:
        unique_together = (('session', 'branch', 'grade', 'subject'),)

    def __str__(self):
        return self.subject


class SchoolAdminUser(models.Model):
    pass


class BranchUser(models.Model):
    school = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    admin_status = models.BooleanField(default=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    grade = models.ForeignKey(
        SchoolGrade, on_delete=models.CASCADE, blank=True, null=True)
    section = models.ForeignKey(
        Section, on_delete=models.CASCADE, blank=True, null=True)
    status = models.BooleanField(default=True)
    added_by = models.ForeignKey(SuperBranchUser, on_delete=models.CASCADE)
    # class Meta:
    #     unique_together = (('school', 'subject'),)

    def __str__(self):
        return self.user.username


class SchoolTermStatus(models.Model):
        value = models.CharField(max_length=100)

        
class SchoolTerm(models.Model):
    year = models.ForeignKey(EduSession, on_delete=models.CASCADE)
    school = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    term_name = models.CharField(max_length=200)
    name_in_short = models.CharField(max_length=200, null=True, blank=True)
    active = models.BooleanField(default=True)
    status = models.ForeignKey(SchoolTermStatus, on_delete=models.CASCADE, default=1)
    final_term = models.BooleanField(default=False)
    final_term_name = models.CharField(max_length=200, null=True, blank=True)
    class Meta:
        unique_together = (('year', 'school', 'term_name'),)

    def __str__(self):
        return str(self.term_name) + ',' + str(self.school.name) + ',' + str(self.school.location)


class ResultManagement(models.Model):
    school = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    year = models.ForeignKey(EduSession, on_delete=models.CASCADE)
    school_term = models.ForeignKey(SchoolTerm, on_delete=models.CASCADE)
    term_calculation = models.CharField(max_length=500)

    # class Meta:
    #     unique_together = (('school', 'year', 'school_term'),)

    def __str__(self):
        return self.school_term.term_name


class WeightedResultManagement(models.Model):
    school = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    year = models.ForeignKey(EduSession, on_delete=models.CASCADE)
    school_term = models.ForeignKey(SchoolTerm, on_delete=models.CASCADE)
    weight_config = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (('school', 'year', 'school_term'),)

    def __str__(self):
        return f"Weighted {self.school_term.term_name}"

class House(models.Model):
    school = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    name = models.CharField(max_length=500)

    def __str__(self):
       return self.name

class Student(models.Model):
    reg_no = models.CharField(max_length=9, primary_key=True, unique=True)
    pin_code = models.IntegerField()
    name = models.CharField(max_length=125)
    gender = models.BooleanField()
    dob = models.CharField(max_length=10, blank=True, null=True)

    iemis = models.BigIntegerField(blank=True, null=True)
    house = models.ForeignKey(House, on_delete=models.CASCADE, blank=True, null=True)
    
    temporary_address = models.CharField(max_length=150, blank=True, null=True)
    permanent_address = models.CharField(max_length=150, blank=True, null=True)

    fathers_name = models.CharField(max_length=50, blank=True, null=True)
    fathers_phone = models.BigIntegerField(blank=True, null=True)
    fathers_email = models.EmailField(max_length=100, blank=True, null=True)

    mothers_name = models.CharField(max_length=50, blank=True, null=True)
    mothers_phone = models.BigIntegerField(blank=True, null=True)
    mothers_email = models.EmailField(max_length=100, blank=True, null=True)

    guardian_name = models.CharField(max_length=50, blank=True, null=True)
    guardian_phone = models.BigIntegerField(blank=True, null=True)
    guardian_email = models.EmailField(max_length=100, blank=True, null=True)

    school = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)

    status = models.BooleanField(default=True)
    publish_result = models.BooleanField(default=True)

    added = models.DateTimeField(default=datetime.now)
    modified = models.DateTimeField(auto_now_add=True)

    old_data = models.TextField(blank=True, null=True)


    # class Meta:
    #     unique_together = (('roll_no','grade', 'section'),)

    def __str__(self):
        return self.name


class StudentSession(models.Model):
    session = models.ForeignKey(EduSession, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    grade = models.ForeignKey(SchoolGrade, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    roll_no = models.IntegerField()
    status = models.BooleanField(default=True)

    class Meta:
        unique_together = (('session', 'student', 'grade'),)


class GradeFullMarks(models.Model):
    session = models.ForeignKey(EduSession, on_delete=models.CASCADE)
    school = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    grade = models.ForeignKey(SchoolGrade, on_delete=models.CASCADE)
    term = models.ForeignKey(SchoolTerm, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    th_fm = models.IntegerField()
    pr_fm = models.IntegerField()
    th_pm = models.IntegerField()
    pr_pm = models.IntegerField()

    def __str__(self):
        return self.subject.subject


class MarkObtained(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    session = models.ForeignKey(EduSession, on_delete=models.CASCADE)
    school = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    grade = models.ForeignKey(SchoolGrade, on_delete=models.CASCADE)
    term = models.ForeignKey(SchoolTerm, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    th_mo = models.IntegerField()
    pr_mo = models.IntegerField()

    class Meta:
        unique_together = (('student', 'session', 'school',
                            'grade', 'term', 'subject'),)

    def __str__(self):
        return str(self.subject)


class TermResult(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    session = models.ForeignKey(EduSession, on_delete=models.CASCADE)
    school = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    grade = models.ForeignKey(SchoolGrade, on_delete=models.CASCADE)
    term = models.IntegerField()
    mo = models.CharField(max_length=500)


class Attendance(models.Model):
    reg_no = models.ForeignKey(
        Student, to_field='reg_no', on_delete=models.CASCADE)
    grade = models.ForeignKey(SchoolGrade, on_delete=models.CASCADE)
    session = models.ForeignKey(EduSession, on_delete=models.CASCADE)
    term = models.ForeignKey(SchoolTerm, on_delete=models.CASCADE, blank=True, null=True)
    no_of_school_days = models.IntegerField()
    no_of_present_days = models.IntegerField()
    no_of_absent_days = models.IntegerField()


class Rank(models.Model):
    reg_no = models.ForeignKey(
        Student, to_field='reg_no', on_delete=models.CASCADE)
    grade = models.ForeignKey(SchoolGrade, on_delete=models.CASCADE)
    session = models.ForeignKey(EduSession, on_delete=models.CASCADE)
    term = models.IntegerField()
    total_mark = models.IntegerField()
    section_rank = models.IntegerField()
    rank = models.IntegerField()


class SchoolResultType(models.Model):
    school = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    session = models.ForeignKey(EduSession, on_delete=models.CASCADE)
    result_type = models.IntegerField()


class LiveResult(models.Model):
    school = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    term = models.IntegerField()
    grade_list = models.CharField(max_length=250)
    status = models.BooleanField(default=True)
    calculation_type = models.CharField(max_length=20, default="legacy")


class UserStudent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)

    class Meta:
        unique_together = (('user', 'student'),)

    def __str__(self):
        return self.student.name


class CreatedUsers(models.Model):
    added_by = models.ForeignKey(User, on_delete=models.CASCADE)
    guardian = models.ForeignKey(User, related_name="guardian_name", on_delete=models.CASCADE)
    added_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    previous_data = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = (('added_by', 'guardian'),)

    def __str__(self):
        return str(self.guardian)


class Teacher(models.Model):
    added_by = models.ForeignKey(User, on_delete=models.CASCADE)
    teacher = models.ForeignKey(User, related_name="usernames", on_delete=models.CASCADE)
    added_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    previous_data = models.TextField(blank=True, null=True)
#
#
# class TeacherGradeAccess(models.Model):
#     teacher = models.ForeignKey(User, on_delete=models.CASCADE)
#     grade = models.ForeignKey(SchoolGrade, on_delete=models.CASCADE)
#
#


class TeacherSubjectAccess(models.Model):
    session = models.ForeignKey(EduSession, on_delete=models.CASCADE)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    grade = models.ForeignKey(SchoolGrade, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    status = models.BooleanField(default=True)


class Homework(models.Model):
    session = models.ForeignKey(EduSession, on_delete=models.CASCADE)
    grade = models.ForeignKey(SchoolGrade, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    homework = models.TextField()
    nepali_date = NepaliDateField()
    added_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)


class StudentComplain(models.Model):
    VERDICT_CHOICES = [
        ('good_progress', 'Good Progress'),
        ('need_attention', 'Need Attention'),
        ('immediate_concern', 'Immediate Concern'),
    ]
    
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    session = models.ForeignKey(EduSession, on_delete=models.CASCADE)
    school = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    grade = models.ForeignKey(SchoolGrade, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    term = models.ForeignKey(SchoolTerm, on_delete=models.CASCADE)
    
    # Positive points (multiple selection)
    positive_points = models.JSONField(default=list, blank=True)
    
    # Negative points (multiple selection)
    negative_points = models.JSONField(default=list, blank=True)
    
    # Teacher suggestions (multiple selection)
    teacher_suggestions = models.JSONField(default=list, blank=True)
    
    # Final verdict
    final_verdict = models.CharField(max_length=20, choices=VERDICT_CHOICES)
    
    # Additional comments
    additional_comments = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'session', 'term']
    
    def __str__(self):
        return f"{self.student.name} - {self.teacher.username} - {self.term.name}"


# update required
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator

class SchoolBranch(models.Model):
    name = models.CharField(max_length=200)
    city = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=200)
    phone = models.BigIntegerField()
    email = models.EmailField()
    logo = models.FileField(upload_to='logos/', blank=True)
    shortcode = models.SlugField(unique=True, blank=True)
    is_main_branch = models.BooleanField(default=False)
    parent_branch = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    min_registration = models.BigIntegerField(blank=True, null=True)
    max_registration = models.BigIntegerField(blank=True, null=True)
    slogan = models.CharField(max_length=250, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name}, {self.location}"

class AcademicSession(models.Model):
    name = models.CharField(max_length=9, unique=True)  # "2025-2026"
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class GradeLevel(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name

class Grade(models.Model):
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)
    branch = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    level = models.ForeignKey(GradeLevel, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=50)
    sequence = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [['session', 'branch', 'name']]
        ordering = ['sequence']

    def __str__(self):
        return f"{self.name} ({self.session.name})"

class Section(models.Model):
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='sections')
    name = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [['grade', 'name']]

    def __str__(self):
        return f"{self.grade.name} - {self.name}"

class House(models.Model):
    branch = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Student(models.Model):
    registration_number = models.CharField(max_length=20, unique=True)
    pin = models.CharField(max_length=10)
    name = models.CharField(max_length=125)
    gender = models.BooleanField(choices=((True, 'Male'), (False, 'Female')))
    date_of_birth = models.DateField(null=True, blank=True)
    temporary_address = models.TextField(blank=True)
    permanent_address = models.TextField(blank=True)
    father_name = models.CharField(max_length=100, blank=True)
    father_phone = models.BigIntegerField(null=True, blank=True)
    father_email = models.EmailField(blank=True)
    mother_name = models.CharField(max_length=100, blank=True)
    mother_phone = models.BigIntegerField(null=True, blank=True)
    mother_email = models.EmailField(blank=True)
    guardian_name = models.CharField(max_length=100, blank=True)
    guardian_phone = models.BigIntegerField(null=True, blank=True)
    guardian_email = models.EmailField(blank=True)
    branch = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class StudentEnrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    roll_number = models.PositiveIntegerField()
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)   # null means currently active
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['start_date']

    def __str__(self):
        end = self.end_date or 'present'
        return f"{self.student.name} – {self.grade.name} ({self.section.name}) {self.start_date} to {end}"

class StudentHouseAssignment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    house = models.ForeignKey(House, on_delete=models.CASCADE)
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['start_date']

    def __str__(self):
        end = self.end_date or 'present'
        return f"{self.student.name} – {self.house.name} ({self.start_date} to {end})"

class SubjectMaster(models.Model):
    code = models.CharField(max_length=20, unique=True)
    canonical_name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.canonical_name

class SubjectOffering(models.Model):
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)
    branch = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    subject = models.ForeignKey(SubjectMaster, on_delete=models.CASCADE)
    default_textbook = models.CharField(max_length=200, blank=True)
    is_heavy_weight = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [['session', 'branch', 'grade', 'section', 'subject']]

    def __str__(self):
        return f"{self.grade.name} - {self.section.name}: {self.subject.canonical_name}"

class StudentSubjectAlias(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)
    subject = models.ForeignKey(SubjectMaster, on_delete=models.CASCADE)
    custom_name = models.CharField(max_length=200)

    class Meta:
        unique_together = [['student', 'session', 'subject']]

    def __str__(self):
        return f"{self.student.name} - {self.session.name}: {self.custom_name}"

class Term(models.Model):
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)
    branch = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=20)
    is_final = models.BooleanField(default=False)
    sequence = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [['session', 'branch', 'name']]
        ordering = ['sequence']

    def __str__(self):
        return f"{self.name} ({self.session.name})"

class ExamFullMarks(models.Model):
    offering = models.ForeignKey(SubjectOffering, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    theory_full = models.PositiveSmallIntegerField(default=0)
    theory_pass = models.PositiveSmallIntegerField(default=0)
    practical_full = models.PositiveSmallIntegerField(default=0)
    practical_pass = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = [['offering', 'term']]

    def __str__(self):
        return f"{self.offering} - {self.term.name}"

class ScoreRecord(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    enrollment = models.ForeignKey(StudentEnrollment, on_delete=models.CASCADE)
    offering = models.ForeignKey(SubjectOffering, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    theory_marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    practical_marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    exam_date = models.DateField(null=True, blank=True)
    recorded_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['student', 'offering', 'term']]

    def total_obtained(self):
        return (self.theory_marks or 0) + (self.practical_marks or 0)

    def total_full(self):
        fm = self.offering.examfullmarks_set.get(term=self.term)
        return (fm.theory_full or 0) + (fm.practical_full or 0)

    def percentage(self):
        return (self.total_obtained() / self.total_full()) * 100 if self.total_full() else 0

class User(AbstractUser):
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('school_admin', 'School Admin'),
        ('teacher', 'Teacher'),
        ('viewer', 'Viewer'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer')
    branches = models.ManyToManyField(SchoolBranch, blank=True)
    mfa_secret = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.email

class TeacherSubjectAccess(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'teacher'})
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)
    offering = models.ForeignKey(SubjectOffering, on_delete=models.CASCADE)
    can_enter_marks = models.BooleanField(default=True)

    class Meta:
        unique_together = [['teacher', 'offering']]
