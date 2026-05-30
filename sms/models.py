from django.contrib.auth.models import User
from django.db import models
from datetime import datetime
from nepali_datetime_field.models import NepaliDateField
from sms.middleware import get_current_request
from .managers import SafeBranchUserManager


class SafeBranchUserQuerySet(models.QuerySet):
    def get(self, *args, **kwargs):
        try:
            return super().get(*args, **kwargs)
        except self.model.MultipleObjectsReturned:
            qs = self.filter(*args, **kwargs)
            
            request = get_current_request()
            if request and hasattr(request, 'session') and request.session:
                sso_business = request.session.get('sso_business', {})
                business_id = sso_business.get('id')
                if business_id:
                    preferred_qs = qs.filter(school__shortcode=business_id)
                    if preferred_qs.exists():
                        active_pref = preferred_qs.filter(status=True)
                        if active_pref.exists():
                            return active_pref.first()
                        return preferred_qs.first()
            
            active_qs = qs.filter(status=True)
            if active_qs.exists():
                return active_qs.first()
            return qs.first()



class SchoolScopedQuerySet(models.QuerySet):
    def filter(self, *args, **kwargs):
        """Automatically filter by current school if session provides it.
        This ensures any QuerySet operation respects multi‑tenant isolation.
        """
        request = get_current_request()
        if request and hasattr(request, "session") and request.session:
            sso_business = request.session.get("sso_business", {})
            business_id = sso_business.get("id")
            if business_id:
                # Add school filter directly to kwargs to avoid recursion
                kwargs.setdefault('school__shortcode', business_id)
        return super().filter(*args, **kwargs)

class SchoolScopedManager(models.Manager):
    def get_queryset(self):
        return SchoolScopedQuerySet(self.model, using=self._db)


    def get(self, *args, **kwargs):
        return self.get_queryset().get(*args, **kwargs)



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
    location = models.CharField(max_length=200)
    phone = models.BigIntegerField()
    website = models.URLField(max_length=250, blank=True)
    email = models.EmailField(max_length=50)

    logo = models.FileField(upload_to='school/', blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    shortcode = models.CharField(
        max_length=40, unique=True, blank=True, null=True)

    status = models.BooleanField(default=True)
    is_branch = models.BooleanField(default=False)
    school = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True)

    min_reg = models.BigIntegerField(blank=True, null=True)
    max_reg = models.BigIntegerField(blank=True, null=True)
    owner = models.ForeignKey(SuperBranchUser, on_delete=models.CASCADE)
    slogan = models.CharField(max_length=250, blank=True, null=True)

    def __str__(self):
        name_location = str(self.name) + ',' + str(self.location)
        return name_location


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
    school = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE, null=True, blank=True)
    section = models.CharField(max_length=200)

    class Meta:
        unique_together = (('school', 'grade', 'section', 'session'),)

    objects = SchoolScopedManager()

    def __str__(self):
        return self.section


class SubjectMaster(models.Model):
    school = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE, null=True, blank=True)
    code = models.CharField(max_length=20)
    canonical_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = (('school', 'code'), ('school', 'canonical_name'))

    objects = SchoolScopedManager()



class Subject(models.Model):
    session = models.ForeignKey(EduSession, on_delete=models.CASCADE)
    branch = models.ForeignKey(SchoolBranch, on_delete=models.CASCADE)
    grade = models.ForeignKey(SchoolGrade, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE, null=True, blank=True)
    subject_master = models.ForeignKey(SubjectMaster, on_delete=models.CASCADE, null=True, blank=True)
    subject = models.CharField(max_length=200)
    status = models.BooleanField(default=True)
    heavy_weight = models.BooleanField(default=True)

    class Meta:
        unique_together = (('session', 'branch', 'grade', 'section', 'subject'),)

    def __str__(self):
        if self.section:
            return f"{self.subject} ({self.grade} - {self.section})"
        return f"{self.subject} ({self.grade})"


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

    objects = SafeBranchUserManager()

    def __str__(self):
        return self.user.username


class SchoolTermStatus(models.Model):
    value = models.CharField(max_length=100)

    def __str__(self):
        return self.value

        
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
    
    avatar = models.FileField(upload_to='students/avatars/', blank=True, null=True)

    added = models.DateTimeField(default=datetime.now)
    modified = models.DateTimeField(auto_now_add=True)

    old_data = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name
        
    def get_avatar(self, session=None):
        if session:
            try:
                student_session = self.studentsession_set.get(session=session)
                if student_session.avatar:
                    return student_session.avatar
            except (StudentSession.DoesNotExist, StudentSession.MultipleObjectsReturned):
                pass
        return self.avatar


class StudentSession(models.Model):
    session = models.ForeignKey(EduSession, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    grade = models.ForeignKey(SchoolGrade, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    roll_no = models.IntegerField()
    status = models.BooleanField(default=True)
    
    avatar = models.FileField(upload_to='students/sessions/', blank=True, null=True)
    parent_can_view_result = models.BooleanField(default=True)
    parent_can_view_homework = models.BooleanField(default=True)

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
    is_absent = models.BooleanField(default=False)

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

    def __str__(self):
        return self.teacher.username


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
    
    positive_points = models.JSONField(default=list, blank=True)
    negative_points = models.JSONField(default=list, blank=True)
    teacher_suggestions = models.JSONField(default=list, blank=True)
    
    final_verdict = models.CharField(max_length=20, choices=VERDICT_CHOICES)
    additional_comments = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'session', 'term']
    
    def __str__(self):
        return f"{self.student.name} - {self.teacher.username} - {self.term.term_name}"
