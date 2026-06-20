# # from django.shortcuts import render
# # from django.http import Http404, HttpResponse, HttpResponseRedirect
# # from django.contrib.auth.decorators import login_required
# # from django.views.generic import View
# # from .forms import SignUpForm
# # from django.contrib.auth.models import User
# # from django.contrib.auth import authenticate, update_session_auth_hash
# # from django.contrib.auth.forms import PasswordChangeForm
# # from django.contrib import messages

# # from django.shortcuts import redirect
# # from django.contrib.auth.hashers import make_password
# # from sms.models import *
# # import json

# # from django.db.models import Max
# # from random import randint
# # from datetime import datetime
# # from django.views.generic import View
# # from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
# # from django.contrib.auth.decorators import login_required
# # from collections import OrderedDict

# # # Create your views here.
# # from .func import *

# # # from .student_reg import my_students
# # from django.db.models import Q

# # from io import BytesIO
# # from django.template.loader import get_template
# # # from xhtml2pdf import pisa
# # import logging
# # from collections import defaultdict

# import logging
# import secrets
# import requests
# from django.conf import settings
# from django.shortcuts import render, redirect
# from django.contrib.auth.decorators import login_required
# from django.contrib.auth.hashers import make_password
# from django.contrib.auth.models import User
# from django.contrib import messages
# from sms.models import *                     # Teacher, BranchUser, Subject, TeacherSubjectAccess
# from sso.models import HamroUserProfile
# # from session.models import get_current_session
# from .func import *

# Standard library
import json
import logging
import secrets
import csv
from collections import OrderedDict, defaultdict
from datetime import datetime
from io import BytesIO
from random import randint

# Third-party
import requests

# Django core
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Max, Q
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.template.loader import get_template
from django.views.generic import View

# Local apps
from .forms import SignUpForm, SchoolForm
from .func import *
from sms.models import *   # Teacher, BranchUser, Subject, TeacherSubjectAccess
from sso.models import HamroUserProfile

logger = logging.getLogger(__name__)

this_year = 2083

def get_current_session():
    """Helper to get the current session without executing on import."""
    from sms.middleware import get_current_request
    request = get_current_request()
    if request and hasattr(request, 'session') and request.session:
        active_session_id = request.session.get('active_session_id')
        if active_session_id:
            try:
                return EduSession.objects.get(id=active_session_id)
            except EduSession.DoesNotExist:
                pass
    try:
        # Hardcoded for now as per original logic, but wrapped in a function
        return EduSession.objects.get(year=this_year)
    except EduSession.DoesNotExist:
        return EduSession.objects.filter(status=True).order_by('-year').first()


def get_branch_info(user):
    """Helper to get branch and school info for a user."""
    try:
        branchuser = BranchUser.objects.select_related('school').get(user=user)
        if not branchuser.school.status:
            return None, "Sorry! School has been disabled."
        return branchuser, None
    except BranchUser.DoesNotExist:
        return None, "Sorry! You are not allowed to access this page."
    except Exception as e:
        logger.error(f'Error in get_branch_info: {e}')
        return None, "Sorry! You are not allowed to access this page."

# Security utility to ensure the accessed object belongs to the user's school
def ensure_branch_user(request, obj):
    """Raise HttpResponseForbidden if obj does not belong to the user's school.
    Supports objects with a direct `school` attribute or a related `grade.school`.
    """
    from django.http import HttpResponseForbidden
    branchuser, err = get_branch_info(request.user)
    if err:
        return HttpResponseForbidden(err)
    # Determine the object's school
    if hasattr(obj, 'school'):
        obj_school = obj.school
    elif hasattr(obj, 'grade') and hasattr(obj.grade, 'school'):
        obj_school = obj.grade.school
    else:
        # Unknown object type, deny access
        return HttpResponseForbidden('Access denied.')
    if obj_school.id != branchuser.school.id:
        # Render custom error page
        return HttpResponseForbidden(render(request, 'panel/access_denied.html'))
    # If all good, return None (no response)
    return None

exam_board = [10]

@login_required
def index(request):
    user = request.user
    if CreatedUsers.objects.filter(guardian=user).exists():
        return redirect("/guardian/")
    if SuperBranchUser.objects.filter(user=user).exists():
        if not BranchUser.objects.filter(user=user, status=True).exists():
            return redirect("/superuser/")
    
    if Teacher.objects.filter(teacher=user).exists():
        try:
            this_teacher = Teacher.objects.get(teacher=user)          
            branchuser, error = get_branch_info(this_teacher.added_by)
            if error:
                return HttpResponse(f'{error} Click <a href="/logout/">Here</a> to login using different account.')
            return redirect("/teacher/")
        except Teacher.DoesNotExist:
            pass

    branchuser, error = get_branch_info(user)
    if error:
        return HttpResponse(f'{error} Click <a href="/logout/">Here</a> to login using different account.')

    schoolbranch = branchuser.school
    current_session = get_current_session()

    from django.db.models import Count, Q
    
    grade_level = GradeLevel.objects.filter(schoolgrade__school=schoolbranch, schoolgrade__active=True).distinct().order_by("id")
    # Optimize: Use annotation to get male/female/total counts in a single query
    grades = SchoolGrade.objects.filter(school=schoolbranch, active=True).annotate(
        male_count=Count('studentsession', filter=Q(studentsession__session=current_session, studentsession__status=True, studentsession__student__gender=True)),
        female_count=Count('studentsession', filter=Q(studentsession__session=current_session, studentsession__status=True, studentsession__student__gender=False)),
        total_count=Count('studentsession', filter=Q(studentsession__session=current_session, studentsession__status=True))
    ).order_by("grade_weight")

    total_grades = {
        grade.id: {
            "name": grade.grade_name,
            "male": grade.male_count,
            "female": grade.female_count,
            "total": grade.total_count
        } for grade in grades
    }

    context = {
        "grade_level": grade_level,
        "grades": grades,
        "branchuser": branchuser,
        "school": schoolbranch,
        "total_grades": total_grades
    }
    return render(request, "panel/index.html", context)


@login_required
def set_theme(request):
    theme = request.GET.get('theme', 'default')
    if theme not in ['default', 'tabler']:
        theme = 'default'

    next_url = request.META.get('HTTP_REFERER', '/panel/')
    response = HttpResponseRedirect(next_url)
    response.set_cookie('theme', theme, max_age=60*60*24*365, httponly=False)
    return response


def login(request):
    print(request)
    if request.method == "POST":
        print(request)
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(username=username, password=password)
        if user is not None:
            auth_login(request, user)
            print("user found", user)
            return redirect("/panel/")
        else:
            print("user not found", user)
            return redirect("/login/")

            # print(username, password)
        # print('POST')
        # for key in request.POST:
        #     print(key)
        #     value = request.POST[key]
        #     print(value)
    else:
        print("its a get not a post")
    return render(request, "panel/login.html")


def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        # print(form.)
        print(form.errors)
        if form.is_valid():
            # form.save()
            username = form.cleaned_data.get("username")
            print(username)
            email = form.cleaned_data.get("email")
            raw_password = form.cleaned_data.get("password1")
            newuser = User.objects.create_user(username, email, raw_password)
            newuser.first_name = form.cleaned_data.get("first_name")
            newuser.last_name = form.cleaned_data.get("last_name")
            newuser.save()
            print(newuser)
            user = authenticate(username=username, password=raw_password)
            auth_login(request, user)
            return redirect("/")
        else:
            print("form is not valid")
    else:
        form = SignUpForm()

    return render(request, "panel/signup.html", {"form": form})


def recover(request):
    return render(request, "panel/recover.html")


@login_required
def profile(request):
    user = request.user
    branchuser, error = get_branch_info(user)
    if error:
        return HttpResponse(error)
    school = branchuser.school
    grade_level = GradeLevel.objects.filter(schoolgrade__school=school, schoolgrade__active=True).distinct().order_by("id")
    
    # Initialize the password change form
    password_form = PasswordChangeForm(user)
    
    context = {
        "grade_level": grade_level,
        "branchuser": branchuser,
        "school": school,
        "user": user,
        "password_form": password_form,
    }
    return render(request, "panel/profile.html", context)


@login_required
def lockscreen(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]

        user = authenticate(username=username, password=password)
        auth_login(request, user)
        return redirect("/")

    username = None
    if request.user.is_authenticated:
        username = request.user.username
        # username = request.user.username
        logout(request)
    else:
        return redirect("/login/")
    context = {"username": username}
    return render(request, "panel/lock-screen.html", context)


def undermaintenance(request):
    return render(request, "panel/undermaintenance.html")


def mail(request):
    return render(request, "panel/email-inbox.html")


def mailread(request, mailid):
    return render(request, "panel/email-read.html")


def addgrade(request, level):
    user = request.user
    message = " "
    success = ""
    branchuser, error = get_branch_info(user)
    if error:
        return HttpResponse(error)
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )

    gradelevel = GradeLevel.objects.get(id=level)
    schoolbranch = SchoolBranch.objects.get(id=branchuser.school_id)

    if request.method == "POST":

        grade_name = request.POST.get("grade_name").upper()
        grade_weight = request.POST.get("grade_weight")

        if SchoolGrade.objects.filter(school=schoolbranch, grade_name=grade_name).count() == 0 :
            schoolgrade = SchoolGrade()
            schoolgrade.school = schoolbranch
            schoolgrade.level = gradelevel
            schoolgrade.grade_name = grade_name
            schoolgrade.grade_weight = grade_weight
            schoolgrade.session = get_current_session()
            schoolgrade.save()
            if schoolgrade.id != None:
                message = grade_name + " has been added successfully."
                success = True

                print(message, success)
        else:
            message = "Duplicate entry found for " + grade_name
            success = False

    grade_level = GradeLevel.objects.all()
    grades = SchoolGrade.objects.filter(school=schoolbranch).order_by("id")

    context = {
        "grade_level": grade_level,
        "grades": grades,
        "gradelevel": gradelevel,
        "branchuser": branchuser,
        "message": message,
        "success": success,
        "school":schoolbranch,
    }
    return render(request, "panel/addgrade.html", context)


@login_required
def listgradeitems(request, gradelevel):

    user = request.user
    message = " "
    success = ""
    subjects = ""
    allsection = ""
    student = ""

    branchuser, error = get_branch_info(user)
    if error:
        return HttpResponse(error)
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )

    schoolbranch = SchoolBranch.objects.get(id=branchuser.school_id)

    grade_level = GradeLevel.objects.all()
    grades = SchoolGrade.objects.filter(school=schoolbranch).order_by("id")

    avaiablesections = Section.objects.filter(grade=gradelevel, school=branchuser.school)
    grade_obj = SchoolGrade.objects.get(id=int(gradelevel))
    # Security check: ensure grade belongs to user's school
    resp = ensure_branch_user(request, grade_obj)
    if resp:
        return resp
    subjects = Subject.objects.filter(branch=branchuser.school, grade=grade_obj.id)
    # Use grade_obj for further logic
    gradelevel = grade_obj
    students = Student.objects.filter(school=branchuser.school, grade=gradelevel.id)

    section = False
    teacher = False
    subject = False
    list_student = False

    if request.method == "GET" and "list" in request.GET:
        list_item = request.GET["list"]

        if list_item == "student":
            list_student = True

    if request.method == "GET" and "add" in request.GET:
        add = request.GET["add"]
        if add == "section":
            # Show the Add Section form on the same page; preserve all query parameters
            section = True
        elif add == "subject":
            subject = True
        elif add == "student":
            student = True
        elif add == "teacher":
            teacher = True
        else:
            return HttpResponse(
                'Sorry! Something went wrong. Click <a href="/">Here</a> to go the homepage.'
            )

    if request.method == "GET" and "section" in request.GET:
        section = True

    context = {
        "grade_level": grade_level,
        "g_level": gradelevel,
        "gradelevel": gradelevel.id,
        "grades": grades,
        "branchuser": branchuser,
        "section": section,
        "subject": subject,
        "teacher": teacher,
        "student": student,
        "students": students,
        "male_count": male_count,
        "female_count": female_count,
        "avaiablesections": avaiablesections,
        "male_count": male_count,
        "female_count": female_count,
        "subjects": subjects,
        "list_student": list_student,
        "school":schoolbranch,
    }
    return render(request, "panel/listgradeitems.html", context)




@login_required
def addsubject(request):
    this_session = get_current_session()
    user = request.user
    if request.method == 'POST':
        gradelevel = request.POST.get('gradelevel')
        redurl = request.POST.get('redurl')
        subject_master_id = request.POST.get('subject_master')
        section_id = request.POST.get('section')
        internal_name = request.POST.get('subjectname', '').strip()

        try:
            grade = SchoolGrade.objects.get(id=gradelevel)
        except (ValueError, SchoolGrade.DoesNotExist):
            return HttpResponse("Grade not found.")

        try:
            userbranch = BranchUser.objects.get(user=user)
        except BranchUser.DoesNotExist:
            return HttpResponse("Branch user not found.")

        try:
            sm = SubjectMaster.objects.get(id=subject_master_id)
        except (ValueError, TypeError, SubjectMaster.DoesNotExist):
            messages.error(request, "Invalid Standard Subject selected.")
            return HttpResponseRedirect(redurl)

        # Fallback to canonical name if custom internal name is empty
        if not internal_name:
            internal_name = sm.canonical_name

        # Resolve section if provided
        section = None
        if section_id:
            try:
                section = Section.objects.get(id=section_id)
            except (ValueError, TypeError, Section.DoesNotExist):
                pass

        subject_upper = internal_name.strip().upper()

        # Check unique constraint: (session, branch, grade, section, subject)
        if Subject.objects.filter(
            session=this_session,
            branch=userbranch.school,
            grade=grade,
            section=section,
            subject=subject_upper
        ).exists():
            messages.error(request, f"Subject '{subject_upper}' is already assigned to this grade/section in the current session.")
        else:
            Subject.objects.create(
                session=this_session,
                branch=userbranch.school,
                grade=grade,
                section=section,
                subject_master=sm,
                subject=subject_upper
            )
            messages.success(request, f"Subject '{subject_upper}' added successfully.")

        return HttpResponseRedirect(redurl)

    else:
        return HttpResponse('Sorry! Something went wrong. Click <a href="/">Here</a> to go the homepage.')


@login_required
def addteacher(request):
    user = request.user
    if request.method == "POST":
        gradelevel = request.POST.get("gradelevel")
        redurl = request.POST.get("redurl")
        username = request.POST.get("teachersname")
        section = request.POST.get("section")
        password = request.POST.get("password")

        # print(gradelevel, grade, section)

        grade = SchoolGrade.objects.get(id=gradelevel)
        # Security check: ensure grade belongs to user's school
        resp = ensure_branch_user(request, grade)
        if resp:
            return resp
        userbranch, error = get_branch_info(user)
        if error:
            return HttpResponse(error)

        print(username, gradelevel, userbranch.school.id, section)
        print(userbranch.school)

        # BranchUser.objects.filter()

        # Subject.objects.get_or_create(branch=userbranch.school, grade=grade,subject=subject.upper())

        # Section.objects.get_or_create(grade=grade,section=sectionname.upper())

        return HttpResponseRedirect(redurl)

    else:
        return HttpResponse(
            'Sorry! Something went wrong. Click <a href="/">Here</a> to go the homepage.'
        )


@login_required
def addstudent(request):
    user = request.user
    if request.method == "POST":
        gradelevel = request.POST.get("gradelevel")
        redurl = request.POST.get("redurl")

        # Required fields
        studentname = request.POST.get("studentname", "").strip()
        rollno = request.POST.get("rollno")
        gender_str = request.POST.get("gender")
        section = request.POST.get("section")

        missing_fields = []
        if not studentname:
            missing_fields.append("Student Name")
        if not rollno:
            missing_fields.append("Roll No.")
        if gender_str not in ["True", "False"]:
            missing_fields.append("Gender")
        if not section:
            missing_fields.append("Section")

        if missing_fields:
            messages.error(request, f"Missing required fields: {', '.join(missing_fields)}")
            return HttpResponseRedirect(redurl or "/panel/")

        gender = gender_str == "True"
        # Begin student creation logic
        branchuser, err = get_branch_info(user)
        if err:
            messages.error(request, err)
            return HttpResponseRedirect(redurl or "/panel/")
        school = branchuser.school

        # Generate new registration number
        reg_no = findNewRegNo(school.id)

        # Gather optional fields
        optional_fields = {
            "dob": request.POST.get("dob"),
            "iemis": request.POST.get("iemis"),
            "house_id": request.POST.get("house"),
            "temporary_address": request.POST.get("tempaddr"),
            "permanent_address": request.POST.get("peraddr"),
            "fathers_name": request.POST.get("fathersname"),
            "fathers_phone": request.POST.get("fathersphone"),
            "fathers_email": request.POST.get("fathersemail"),
            "mothers_name": request.POST.get("mothersname"),
            "mothers_phone": request.POST.get("mothersphone"),
            "mothers_email": request.POST.get("mothersemail"),
            "guardian_name": request.POST.get("guardianname"),
            "guardian_phone": request.POST.get("guardianphone"),
            "guardian_email": request.POST.get("guardianemail"),
        }

        student = Student(
            reg_no=reg_no,
            pin_code= randint(1000, 9999),
            name=studentname,
            gender=gender,
            dob=optional_fields["dob"],
            iemis=optional_fields["iemis"],
            school=school,
            status=True,
            publish_result=True,
        )
        # Set optional foreign keys if provided
        if optional_fields["house_id"]:
            try:
                student.house = House.objects.get(id=optional_fields["house_id"])
            except House.DoesNotExist:
                pass
        # Assign remaining optional fields
        student.temporary_address = optional_fields["temporary_address"]
        student.permanent_address = optional_fields["permanent_address"]
        student.fathers_name = optional_fields["fathers_name"]
        student.fathers_phone = optional_fields["fathers_phone"]
        student.fathers_email = optional_fields["fathers_email"]
        student.mothers_name = optional_fields["mothers_name"]
        student.mothers_phone = optional_fields["mothers_phone"]
        student.mothers_email = optional_fields["mothers_email"]
        student.guardian_name = optional_fields["guardian_name"]
        student.guardian_phone = optional_fields["guardian_phone"]
        student.guardian_email = optional_fields["guardian_email"]
        student.save()

        # Resolve grade and section objects
        try:
            grade_obj = SchoolGrade.objects.get(id=gradelevel)
            section_obj = Section.objects.get(id=section)
        except (SchoolGrade.DoesNotExist, Section.DoesNotExist):
            messages.error(request, "Invalid grade or section.")
            return HttpResponseRedirect(redurl or "/panel/")

        # Create StudentSession linking to grade and section
        StudentSession.objects.create(
            session=get_current_session(),
            student=student,
            grade=grade_obj,
            section=section_obj,
            roll_no=rollno,
            status=True,
        )

        messages.success(request, f"Student {student.name} added successfully.")
        return HttpResponseRedirect(redurl or "/panel/")



def findNewRegNo(school):
    if Student.objects.filter(school=school).count() != 0:
        max_reg_no = Student.objects.filter(school=school).aggregate(Max("reg_no"))[
            "reg_no__max"
        ]
        max_student = Student.objects.get(reg_no=max_reg_no)

        new_reg = int(max_student.reg_no) + 1
        school = SchoolBranch.objects.get(id=school)
        if new_reg >= school.max_reg:
            return HttpResponse(
                'Sorry! Something went wrong. Click <a href="/">Here</a> to go the homepage.'
            )
        else:
            return new_reg
    else:
        school = SchoolBranch.objects.get(id=school)

        return int(school.min_reg) + 1


@login_required
def editstudentdetailbyregno(request, regno):
    user = request.user
    branchuser, error = get_branch_info(user)
    if error:
        return HttpResponse(error)
    reg_finder = Student.objects.filter(reg_no=regno)
    message = False
    if reg_finder.count() == 1:
        student = Student.objects.get(reg_no=regno)
        if branchuser.school == student.school:
            avaiablesections = Section.objects.filter(grade=student.grade)
            if request.method == "POST":
                studentname = request.POST.get("studentname")
                rollno = request.POST.get("rollno")
                gender = request.POST.get("gender")
                section = request.POST.get("section")

                section = Section.objects.get(id=section)

                student.name = studentname
                student.roll_no = rollno
                student.gender = gender
                student.section = section
                try:
                    student.save()
                except:
                    return HttpResponse(
                        'Sorry! something went wrong. Click <a href="/panel/">Here</a> to go the panel.'
                    )

                success = True
                student = Student.objects.get(reg_no=regno)
                message = "Details of Student " + student.name + " has been updated."

                context = {
                    "student": student,
                    "avaiablesections": avaiablesections,
                    "message": message,
                    "success": success,
                }
                return render(request, "panel/editstudent_byreg_no.html", context)

            else:
                context = {"student": student, "avaiablesections": avaiablesections}
                return render(request, "panel/editstudent_byreg_no.html", context)
        else:
            return HttpResponse(
                'Sorry! something went wrong. You have no access to edit information of this Student. Click <a href="/panel/">Here</a> to go the panel.'
            )
    else:
        return HttpResponse(
            'Sorry! something went wrong. We could not find the Registration Number. Click <a href="/">Here</a> to go the homepage.'
        )


# def printentrancecard(request):
#     user = request.user
#     if user.id != 16:
#         width = 50
#         logo = "https://grihakarya.hamro.com/samataeast/images/logo1.jpg"
#     else:
#         width = 50
#         logo = "http://school3.nep.onl/wp-content/uploads/sites/8/2019/12/51150449_1650894705012798_8214025074135531520_n.png"
#     branchuser = BranchUser.objects.get(user=user)
#     school = SchoolBranch.objects.get(id=branchuser.school.id)
#
#     if request.method == "POST":
#         term = request.POST.get("term")
#         whattype = request.POST.get("whattype")
#         if whattype == "True":
#             whattype = True
#         else:
#             whattype = False
#         print(term)
#         students = Student.objects.filter(school=school, status=True).exclude(grade=110)
#         count = students.count()
#         print(students)
#         term_exam = SchoolTerm.objects.get(id=term)
#
#         if whattype:
#             context = {
#                 "school": school,
#                 "students": students,
#                 "count": count,
#                 "term_exam": term_exam,
#                 "year": this_year,
#                 "logo": logo,
#                 "width": width,
#                 "blankcount": "12345678",
#             }
#
#             return render(request, "panel/entrancecard.html", context)
#         else:
#             context = {
#                 "school": school,
#                 "term_exam": term_exam,
#                 "year": this_year,
#                 "logo": logo,
#                 "width": width,
#                 "blankcount": "12345678",
#             }
#
#             return render(request, "panel/entrancecardblank.html", context)
#
#     exam_types = SchoolTerm.objects.filter(school=branchuser.school)
#
#     grades = SchoolGrade.objects.filter(school=branchuser.school)
#
#     context = {"grades": grades, "school": school, "exam_types": exam_types}
#     return render(request, "panel/entrancecardbase.html", context)

#
# @login_required
# class PrintEntranceCard(View):
#     def get(self, request, *args, **kwargs):
#         user = request.user
#         branchuser = BranchUser.objects.get(user=user)
#         school = SchoolBranch.objects.get(id=branchuser.school.id)
#
#         exam_types = SchoolTerm.objects.filter(school=branchuser.school)
#
#         grades = SchoolGrade.objects.filter(school=branchuser.school)
#
#         context = {
#             "grades": grades,
#             "school": school,
#             "branch": branch,
#             "exam_types": exam_types,
#         }
#         return render(request, "panel/entrancecardbase.html", context)
#
#     def post(self, request, *args, **kwargs):
#         branch4user = find_branch_for_user(request.user)
#         if branch4user == False:
#             return HttpResponse("You do not have rights to access this page ")
#         else:
#             # print('Branch: ',branch4user['branch'])
#             school = branch4user["school"]
#             branch = branch4user["branch"]
#             # print(school.id)
#             # print(branch.id)
#
#         print(request.POST)
#         term = request.POST.get("term")
#         this_term = V2TerminalExams.objects.get(
#             school=school, branch=branch, value=term
#         )
#         students = (
#             Student.objects.filter(school=school, branch=branch)
#                 .exclude(grade_id__exact=14)
#                 .exclude(status=0)
#                 .order_by("grade")
#         )
#         context = {
#             "school": school,
#             "branch": branch,
#             "this_term": this_term,
#             "year": year,
#             "students": students,
#             "count": 2,
@login_required
@login_required
def student_detail(request, grade=False, section=False):
    user = request.user
    branchuser, error = get_branch_info(user)
    if error:
        return HttpResponse(f'{error} Click <a href="/panel/">Here</a> to go the panel.')
        
    school = branchuser.school
    current_session = get_current_session()
    
    # If accessed without POST or GET parameters, show the selector BASE page
    if request.method == "GET" and not grade:
        grades = SchoolGrade.objects.filter(school=school, active=True).order_by('grade_weight')
        sections = Section.objects.filter(grade__school=school, session=current_session).select_related('grade')
        
        section_list = {}
        for sec in sections:
            g_id = str(sec.grade_id)
            if g_id not in section_list:
                section_list[g_id] = {}
            section_list[g_id][str(sec.id)] = sec.section

        context = {
            "branchuser": branchuser,
            "school": school,
            "grades": grades,
            "section_list": json.dumps(section_list)
        }
        return render(request, "panel/student_detail_base.html", context)

    # Process filters from URL or POST
    # target variables will be set below with 'all' handling

    grade_print = section_print = this_grade = this_section = False
    students = OrderedDict()

    # Determine target grade and section, supporting 'all' selection
    target_grade_id = grade or request.POST.get("grade")
    target_section_id = section or request.POST.get("section")
    info_type = request.POST.get("info_type", "current")

    grade_print = section_print = False
    # If 'all' is selected for grade, treat as no specific grade filter
    if not target_grade_id or target_grade_id == "all":
        school_grade_qs = SchoolGrade.objects.filter(school=school, active=True).order_by('grade_weight')
    else:
        school_grade_qs = SchoolGrade.objects.filter(id=target_grade_id)
        grade_print = True

    # Handle section filter; ignore if 'all' selected
    if target_section_id and target_section_id != "all":
        try:
            this_section = Section.objects.get(id=target_section_id)
            section_print = True
        except Section.DoesNotExist:
            return HttpResponse('Section not found.')
    else:
        this_section = None


    for sg in school_grade_qs:
        this_grade = sg
        query = Q(session=current_session, grade=sg, status=True)
        if this_section:
            query &= Q(section=this_section)
        
        student_in_session = StudentSession.objects.filter(query).select_related(
            'student', 'grade', 'section'
        ).order_by('section', 'roll_no', 'student')

        for sis in student_in_session:
            students[sis.student.reg_no] = {
                'reg_no': sis.student.reg_no,
                'name': sis.student.name,
                'grade': sis.grade.grade_name,
                'section': sis.section,
                'pin_code': sis.student.pin_code,
                'gender': sis.student.gender,
                'roll_no': sis.roll_no,
                'fathers_name': sis.student.fathers_name,
                'mothers_name': sis.student.mothers_name,
                'guardian_name': sis.student.guardian_name,
                'guardian_phone': sis.student.guardian_phone,
                'guardian_email': sis.student.guardian_email,
                'fathers_email': sis.student.fathers_email,
                'mothers_email': sis.student.mothers_email,
                'fathers_phone': sis.student.fathers_phone,
                'mothers_phone': sis.student.mothers_phone,
                'house': sis.student.house.name if sis.student.house else '',
                'temporary_address': sis.student.temporary_address,
                'permanent_address': sis.student.permanent_address,
                'student_info': sis.student,
            }

    context = {
        "school": school, 
        "students": students, 
        'this_grade': this_grade, 
        'this_section': this_section,
        'grade_print': grade_print, 
        'section_print': section_print,
        'info_type': info_type
    }
    # Export to Excel (CSV) if requested
    if request.GET.get('export') == 'excel':
        import csv
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="student_detail.csv"'
        writer = csv.writer(response)
        # Header row
        writer.writerow([
            'Reg No', 'Name', 'Grade', 'Section', 'House', 'Roll No',
            'DOB', 'Gender', 'Temp Address', 'Perm Address',
            "Father's Name", "Father's Phone", "Father's Email",
            "Mother's Name", "Mother's Phone", "Mother's Email",
            "Guardian's Name", "Guardian's Phone", "Guardian's Email"
        ])
        for s in students.values():
            writer.writerow([
                s.get('reg_no'),
                s.get('name'),
                s.get('grade'),
                s.get('section'),
                s.get('house'),
                s.get('roll_no'),
                getattr(s.get('student_info'), 'dob', ''),
                'M' if s.get('gender') else 'F',
                s.get('temporary_address'),
                s.get('permanent_address'),
                s.get('fathers_name'), s.get('fathers_phone'), s.get('fathers_email'),
                s.get('mothers_name'), s.get('mothers_phone'), s.get('mothers_email'),
                s.get('guardian_name'), s.get('guardian_phone'), s.get('guardian_email')
            ])
        return response
    return render(request, "panel/student_detail_print.html", context)

@login_required
def printmarksform(request):
    user = request.user
    branchuser, error = get_branch_info(user)
    if error:
        return HttpResponse(f'{error} Click <a href="/panel/">Here</a> to go the panel.')
        
    school = branchuser.school
    current_session = get_current_session()

    if request.method == "POST":
        term = request.POST.get("term")
        grade_id = request.POST.get("grade")
        section_id = request.POST.get("section")
        
        term_exam = SchoolTerm.objects.get(id=term)
        grade = SchoolGrade.objects.get(id=grade_id)
        section = Section.objects.get(id=section_id, session=current_session)

        # Optimize: select_related to avoid N+1 queries in template
        students = StudentSession.objects.filter(
            grade=grade, session=current_session, section=section, status=True
        ).select_related('student').order_by('roll_no')
        
        context = {
            "school": school,
            "students": students,
            "count": students.count(),
            "term_exam": term_exam,
            "grade": grade,
            "section": section,
            "this_year": current_session.year,
        }
        return render(request, "panel/printmarksform.html", context)

    exam_types = SchoolTerm.objects.filter(school=school, year=current_session)
    grades = SchoolGrade.objects.filter(school=school).order_by("grade_weight")
    
    section_list = {}
    # Optimize: prefetch sections or use a more efficient way to build the list
    all_sections = Section.objects.filter(grade__school=school, session=current_session).select_related('grade')
    for sec in all_sections:
        grade_key = str(sec.grade_id)
        if grade_key not in section_list:
            section_list[grade_key] = {}
        section_list[grade_key][str(sec.id)] = sec.section

    context = {
        "grades": grades,
        "school": school,
        "exam_types": exam_types,
        "section_list": json.dumps(section_list),
        "this_year": current_session.year
    }
    return render(request, "panel/printmarksformbase.html", context)


@login_required
def school_settings(request):
    """
    Allow admin users to view and update their school's basic information.
    """
    user = request.user
    branchuser, error = get_branch_info(user)
    if error:
        return HttpResponse(f'{error} Click <a href="/panel/">Here</a> to go the panel.')

    # Only admins may edit
    if not getattr(branchuser, "admin_status", False):
        return HttpResponse("Permission denied: admin access required.", status=403)

    school = branchuser.school
    if request.method == "POST":
        form = SchoolForm(request.POST, request.FILES, instance=school)
        if form.is_valid():
            form.save()
            messages.success(request, "School information updated successfully.")
            return redirect("panel:school_settings")
    else:
        form = SchoolForm(instance=school)

    return render(request, "panel/school_settings.html", {"form": form, "school": school})
def letterpincode(request):
    user = request.user
    branchuser, error = get_branch_info(user)
    if error:
        return HttpResponse(f'{error} Click <a href="/">Here</a> to go the homepage.')
    
    school = branchuser.school
    current_session = get_current_session()
    students = OrderedDict()
    
    school_grade = SchoolGrade.objects.filter(school=school, active=True).order_by('grade_weight')
    
    # Optimize: Use select_related and better query structure
    for sg in school_grade:
        student_in_session = StudentSession.objects.filter(
            session=current_session, grade=sg, status=True
        ).select_related('student', 'grade').order_by('section', 'roll_no', 'student')
        
        for sis in student_in_session:
            students[sis.student.reg_no] = {
                'reg_no': sis.student.reg_no,
                'name': sis.student.name,
                'grade': sis.grade.grade_name,
                'section': sis.section,
                'pin_code': sis.student.pin_code,
                'info': sis.student
            }

    context = {"school": school, "students": students}
    return render(request, "panel/letter_pincode_2080.html", context)


@login_required
def fullmarks(request):
    user = request.user
    branchuser, error = get_branch_info(user)
    if error:
        return HttpResponse(f'{error} Click <a href="/">Here</a> to go the homepage.')

    school = branchuser.school
    current_session = get_current_session()
    
    exam_types = SchoolTerm.objects.filter(school=school, year=current_session)
    grades = SchoolGrade.objects.filter(school=school).order_by("grade_weight")

    context = {
        "grades": grades,
        "school": school,
        "exam_types": exam_types,
        "edusession": current_session,
    }

    return render(request, "panel/marks.html", context)


@login_required
def inputfullmarksredirector(request):
    if request.method == "POST":
        user = request.user
        branchuser, error = get_branch_info(user)
        if error:
            return HttpResponse('Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.')
            return HttpResponse(
                'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
            )

        term = request.POST.get("term")
        grade = request.POST.get("grade")

        url = "/panel/addfullmarks/" + grade + "/" + term + "/"

        return HttpResponseRedirect(url)

    else:
        return HttpResponseRedirect("/")


@login_required
def addfullmarks(request, grade, term):
    user = request.user
    branchuser, error = get_branch_info(user)
    if error:
        return HttpResponse(f'{error} Click <a href="/">Here</a> to go the homepage.')

    school = branchuser.school
    exam_term = SchoolTerm.objects.get(id=term)
    grade = SchoolGrade.objects.get(id=grade)
    current_session = get_current_session()

    subjects = Subject.objects.filter(branch=school, grade=grade, status=True).order_by("id")

    if request.method == "POST":
        for subject in subjects:
            this_subject = str(subject.id)
            th_full = request.POST.get(this_subject + "_th_full")
            pr_full = request.POST.get(this_subject + "_pr_full")
            th_pass = request.POST.get(this_subject + "_th_pass")
            pr_pass = request.POST.get(this_subject + "_pr_pass")

            GradeFullMarks.objects.update_or_create(
                session=current_session,
                school=school,
                grade=grade,
                term=exam_term,
                subject=subject,
                defaults={
                    'th_fm': th_full,
                    'pr_fm': pr_full,
                    'th_pm': th_pass,
                    'pr_pm': pr_pass
                }
            )

    subjects_with_marks = GradeFullMarks.objects.filter(
        session=current_session, school=school, grade=grade, term=exam_term
    )
    gs = subjects_with_marks.exists()

    context = {
        "grade": grade,
        "school": school,
        "exam_term": exam_term,
        "edusession": current_session,
        "subjects": subjects_with_marks if gs else subjects,
        "gs": gs,
    }

    return render(request, "panel/addfullmarks.html", context)


def addfullmarksedit(request, grade, term):
    the_grade = grade
    the_term = term
    user = request.user
    branchuser, error = get_branch_info(user)
    if error:
        return HttpResponse(f'{error} Click <a href="/">Here</a> to go the homepage.')

    school = branchuser.school
    exam_term = SchoolTerm.objects.get(id=term)
    grade = SchoolGrade.objects.get(id=grade)
    current_session = get_current_session()

    subjects = Subject.objects.filter(session=current_session, branch=school, grade=grade, status=True).order_by("id")

    if (
            GradeFullMarks.objects.filter(
                session=edusession, school=school, grade=grade, term=exam_term
            ).count()
            == 0
    ):
        gs = False
    else:
        gs = True

    if request.method == "POST":
        for subject in subjects:
            print(subject.id, subject.subject)
            this_subject = str(subject.id)
            th_full = request.POST.get(this_subject + "_th_full", 0)
            pr_full = request.POST.get(this_subject + "_pr_full", 0)
            th_pass = request.POST.get(this_subject + "_th_pass", 0)
            pr_pass = request.POST.get(this_subject + "_pr_pass", 0)

            if (
                    GradeFullMarks.objects.filter(
                        session=edusession,
                        school=school,
                        grade=grade,
                        term=exam_term,
                        subject=subject,
                    ).count()
                    == 1
            ):
                gfm = GradeFullMarks.objects.get(
                    session=edusession,
                    school=school,
                    grade=grade,
                    term=exam_term,
                    subject=subject,
                )

                gfm.session = edusession
                gfm.school = school
                gfm.grade = grade
                gfm.term = exam_term
                gfm.subject = subject
                gfm.th_fm = th_full
                gfm.pr_fm = pr_full
                gfm.th_pm = th_pass
                gfm.pr_pm = pr_pass

                gfm.save()
            else:
                gfm = GradeFullMarks()

                gfm.session = edusession
                gfm.school = school
                gfm.grade = grade
                gfm.term = exam_term
                gfm.subject = subject
                gfm.th_fm = th_full
                gfm.pr_fm = pr_full
                gfm.th_pm = th_pass
                gfm.pr_pm = pr_pass

                gfm.save()

        url = "/panel/addfullmarks/" + the_grade + "/" + the_term + "/"

        return HttpResponseRedirect(url)

    subjects = GradeFullMarks.objects.filter(
        session=edusession, school=school, grade=grade, term=exam_term
    )

    context = {
        "grade": grade,
        "school": school,
        "exam_term": exam_term,
        "edusession": edusession,
        "subjects": subjects,
        "gs": gs,
    }

    return render(request, "panel/addfullmarksedit.html", context)


@login_required
def subjectwisemarksformbase(request):
    user = request.user
    branchuser, error = get_branch_info(user)
    if error:
        return HttpResponse(f'{error} Click <a href="/">Here</a> to go the homepage.')

    school = branchuser.school
    current_session = get_current_session()
    grade_level = GradeLevel.objects.all()
    grades = SchoolGrade.objects.filter(school=school).order_by("grade_weight")

    if request.method == "POST":
        term_id = request.POST.get("term")
        grade_id = request.POST.get("grade")
        section_id = request.POST.get("section")
        pra_marks_input = request.POST.get("praMarks")
        order = request.POST.get("order")
        
        this_grade = SchoolGrade.objects.get(id=grade_id)
        # Optimize: select_related/prefetch_related if needed, but here simple filter is fine
        subjects = Subject.objects.filter(
            branch=school, grade=this_grade, status=True, session=current_session
        ).order_by("id")
        
        term_exam = SchoolTerm.objects.get(id=term_id)
        section = Section.objects.get(id=section_id)

        context = {
            "school": school,
            "term_exam": term_exam,
            "grade": this_grade,
            "section": section,
            "subjects": subjects,
            "praMarks": pra_marks_input,
            "grade_level": grade_level,
            "grades": grades,
            "branchuser": branchuser,
            "order": order,
        }
        return render(request, "panel/subjectwiseselectsubject.html", context)

    exam_types = SchoolTerm.objects.filter(school=school, year=current_session)
    
    section_list = {}
    all_sections = Section.objects.filter(grade__school=school, session=current_session).select_related('grade')
    for sec in all_sections:
        grade_key = str(sec.grade_id)
        if grade_key not in section_list:
            section_list[grade_key] = {}
        section_list[grade_key][str(sec.id)] = sec.section

    context = {
        "grades": grades,
        "school": school,
        "exam_types": exam_types,
        "section_list": json.dumps(section_list),
        "grade_level": grade_level,
        "branchuser": branchuser,
        "this_year": current_session.year,
    }
    return render(request, "panel/subjectwisemarksformbase.html", context)


@login_required
def subject_wise_marks_entry(request):
    user = request.user
    branchuser, error = get_branch_info(user)
    if error:
        return HttpResponse(f'{error} Click <a href="/">Here</a> to go the homepage.')
    
    school = branchuser.school
    current_session = get_current_session()

    term_id = request.POST.get("term") or request.GET.get("term")
    grade_id = request.POST.get("grade") or request.GET.get("grade")
    section_id = request.POST.get("section") or request.GET.get("section")
    subject_id = request.POST.get("subject") or request.GET.get("subject")

    if term_id and grade_id and section_id and subject_id:
        order = int(request.POST.get("order") or request.GET.get("order") or 1)

        grade = SchoolGrade.objects.get(id=grade_id)
        section = Section.objects.get(id=section_id)
        subject = Subject.objects.get(id=subject_id)
        term_exam = SchoolTerm.objects.get(id=term_id)
        
        # Optimize queries for students
        student_query = StudentSession.objects.filter(
            session=current_session, grade=grade, section=section, status=True
        ).select_related('student')
        
        if order == 2:    # roll_no
            students = student_query.order_by('roll_no')
        elif order == 3:    # name
            students = student_query.order_by('student__name')
        else:               # reg_no
            students = student_query.order_by('student__reg_no')

        try:
            fullmark = GradeFullMarks.objects.get(
                school=school, grade=grade, session=current_session,
                term=term_exam, subject=subject,
            )
        except GradeFullMarks.DoesNotExist:
            return HttpResponse("Full marks configuration missing for this subject.")

        new_desc = {}
        # Prefetch MarksObtained to avoid N+1 in the loop
        marks_dict = {
            m.student_id: m for m in MarkObtained.objects.filter(
                school=school, grade=grade, term=term_exam,
                subject=subject, session=current_session
            )
        }

        for student_session in students:
            student = student_session.student
            reg_no = student.reg_no
            new_desc[reg_no] = {
                "name": student.name,
                "roll_no": student_session.roll_no
            }
            
            if request.POST.get("submittedhere") == "1":
                is_absent = request.POST.get(f"{reg_no}_absent") == "1"
                th_mo = int(request.POST.get(f"{reg_no}_th") or 0)
                pr_mo = int(request.POST.get(f"{reg_no}_pr") or 0)
                if is_absent:
                    th_mo = 0
                    pr_mo = 0

                the_mo, created = MarkObtained.objects.update_or_create(
                    student=student,
                    school=school,
                    grade=grade,
                    term=term_exam,
                    subject=subject,
                    session=current_session,
                    defaults={'th_mo': th_mo, 'pr_mo': pr_mo, 'is_absent': is_absent}
                )
                new_desc[reg_no]["th_mo"] = th_mo
                new_desc[reg_no]["pr_mo"] = pr_mo
                new_desc[reg_no]["is_absent"] = is_absent
            else:
                mo = marks_dict.get(reg_no)
                if not mo:
                    mo = MarkObtained.objects.create(
                        student=student, session=current_session, school=school,
                        grade=grade, term=term_exam, subject=subject,
                        th_mo=0, pr_mo=0, is_absent=False
                    )
                new_desc[reg_no]["th_mo"] = mo.th_mo
                new_desc[reg_no]["pr_mo"] = mo.pr_mo
                new_desc[reg_no]["is_absent"] = mo.is_absent
        
        praMarks = fullmark.pr_fm > 0
        
        context = {
            "school": school,
            "students": students,
            "term_exam": term_exam,
            "grade": grade,
            "section": section,
            "subject": subject,
            "praMarks": praMarks,
            "fullmark": fullmark,
            "new_desc": new_desc,
            "order": order,
        }
        return render(request, "panel/subjectwisemarksform.html", context)
    
    return redirect('index')

@login_required
def submitsubjectwise(request):
    user = request.user
    branchuser, error = get_branch_info(user)
    if error:
        return HttpResponse(f'{error} Click <a href="/">Here</a> to go the homepage.')

    school = branchuser.school
    current_session = get_current_session()

    if request.method == "POST":
        term_id = request.POST.get("term")
        grade_id = request.POST.get("grade")
        section_id = request.POST.get("section")
        praMarks_input = request.POST.get("praMarks")
        subject_id = request.POST.get("subject")

        this_grade = SchoolGrade.objects.get(id=grade_id)
        section = Section.objects.get(id=section_id)
        subject = Subject.objects.get(id=subject_id)
        term_exam = SchoolTerm.objects.get(id=term_id)
        
        # Optimize: select_related student
        student_sessions = StudentSession.objects.filter(
            grade=this_grade, session=current_session, section=section, status=True
        ).select_related('student')
        
        try:
            fullmark = GradeFullMarks.objects.get(
                school=school, grade=this_grade, session=current_session,
                term=term_exam, subject=subject,
            )
        except GradeFullMarks.DoesNotExist:
            return HttpResponse("Full marks configuration missing.")

        praMarks = praMarks_input == "1"

        for ss in student_sessions:
            student = ss.student
            th_mo = int(request.POST.get(f"{student.reg_no}_th") or 0)
            pr_mo = int(request.POST.get(f"{student.reg_no}_pr") or 0) if praMarks else 0

            MarkObtained.objects.update_or_create(
                student=student,
                session=current_session,
                school=school,
                grade=this_grade,
                term=term_exam,
                subject=subject,
                defaults={'th_mo': th_mo, 'pr_mo': pr_mo}
            )

        context = {
            "school": school,
            "students": student_sessions,
            "term_exam": term_exam,
            "grade": this_grade,
            "section": section,
            "subject": subject,
            "praMarks": praMarks,
            "fullmark": fullmark,
        }
        return render(request, "panel/subjectwisemarksform.html", context)
    
    return HttpResponseRedirect("/")


@login_required
def edgradeitems(request, gradelevel):
    user = request.user
    branchuser, error = get_branch_info(user)
    if error:
        return HttpResponse(f'{error} Click <a href="/">Here</a> to go the homepage.')

    schoolbranch = branchuser.school
    current_session = get_current_session()
    
    grade_level_all = GradeLevel.objects.all()
    grades = SchoolGrade.objects.filter(school=schoolbranch).order_by("grade_weight")
    standard_subjects = SubjectMaster.objects.filter(school=schoolbranch).order_by('canonical_name')
    
    try:
        this_grade = SchoolGrade.objects.get(id=int(gradelevel))
    except (ValueError, SchoolGrade.DoesNotExist):
        return HttpResponse("Grade not found.")

    avaiablesections = Section.objects.filter(grade=this_grade, session=current_session)
    exam_types = SchoolTerm.objects.filter(school=schoolbranch, year=current_session, active=True)
    subjects = Subject.objects.filter(branch=schoolbranch, grade=this_grade, session=current_session).order_by('id')
    students = StudentSession.objects.filter(grade=this_grade, session=current_session).select_related('student', 'section').order_by("section", "roll_no")

    # Add male/female counts for the dashboard
    male_count = students.filter(student__gender=True, status=True).count()
    female_count = students.filter(student__gender=False, status=True).count()

    # Optimize teacher access lookup
    teacher_subject_access = TeacherSubjectAccess.objects.filter(
        session=current_session, grade=this_grade
    ).select_related('teacher', 'teacher__hamro_profile', 'subject', 'section')
    
    teacher_access = {}
    for tsa in teacher_subject_access:
        sub_id = tsa.subject_id
        t_id = tsa.teacher_id
        sec_id = tsa.section_id
        
        if sub_id not in teacher_access:
            teacher_access[sub_id] = {}
        if t_id not in teacher_access[sub_id]:
            teacher_access[sub_id][t_id] = {}
            
        try:
            photo_url = tsa.teacher.hamro_profile.avatar_url
            if not photo_url:
                photo_url = None
        except Exception:
            photo_url = None

        teacher_access[sub_id][t_id][sec_id] = {
            'name': f"{tsa.teacher.first_name} {tsa.teacher.last_name}",
            'section': tsa.section.section,
            'status': tsa.status,
            'photo': photo_url
        }

    # Rest of the logic simplified
    section = list_attendance = list_subject = this_term = teacher = teachers = subject = student = None
    list_student = ed_subject = hw_subject = attendance = student_by_reg = change_name = assign_section = assign_house = None
    edsubject = hwsubject = cn_subject = houses = sections = ""
    this_section = None

    if request.method == "GET":
        list_item = request.GET.get("list")
        if list_item == "student":
            list_student = True
        elif list_item == "subject":
            list_subject = True
        elif list_item == "attendance":
            list_attendance = True
            term_id = request.GET.get("term")
            if term_id:
                try:
                    this_term = SchoolTerm.objects.get(id=int(term_id))
                except (ValueError, SchoolTerm.DoesNotExist):
                    this_term = None
            section_id = request.GET.get("section")
            if section_id:
                try:
                    this_section = avaiablesections.filter(id=int(section_id)).first()
                    if this_section:
                        students = students.filter(section=this_section)
                except ValueError:
                    pass

        assign_item = request.GET.get("assign")
        if assign_item == "house":
            assign_house = True
            students = students.filter(status=True)
            houses = House.objects.filter(school=schoolbranch)
        elif assign_item == "section":
            students = students.filter(status=True)
            assign_section = True
        elif assign_item == "teacher":
            teacher = True
            teachers = Teacher.objects.filter(added_by=user)

        add = request.GET.get("add")
        if add == "section":
            students = students.filter(status=True)
            section = True
        elif add == "subject":
            subject = True
        elif add == "student":
            student = True
        elif add == "teacher":
            teacher = True
            teachers = Teacher.objects.filter(added_by=user)
        elif add == "attendance":
            students = students.filter(status=True)
            attendance = True
            term_id = request.GET.get("term")
            if term_id:
                try:
                    this_term = SchoolTerm.objects.get(id=int(term_id))
                except (ValueError, SchoolTerm.DoesNotExist):
                    this_term = None
            section_id = request.GET.get("section")
            if section_id:
                try:
                    this_section = avaiablesections.filter(id=int(section_id)).first()
                    if this_section:
                        students = students.filter(section=this_section)
                except ValueError:
                    pass
        elif add == "student_by_reg":
            student_by_reg = True

        ed = request.GET.get("ed")
        if ed:
            edsubject = subjects.filter(id=ed).first()
            if edsubject:
                ed_subject = True

        hw = request.GET.get("hw")
        if hw:
            hwsubject = subjects.filter(id=hw).first()
            if hwsubject:
                hw_subject = True

        cn = request.GET.get("cn")
        if cn:
            cn_subject = subjects.filter(id=cn).first()
            if cn_subject:
                change_name = True

        uta = request.GET.get("uta")
        if uta:
            # Handle teacher access toggle
            tsa_toggle = TeacherSubjectAccess.objects.filter(
                session=current_session, teacher_id=uta, 
                subject_id=request.GET.get("sub"), 
                section_id=request.GET.get("sec")
            ).first()
            if tsa_toggle:
                tsa_toggle.status = not tsa_toggle.status
                tsa_toggle.save()
                return redirect(request.path)

    if list_attendance and this_term:
        students = Attendance.objects.filter(grade=this_grade, session=current_session, term=this_term)
        if this_section:
            # Filter attendance by students in this section
            section_students = StudentSession.objects.filter(grade=this_grade, session=current_session, section=this_section).values_list('student__reg_no', flat=True)
            students = students.filter(reg_no__in=section_students)

    context = {
        "grade_level": grade_level_all,
        "g_level": this_grade,
        "gradelevel": this_grade.id,
        "grades": grades,
        "branchuser": branchuser,
        "school": schoolbranch,
        "standard_subjects": standard_subjects,
        "section": section,
        "subject": subject,
        "teacher": teacher,
        "teachers": teachers,
        'teacher_access': teacher_access,
        "student": student,
        "students": students,
        "male_count": male_count,
        "female_count": female_count,
        "avaiablesections": avaiablesections,
        "subjects": subjects,
        "list_student": list_student,
        "list_subject": list_subject,
        "list_attendance": list_attendance,
        "ed_subject": ed_subject,
        "hw_subject": hw_subject,
        "hwsubject": hwsubject,
        "edsubject": edsubject,
        "attendance": attendance,
        "student_by_reg": student_by_reg,
        "change_name": change_name,
        "cn_subject": cn_subject,
        "exam_types": exam_types,
        "this_term": this_term,
        "assign_house": assign_house,
        "houses": houses,
        "assign_section": assign_section,
        "this_section": this_section
    }
    return render(request, "panel/listgradeitems.html", context)


@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('profile')
        else:
            # Handle invalid form by showing the profile page with errors
            branchuser = BranchUser.objects.get(user=request.user)
            school = branchuser.school
            grade_level = GradeLevel.objects.all()
            context = {
                "grade_level": grade_level,
                "branchuser": branchuser,
                "school": school,
                "user": request.user,
                "password_form": form,
                "show_password_modal": True,  # Flag to trigger the modal on reload
            }
            messages.error(request, 'Please correct the error below.')
            return render(request, "panel/profile.html", context)
    return redirect('profile')


def addAttendance(request, grade=None):
    # print(request.POST)
    if request.method == "POST":
        grade_id = request.POST.get("grade")
        term_id = request.POST.get("term")
        grade = SchoolGrade.objects.get(id=grade_id)
        term = SchoolTerm.objects.get(id=term_id)
        session = get_current_session()
        no_of_school_days = int(request.POST.get("no_of_school_days"))
        data_type = request.POST.get("data_type")
        students = StudentSession.objects.filter(grade=grade, session=session, status=True)
        for std_sess in students:
            student = std_sess.student
            std_att = request.POST.get(str(student.reg_no), "0").strip()
            if std_att == "":
                std_att = 0
            else:
                std_att = int(std_att)
            
            if data_type == "present":
                school_days = no_of_school_days
                present_days = std_att
                absent_days = no_of_school_days - std_att
            else:
                school_days = no_of_school_days
                present_days = no_of_school_days - std_att
                absent_days = std_att

            try:
                created = Attendance.objects.get(
                    reg_no=student, grade=grade, session=session, term=term
                )
                if std_att != 0:
                    created.no_of_school_days = no_of_school_days
                    created.no_of_present_days = present_days
                    created.no_of_absent_days = absent_days
                    created.save()

            except Attendance.DoesNotExist:
                attend = Attendance()
                attend.reg_no = student
                attend.grade = grade
                attend.session = session
                attend.term = term
                attend.no_of_school_days = no_of_school_days
                attend.no_of_present_days = present_days
                attend.no_of_absent_days = absent_days
                attend.save()

            # print(created)
        # print(type(grade))
        return HttpResponseRedirect("/panel/grades/" + str(grade.id) + "/")
    else:
        return HttpResponseRedirect("/panel/")


@login_required
def edsubject(request):
    user = request.user
    if request.method == "POST":
        redurl = request.POST.get("redurl")
        gradelevel = request.POST.get("gradelevel")
        edsubjectid = request.POST.get("edsubjectid")

        schoolgrade = SchoolGrade.objects.get(id=gradelevel)
        try:
            branchuser = BranchUser.objects.get(user=user)
        except BranchUser.DoesNotExist:
            return HttpResponse(
                'Sorry! You are not allowed to access this page. Click <a href="/panel/">Here</a> to go the Panel.'
            )

        if schoolgrade.school == branchuser.school:
            subject = Subject.objects.get(id=edsubjectid)
            if subject.status == 1:
                subject.status = 0
            else:
                subject.status = 1
            subject.save()
            return redirect(redurl)
        else:
            return HttpResponse(
                'Sorry! You are not allowed to access this page. Click <a href="/panel/">Here</a> to go the Panel.'
            )

        print(gradelevel, gradelevel, edsubjectid)
        return HttpResponse("Hi")
    else:
        return HttpResponse(
            'Sorry! Something went wrong. Click <a href="/panel/">Here</a> to go the homepage.'
        )


@login_required
def hwsubject(request):
    user = request.user
    if request.method == "POST":
        redurl = request.POST.get("redurl")
        gradelevel = request.POST.get("gradelevel")
        hwsubjectid = request.POST.get("hwsubjectid")

        schoolgrade = SchoolGrade.objects.get(id=gradelevel)
        try:
            branchuser = BranchUser.objects.get(user=user)
        except BranchUser.DoesNotExist:
            return HttpResponse(
                'Sorry! You are not allowed to access this page. Click <a href="/panel/">Here</a> to go the Panel.'
            )

        if schoolgrade.school == branchuser.school:
            subject = Subject.objects.get(id=hwsubjectid)
            if subject.heavy_weight == 1:
                subject.heavy_weight = 0
            else:
                subject.heavy_weight = 1
            subject.save()
            return redirect(redurl)
        else:
            return HttpResponse(
                'Sorry! You are not allowed to access this page. Click <a href="/panel/">Here</a> to go the Panel.'
            )

        print(gradelevel, gradelevel, edsubjectid)
        return HttpResponse("Hi")
    else:
        return HttpResponse(
            'Sorry! Something went wrong. Click <a href="/panel/">Here</a> to go the homepage.'
        )


@login_required
def printledger(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    edusession = EduSession.objects.all().order_by("-year")
    current_session = get_current_session()
    exam_types = SchoolTerm.objects.filter(school=school, active=True)
    grades = SchoolGrade.objects.filter(school=school, active=True).order_by("id")

    section_list = {}
    for session in edusession:
        s_id = str(session.id)
        section_list[s_id] = {}
        for grade in grades:
            sections = Section.objects.filter(grade=grade, session=session)
            grade_dict = {str(s.id): s.section for s in sections}
            section_list[s_id][str(grade.id)] = grade_dict

    section_list = json.dumps(section_list)

    # term_list mapping for year-wise filtering
    term_dict = {}
    for term in exam_types:
        year_id = str(term.year.id)
        if year_id not in term_dict:
            term_dict[year_id] = []
        term_dict[year_id].append({
            'id': term.id,
            'name': f"{term.term_name.upper()} {term.year.year}"
        })
    term_list = json.dumps(term_dict)

    context = {
        "edusession": edusession,
        "current_session": current_session,
        "school": school,
        "exam_types": exam_types,
        "grades": grades,
        "section_list": section_list,
        "term_list": term_list,
    }
    return render(request, "panel/printledger.html", context)


@login_required
def print_ledger_preview(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    if request.method == "POST":
        edusession = request.POST.get("edusession")
        term = request.POST.get("term")
        grade = request.POST.get("grade")
        section = request.POST.get("section")
        order = request.POST.get("order")
        ledgermode = request.POST.get("ledgermode", "1")

        this_grade = SchoolGrade.objects.get(id=grade)
        this_session = EduSession.objects.get(id=edusession)
        this_term = SchoolTerm.objects.get(id=term)

        if section and str(section).strip() not in ("", "0"):
            this_section = Section.objects.get(id=section)
        else:
            this_section = None
        
        subjects = Subject.objects.filter(session=this_session, branch=school, grade=this_grade, status=True).order_by("id")

        from panel.func import _parse_weighted_term_config
        normalized_wconfig = {}
        source_terms = []
        if ledgermode in ["2", "3"]:
            weighted_config_obj = WeightedResultManagement.objects.filter(school=school, year=this_session, school_term=this_term).first()
            if weighted_config_obj:
                normalized_wconfig = _parse_weighted_term_config(weighted_config_obj.weight_config, this_term.id, include_current=True)
                source_term_ids = list(normalized_wconfig.keys())
                # Fetch terms and preserve order from config
                term_objects = {str(t.id): t for t in SchoolTerm.objects.filter(id__in=source_term_ids)}
                source_terms = [term_objects[tid] for tid in source_term_ids if tid in term_objects]
                
                if not source_terms:
                    ledgermode = "1"
            else:
                ledgermode = "1"

        base_qs_kwargs = {"grade": this_grade, "session": this_session, "status": True}
        if this_section:
            base_qs_kwargs["section"] = this_section

        try: order = int(order or "1")
        except: order = 1

        if order == 1:
            students = StudentSession.objects.filter(**base_qs_kwargs).order_by('student__reg_no')
        else:
            students = StudentSession.objects.filter(**base_qs_kwargs).order_by('roll_no')
        
        # Build FM cache for reference table (only for this term)
        this_term_fm_cache = {fm.subject_id: fm for fm in GradeFullMarks.objects.filter(school=school, session=this_session, grade=this_grade, term=this_term)}

        # Pre-fetch marks for all source terms
        all_marks_map = {}
        source_fm_map = {}
        if ledgermode in ["2", "3"]:
            source_term_ids = [t.id for t in source_terms]
            marks_qs = MarkObtained.objects.filter(school=school, session=this_session, grade=this_grade, term_id__in=source_term_ids)
            for m in marks_qs:
                all_marks_map[(m.student_id, m.term_id, m.subject_id)] = (m.th_mo or 0, m.pr_mo or 0)
            
            source_fm_qs = GradeFullMarks.objects.filter(school=school, session=this_session, grade=this_grade, term_id__in=source_term_ids)
            source_fm_map = {(fm.term_id, fm.subject_id): (fm.th_fm or 0, fm.pr_fm or 0) for fm in source_fm_qs}
        else:
            # Standard mode: only this term
            marks_qs = MarkObtained.objects.filter(school=school, session=this_session, grade=this_grade, term=this_term)
            for m in marks_qs:
                all_marks_map[(m.student_id, this_term.id, m.subject_id)] = (m.th_mo or 0, m.pr_mo or 0)

        student_data_list = []
        for student in students:
            std_entry = {
                "reg_no": student.student.reg_no,
                "name": student.student.name,
                "roll_no": student.roll_no,
                "breakdown_terms": [],
            }

            if ledgermode == "1":
                # Standard: Just show marks for this term
                term_entry = {"term_label": this_term.term_name, "subjects": []}
                for sub in subjects:
                    th_obt, pr_obt = all_marks_map.get((student.student_id, this_term.id, sub.id), (0, 0))
                    fm = this_term_fm_cache.get(sub.id)
                    term_entry["subjects"].append({
                        "th_val": int(th_obt) if th_obt == int(th_obt) else round(th_obt, 2),
                        "pr_val": int(pr_obt) if pr_obt == int(pr_obt) else round(pr_obt, 2),
                        "th_max": fm.th_fm if fm else 0,
                        "pr_max": fm.pr_fm if fm else 0
                    })
                std_entry["breakdown_terms"].append(term_entry)
            else:
                # Consolidated Raw or Weighted Breakdown
                student_subject_totals = {sub.id: {"th": 0, "pr": 0} for sub in subjects}
                
                for src_term in source_terms:
                    term_label = getattr(src_term, 'name_in_short', None) or src_term.term_name
                    if ledgermode == "2":
                        term_label += " (WGT)"
                    
                    term_entry = {"term_label": term_label, "subjects": []}
                    w_info = normalized_wconfig.get(str(src_term.id))
                    
                    for sub in subjects:
                        s_th, s_pr = all_marks_map.get((student.student_id, src_term.id, sub.id), (0, 0))
                        s_th_fm, s_pr_fm = source_fm_map.get((src_term.id, sub.id), (100, 100))
                        
                        if ledgermode == "2" and w_info: # Weighted
                            if w_info.get("plan") == "scaling":
                                val_th = (s_th / s_th_fm * w_info["th_target_fm"] * w_info["th_from_th"]) if s_th_fm > 0 else 0
                                val_pr = (s_pr / s_pr_fm * w_info["pr_target_fm"] * w_info["pr_from_pr"]) if s_pr_fm > 0 else 0
                            else:
                                val_th = s_th * w_info["th_from_th"]
                                val_pr = s_pr * w_info["pr_from_pr"]
                        else: # Consolidated Raw
                            val_th = s_th
                            val_pr = s_pr
                        
                        # Add to totals
                        student_subject_totals[sub.id]["th"] += val_th
                        student_subject_totals[sub.id]["pr"] += val_pr
                        
                        term_entry["subjects"].append({
                            "th_val": int(val_th) if val_th == int(val_th) else round(val_th, 2),
                            "pr_val": int(val_pr) if val_pr == int(val_pr) else round(val_pr, 2),
                            "th_max": s_th_fm,
                            "pr_max": s_pr_fm
                        })
                    std_entry["breakdown_terms"].append(term_entry)
                
                # Add TOTAL row at the end of breakdown
                total_label = "TOTAL"
                if ledgermode == "2": total_label += " (WGT)"
                
                total_entry = {"term_label": total_label, "subjects": [], "is_total": True}
                for sub in subjects:
                    t_th = student_subject_totals[sub.id]["th"]
                    t_pr = student_subject_totals[sub.id]["pr"]
                    total_entry["subjects"].append({
                        "th_val": int(t_th) if t_th == int(t_th) else round(t_th, 2),
                        "pr_val": int(t_pr) if t_pr == int(t_pr) else round(t_pr, 2),
                        "th_max": 0, # Not used in total row display usually
                        "pr_max": 0
                    })
                std_entry["breakdown_terms"].append(total_entry)

            student_data_list.append(std_entry)

        # Subject FM list for header reference
        subject_fm_list = []
        for sub in subjects:
            if ledgermode in ["2", "3"]:
                # For weighted/consolidated, determine if PR exists by checking source terms
                th_max = 0
                pr_max = 0
                if ledgermode == "3": # Consolidated (Sum of all source FMs)
                    th_max = sum(source_fm_map.get((t.id, sub.id), (0, 0))[0] for t in source_terms)
                    pr_max = sum(source_fm_map.get((t.id, sub.id), (0, 0))[1] for t in source_terms)
                else: # Weighted (Mode 2)
                    first_w = next(iter(normalized_wconfig.values()), {})
                    if first_w.get("plan") == "scaling":
                        th_max = first_w.get("th_target_fm", 100)
                        pr_max = first_w.get("pr_target_fm", 100)
                    else:
                        for t in source_terms:
                            w_info = normalized_wconfig.get(str(t.id), {})
                            s_th_fm, s_pr_fm = source_fm_map.get((t.id, sub.id), (0, 0))
                            th_max += s_th_fm * w_info.get("th_from_th", 0)
                            pr_max += s_pr_fm * w_info.get("pr_from_pr", 0)
            else:
                fm = this_term_fm_cache.get(sub.id)
                th_max = fm.th_fm if fm else 0
                pr_max = fm.pr_fm if fm else 0

            subject_fm_list.append({
                "name": sub.subject,
                "th_fm": int(th_max),
                "pr_fm": int(pr_max),
            })

        context = {
            "school": school, "term": this_term, "year": this_term.year,
            "student_data": student_data_list, "grade": this_grade, "section": this_section,
            "subjects": subjects, "ledgermode": ledgermode, "ledgertype": "2", # Always marks for preview
            "subject_fm_list": subject_fm_list,
        }
        return render(request, "panel/printledgerpreview.html", context)
    else:
        return HttpResponseRedirect("/panel/")



@login_required
def print_ledger_now(request):
    print("ONE")
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    if request.method == "POST":
        edusession = request.POST.get("edusession")
        term = request.POST.get("term")
        printtype = int(request.POST.get("printtype"))
        grade = request.POST.get("grade2", 0)
        section = request.POST.get("section2", 0)
        # Ledger Mode (Standard vs Weighted Breakdown vs Consolidated Raw)
        ledgermode = request.POST.get("ledgermode", "1")
        # Ledger Type: 1=GRADE, 2=MARKS
        ledgertype = request.POST.get("ledgertype", "1")
        grading_type = int(request.POST.get("grading_type", "2"))
        data_filter = int(request.POST.get("filter", "0"))
        rank_by = request.POST.get("rank_by", "total")

        if grade == 0 or grade == None or grade == "":
            return HttpResponse(
                "Sorry! something went wrong. Please take care while submitting data."
            )
        else:
            this_grade = SchoolGrade.objects.get(id=grade)
        this_session = EduSession.objects.get(id=edusession)
        this_term = SchoolTerm.objects.get(id=term)

        weighted_config_obj = None
        if ledgermode in ["2", "3"]:
            weighted_config_obj = WeightedResultManagement.objects.filter(school=school, year=this_session, school_term=this_term).first()
            if not weighted_config_obj:
                ledgermode = "1"

        if int(section) > 0:
            this_section = Section.objects.get(id=section)
        else:
            this_section = False

        subjects = Subject.objects.filter(
            branch=school, grade=this_grade, session=this_session, status=True
        ).order_by("id")

        source_terms = []
        normalized_wconfig = {}
        from panel.func import _parse_weighted_term_config, _as_float, detailResult2078, grading, split_gpa_grade, GradeAndGpa, GradeAndGpaNew
        
        if ledgermode in ["2", "3"] and weighted_config_obj:
            # Use include_current=True because consolidated raw should show all terms with weights > 0
            normalized_wconfig = _parse_weighted_term_config(weighted_config_obj.weight_config, this_term.id, include_current=True)
            source_term_ids = list(normalized_wconfig.keys())
            
            # Fetch terms and preserve order from config
            term_objects = {str(t.id): t for t in SchoolTerm.objects.filter(id__in=source_term_ids)}
            source_terms = [term_objects[tid] for tid in source_term_ids if tid in term_objects]
        else:
            ledgermode = "1"
            source_terms = [this_term]
            
        for sub in subjects:
            sub.source_list = source_terms
            sub.source_count = len(source_terms)
            sub.source_count_x2 = len(source_terms) * 2


        subjectcount = ""
        for subject in subjects:
            subjectcount += "1"
        if this_section == False:
            students = StudentSession.objects.filter(grade=this_grade, session=this_session, status=True)
            calculated_rank = calculate_rank(school.id, this_session, grade, term, rank_by=rank_by)
        else:
            students = StudentSession.objects.filter(grade=this_grade, section=this_section, session=this_session, status=True)
            calculated_rank = calculate_rank(school.id, this_session, grade, term, this_section, rank_by=rank_by)

        # FM/PM cache for pass/fail detection and FM reference table
        gfm_qs = GradeFullMarks.objects.filter(school=school, session=this_session, grade=this_grade, term=this_term)
        gfm_cache = {g.subject_id: g for g in gfm_qs}

        # Pre-fetch source marks and FM for weighted/consolidated modes
        all_marks_map = {}
        source_fm_map = {}
        source_term_ids = [t.id for t in source_terms]
        marks_qs = MarkObtained.objects.filter(
            school=school, session=this_session, grade=this_grade, 
            term_id__in=source_term_ids, subject_id__in=[s.id for s in subjects]
        )
        for m in marks_qs:
            all_marks_map[(m.student_id, m.term_id, m.subject_id)] = (m.th_mo or 0, m.pr_mo or 0)

        source_fm_qs = GradeFullMarks.objects.filter(
            school=school, session=this_session, grade=this_grade, term_id__in=source_term_ids
        )
        for fm in source_fm_qs:
            source_fm_map[(fm.term_id, fm.subject_id)] = (fm.th_fm or 0, fm.pr_fm or 0)

        # Calculate Full Marks (FM) per subject based on mode
        subject_fm_data = {}
        
        for sub in subjects:
            if ledgermode == "1": # Standard
                gfm = gfm_cache.get(sub.id)
                th_max = gfm.th_fm if gfm else 0
                pr_max = gfm.pr_fm if gfm else 0
            elif ledgermode == "3": # Consolidated (Sum of all source FMs)
                th_max = sum(source_fm_map.get((t.id, sub.id), (0, 0))[0] for t in source_terms)
                pr_max = sum(source_fm_map.get((t.id, sub.id), (0, 0))[1] for t in source_terms)
            else: # Weighted (Mode 2)
                th_max = 0
                pr_max = 0
                first_w = next(iter(normalized_wconfig.values()), {})
                if first_w.get("plan") == "scaling":
                    th_max = first_w.get("th_target_fm", 100)
                    pr_max = first_w.get("pr_target_fm", 100)
                else:
                    for t in source_terms:
                        w_info = normalized_wconfig.get(str(t.id), {})
                        s_th_fm, s_pr_fm = source_fm_map.get((t.id, sub.id), (0, 0))
                        th_max += s_th_fm * w_info.get("th_from_th", 0)
                        pr_max += s_pr_fm * w_info.get("pr_from_pr", 0)
            
            subject_fm_data[sub.id] = {"th_max": th_max, "pr_max": pr_max}

        subject_fm_list = []
        for sub in subjects:
            fm_info = subject_fm_data.get(sub.id, {"th_max": 0, "pr_max": 0})
            subject_fm_list.append({
                "name": sub.subject,
                "th_fm": int(fm_info["th_max"]),
                "pr_fm": int(fm_info["pr_max"]),
                "th_pm": int(fm_info["th_max"] * 0.4) if (fm_info["th_max"] * 0.4) == int(fm_info["th_max"] * 0.4) else round(fm_info["th_max"] * 0.4, 2),
                "pr_pm": int(fm_info["pr_max"] * 0.4) if (fm_info["pr_max"] * 0.4) == int(fm_info["pr_max"] * 0.4) else round(fm_info["pr_max"] * 0.4, 2),
            })

        sn = 0
        data = {}
        from panel.func import get_grade_point_exam
        for student in students:
            sn += 1
            data[sn] = {}
            data[sn]["reg_no"] = student.student.reg_no
            data[sn]["name"] = student.student.name
            data[sn]["roll_no"] = student.roll_no
            data[sn]["section"] = student.section

            # Always fetch printtype=1 so we get both raw marks and grades in subjects dict
            sd = detailResult2078(school, term, grade, student.student.reg_no, 1, edusession=edusession, grading_type=grading_type)
            
            # Always compute weighted_subjects_data regardless of mode so template renders fully
            weighted_subjects_data = []
            for sub in subjects:
                m = sd["subjects"].get(sub.id, {})
                sub_total_th_mo = 0
                sub_total_pr_mo = 0
                sub_total_th_fm = 0
                sub_total_pr_fm = 0
                
                sub_sources = []

                for src_term in source_terms:
                    raw_th, raw_pr = all_marks_map.get((student.student_id, src_term.id, sub.id), (0, 0))

                    conv_th = conv_pr = 0
                    th_grade = pr_grade = "-"
                    th_grade_s = pr_grade_s = ""
                    w_info = normalized_wconfig.get(str(src_term.id))
                    
                    src_th_fm, src_pr_fm = source_fm_map.get((src_term.id, sub.id), (100, 100))

                    th_fail = pr_fail = False
                    th_gp = pr_gp = 0
                    if printtype != 2:
                        if src_th_fm > 0: 
                            res_th = grading(raw_th * 100 / src_th_fm)
                            th_grade, th_grade_s = res_th[0], res_th[1]
                            th_fail = res_th[2] < 1.6
                            th_gp = res_th[2]
                        if src_pr_fm > 0: 
                            res_pr = grading(raw_pr * 100 / src_pr_fm)
                            pr_grade, pr_grade_s = res_pr[0], res_pr[1]
                            pr_fail = res_pr[2] < 1.6
                            pr_gp = res_pr[2]

                    if w_info:
                        if w_info.get("plan") == "scaling":
                            conv_th = (raw_th / src_th_fm * w_info["th_target_fm"] * w_info["th_from_th"]) if src_th_fm > 0 else 0
                            conv_pr = (raw_pr / src_pr_fm * w_info["pr_target_fm"] * w_info["pr_from_pr"]) if src_pr_fm > 0 else 0
                            cal_th_fm = w_info.get("th_target_fm", 0) * w_info.get("th_from_th", 0)
                            cal_pr_fm = w_info.get("pr_target_fm", 0) * w_info.get("pr_from_pr", 0)
                        else:
                            conv_th = raw_th * w_info["th_from_th"]
                            conv_pr = raw_pr * w_info["pr_from_pr"]
                            cal_th_fm = src_th_fm * w_info["th_from_th"]
                            cal_pr_fm = src_pr_fm * w_info["pr_from_pr"]
                    else:
                        cal_th_fm = src_th_fm
                        cal_pr_fm = src_pr_fm
                        conv_th = raw_th
                        conv_pr = raw_pr

                    if ledgermode == "3": # Consolidated (Raw)
                        sub_total_th_mo += raw_th
                        sub_total_pr_mo += raw_pr
                        sub_total_th_fm += src_th_fm
                        sub_total_pr_fm += src_pr_fm
                    else: # Weighted Breakdown (Converted)
                        sub_total_th_mo += conv_th
                        sub_total_pr_mo += conv_pr
                        sub_total_th_fm += cal_th_fm
                        sub_total_pr_fm += cal_pr_fm

                    term_sub_gp = 0
                    if printtype != 2:
                        term_sub_obt = raw_th + raw_pr
                        term_sub_fm = src_th_fm + src_pr_fm
                        term_sub_percent = (term_sub_obt * 100 / term_sub_fm) if term_sub_fm > 0 else 0
                        term_sub_gp = get_grade_point_exam(term_sub_percent)[2]

                    sub_sources.append({
                        "name": src_term.term_name,
                        "name_short": getattr(src_term, 'name_in_short', None) or src_term.term_name,
                        "raw_th": int(raw_th) if raw_th == int(raw_th) else raw_th, 
                        "raw_pr": int(raw_pr) if raw_pr == int(raw_pr) else raw_pr,
                        "th_grade": th_grade, "th_grade_s": th_grade_s,
                        "pr_grade": pr_grade, "pr_grade_s": pr_grade_s,
                        "th_fail": th_fail,
                        "pr_fail": pr_fail,
                        "th_gp": th_gp,
                        "pr_gp": pr_gp,
                        "term_gp": term_sub_gp,
                        "conv_th": int(conv_th) if conv_th == int(conv_th) else round(conv_th, 2), 
                        "conv_pr": int(conv_pr) if conv_pr == int(conv_pr) else round(conv_pr, 2)
                    })

                heavy = sub.heavy_weight if getattr(sub, 'heavy_weight', None) is not None else 1
                if grading_type == 2:
                    g_gpa = GradeAndGpaNew(sub_total_th_fm, sub_total_pr_fm, sub_total_th_mo, sub_total_pr_mo, heavy, result_type=2)
                else:
                    g_gpa = GradeAndGpa(sub_total_th_fm, sub_total_pr_fm, sub_total_th_mo, sub_total_pr_mo, heavy)
                
                # Unified calculation logic for all modes including Standard (Mode 1):
                # We calculate g_gpa dynamically using the evaluated sub_total_th_fm + sub_total_pr_fm.
                # This guarantees that the GP relies strictly upon aggregated total Marks / total FM
                # instead of improperly averaging TH and PR grade points.
                m["theory_raw"] = int(sub_total_th_mo) if sub_total_th_mo == int(sub_total_th_mo) else round(sub_total_th_mo, 2)
                m["prac_raw"] = int(sub_total_pr_mo) if sub_total_pr_mo == int(sub_total_pr_mo) else round(sub_total_pr_mo, 2)
                m["theory_mo"] = g_gpa.th_grade
                m["theory_mo_s"] = g_gpa.th_symbol
                m["prac_mo"] = g_gpa.pr_grade
                m["prac_mo_s"] = g_gpa.pr_symbol
                m["th_fail"] = getattr(g_gpa, 'th_fail', False)
                m["pr_fail"] = getattr(g_gpa, 'pr_fail', False)
                m["gradepoint"] = g_gpa.total_point
                
                # Also provide keys for weighted breakdown template
                m["total_th"] = m["theory_raw"]
                m["total_pr"] = m["prac_raw"]
                m["total_th_grade"] = m["theory_mo"]
                m["total_th_grade_s"] = m["theory_mo_s"]
                m["total_pr_grade"] = m["prac_mo"]
                m["total_pr_grade_s"] = m["prac_mo_s"]
                m["total_gp"] = m["gradepoint"]
                
                weighted_subjects_data.append({
                    "subject_name": sub.subject,
                    "sources": sub_sources,
                    "total_th": m["theory_raw"],
                    "total_pr": m["prac_raw"],
                    "total_th_grade": m["theory_mo"],
                    "total_th_grade_s": m["theory_mo_s"],
                    "total_pr_grade": m["prac_mo"],
                    "total_pr_grade_s": m["prac_mo_s"],
                    "th_fail": m["th_fail"],
                    "pr_fail": m["pr_fail"],
                    "total_gp": m["gradepoint"]
                })
                
                data[sn]["weighted_subjects"] = weighted_subjects_data
                
                if source_terms:
                    consolidated_terms = []
                    for idx, src_term in enumerate(source_terms):
                        term_subjects = []
                        for sub_data in weighted_subjects_data:
                            if idx < len(sub_data["sources"]):
                                src = sub_data["sources"][idx]
                                term_subjects.append({
                                    "raw_th": src["raw_th"], "raw_pr": src["raw_pr"],
                                    "conv_th": src["conv_th"], "conv_pr": src["conv_pr"],
                                    "th_grade": src["th_grade"], "th_grade_s": src["th_grade_s"],
                                    "pr_grade": src["pr_grade"], "pr_grade_s": src["pr_grade_s"],
                                    "th_fail": src.get("th_fail", False), "pr_fail": src.get("pr_fail", False),
                                    "th_gp": src.get("th_gp", 0), "pr_gp": src.get("pr_gp", 0),
                                    "term_gp": src.get("term_gp", 0),
                                })
                            else:
                                term_subjects.append({"raw_th": "-", "raw_pr": "-", "conv_th": "-", "conv_pr": "-", "th_grade": "-", "th_grade_s": "", "pr_grade": "-", "pr_grade_s": ""})
                        
                        term_label = getattr(src_term, 'name_in_short', None) or src_term.term_name
                        if ledgermode == "2":
                            term_label += " (WGT)"
                        
                        consolidated_terms.append({
                            "term_name": src_term.term_name,
                            "term_short": term_label,
                            "subjects": term_subjects,
                        })
                    data[sn]["consolidated_terms"] = consolidated_terms

            data[sn].update({
                "mo_th": sd["mo_th"], "mo_pr": sd["mo_pr"],
                "total": sd["total"], "gp": sd["gp"],
                "subjects": sd["subjects"]
            })

            # Pass/Fail detection + per-subject fail flags (th_fail/pr_fail for gray cells)
            is_failed = False
            total_raw = 0
            total_fm_sum = 0
            combined_gp_sum = 0
            sub_count = 0
            fail_count = 0
            
            # Loop ONLY through the filtered active subjects to avoid unassigned subject junk dict pollution
            for sub in subjects:
                sub_id = sub.id
                marks = sd["subjects"].get(sub_id, {})
                th_raw = marks.get("theory_raw", 0) or 0
                pr_raw = marks.get("prac_raw", 0) or 0
                
                fm_info = subject_fm_data.get(sub_id, {"th_max": 0, "pr_max": 0})
                th_fm = fm_info["th_max"]
                pr_fm = fm_info["pr_max"]

                total_raw += th_raw + (pr_raw if pr_fm > 0 else 0)
                total_fm_sum += th_fm + pr_fm
                
                # Use the already calculated gradepoint and fail flags
                sub_gp = marks.get("gradepoint", 0) or 0
                combined_gp_sum += sub_gp
                sub_count += 1
                
                if marks.get("th_fail", False) or marks.get("pr_fail", False):
                    is_failed = True
                    fail_count += 1
                
            data[sn]["is_failed"] = is_failed
            data[sn]["total_obt"] = int(total_raw) if total_raw == int(total_raw) else round(total_raw, 2)
            data[sn]["total_max"] = int(total_fm_sum)
            
            final_percent = 0
            if total_fm_sum > 0:
                final_percent = round(total_raw * 100 / total_fm_sum, 2)
            data[sn]["percent"] = final_percent if (not is_failed and total_fm_sum > 0) else "-"
            
            # Derived explicitly using percentage logic as requested
            from panel.func import get_grade_point_exam, remarks, samataFinalRemarks
            
            if is_failed:
                data[sn]["gp"] = 0
                if this_term.final_term:
                    data[sn]["remarks"] = samataFinalRemarks(fail_count)
                else:
                    data[sn]["remarks"] = "Labour Hard"
            else:
                grade_res = get_grade_point_exam(final_percent)
                # Ensure GPA is extracted correctly
                calc_gpa = grade_res[2] if len(grade_res) > 2 else 0
                data[sn]["gp"] = calc_gpa
                if this_term.final_term:
                    data[sn]["remarks"] = samataFinalRemarks(fail_count)
                else:
                    data[sn]["remarks"] = getattr(grade_res, '[3]', remarks(calc_gpa))

            
            data[sn]["rank"] = "-" if is_failed else calculated_rank.get(student.student.reg_no, "-")

        # Custom Ranking Logic for Print View (Consistent with Preview)
        student_rank_list = []
        for sn_key, std_data in data.items():
            # Create a simple list for ranking purposes
            student_rank_list.append({
                "reg_no": std_data["reg_no"],
                "gpa": _as_float(std_data.get("gp", 0)),
                "total_obt": _as_float(std_data.get("total_obt", 0)),
                "overall_percent": _as_float(std_data.get("percent", 0)),
                "pass_all": not std_data.get("is_failed", False),
            })

        # Filter passed students for ranking
        passed_students = [s for s in student_rank_list if s["pass_all"]]
        
        # Ranking criteria based on user selection
        if rank_by == "gpa":
            # Primary: GPA (desc), Secondary: Grand Total (desc)
            passed_students.sort(key=lambda x: (
                -round(_as_float(x.get("gpa", 0)), 2), 
                -round(_as_float(x.get("total_obt", 0)), 2), 
                x.get("name", "")
            ))
        else:
            # Primary: Grand Total (desc), Secondary: GPA (desc)
            passed_students.sort(key=lambda x: (
                -round(_as_float(x.get("total_obt", 0)), 2), 
                -round(_as_float(x.get("gpa", 0)), 2), 
                x.get("name", "")
            ))

        # Assign dense ranking (1223 style)
        rank_map = {}
        current_rank = 0
        prev_score = None
        for std in passed_students:
            # Score depends on selected primary criteria
            current_score = round(_as_float(std.get("gpa", 0)), 2) if rank_by == "gpa" else round(_as_float(std.get("total_obt", 0)), 2)
            
            if current_score != prev_score:
                current_rank += 1
                prev_score = current_score
            
            rank_map[std["reg_no"]] = current_rank

        # Update the main data dict with the new ranks and format GPA
        for sn_key, std_data in data.items():
            if not std_data.get("is_failed", False):
                std_data["rank"] = rank_map.get(std_data["reg_no"], "-")
                gpa_grade_str = gpFromGPA(std_data.get("gp", 0))
                std_data["gpa_grade_l"], std_data["gpa_grade_s"] = split_gpa_grade(gpa_grade_str)
            else:
                std_data["rank"] = "-"
            
            # Remove .00 from gp if it's a whole number
            gp_val = std_data.get("gp", 0)
            if gp_val == int(gp_val):
                std_data["gp"] = int(gp_val)

        # Filter the data based on user selection (0=None, 1=Pass, 2=Fail)
        if data_filter == 1: # Pass
            data = {k: v for k, v in data.items() if not v.get("is_failed", False)}
        elif data_filter == 2: # Fail
            data = {k: v for k, v in data.items() if v.get("is_failed", False)}

        # Sort the final data by requested Order By
        # 1=Registration number, 2=Roll no, 3=Rank
        order_by = int(request.POST.get("order", "1"))
        
        sorted_items = sorted(data.items(), key=lambda x: (
            (0 if not x[1].get("is_failed", False) else 1) if order_by == 3 else 0,
            (x[1]["rank"] if not x[1].get("is_failed", False) and isinstance(x[1]["rank"], int) else 9999) if order_by == 3 else 0,
            x[1]["reg_no"] if order_by == 1 else (x[1].get("roll_no", 0) or 0) if order_by == 2 else 0,
            x[1]["name"]
        ))
        
        new_data = {}
        for idx, (old_sn, std_data) in enumerate(sorted_items, 1):
            new_data[idx] = std_data
        data = new_data

        context = {
            "school": school, "term": this_term, "year": this_term.year,
            "data": data, "grade": this_grade, "section": this_section,
            "subjects": subjects, "subjectcount": subjectcount,
            "source_terms": source_terms, "ledgermode": ledgermode, "ledgertype": ledgertype,
            "subject_colspan": subjects.count() * 2,
            "subject_fm_list": subject_fm_list,
            "printtype": printtype,
        }

        # Unified Rendering Layout matching Ledger Preview format and Summarized format logic
        return render(request, "panel/printledgernow_weighted.html", context)
    else:
        return HttpResponseRedirect("/panel/")


@login_required
def printledgernow2078(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    if request.method == "POST":
        edusession = request.POST.get("edusession")
        term = request.POST.get("term")
        printtype = int(request.POST.get("printtype"))
        grade = request.POST.get("grade2", 0)
        section = request.POST.get("section2", 0)
        # printtype = request.POST.get('printtype', )  # 1 DETAIL 2 SUMMARIZED

        print("PRINTTYPE", printtype)

        if grade == 0 or grade == None or grade == "":
            return HttpResponse(
                "Sorry! something went wrong. Please take care while submitting data."
            )
        else:
            this_grade = SchoolGrade.objects.get(id=grade)
        this_session = EduSession.objects.get(id=edusession)
        this_term = SchoolTerm.objects.get(id=term)

        # subjectcount = Subject.objects.filter(branch=school, grade=this_grade, status=True).count()

        if int(section) > 0:
            this_section = Section.objects.get(id=section)
        else:
            this_section = False
        calculated_rank = ""
        subjects = Subject.objects.filter(
            branch=school, grade=this_grade, status=True
        ).order_by("id")
        this_grade_subjects = Subject.objects.filter(
            branch=school, grade=this_grade, status=True
        ).order_by("id")
        subjectcount = ""
        for subject in subjects:
            subjectcount += "1"

        calculated_rank = False
        if this_section == False:
            students = Student.objects.filter(
                school=school, grade=this_grade, status=True
            )
            # calculated_rank = calculaterank(school.id, this_session, grade, term)
        else:
            students = Student.objects.filter(
                school=school, grade=this_grade, section=this_section, status=True
            )
            # calculated_rank = calculaterank(
            #     school.id, this_session, grade, term, this_section
            # )
            # print(school.id, this_session, grade, term, this_section)
            # print('calculated rank ', calculated_rank)
        sn = 0
        data = {}
        for student in students:
            sn += 1
            data[sn] = {}
            data[sn]["reg_no"] = student.reg_no
            data[sn]["name"] = student.name
            data[sn]["section"] = student.section
            # if student.reg_no in calculated_rank:
            #     data[sn]["rank"] = calculated_rank[student.reg_no]
            # else:
            #     data[sn]["rank"] = "-"

            if printtype == 2:
                # sd = summarizedResult(school, term, grade, student.reg_no)
                sd = detailResult2078(school, term, grade, student.reg_no, printtype)
                data[sn]["mo_th"] = sd["mo_th"]
                data[sn]["mo_pr"] = sd["mo_pr"]
                data[sn]["total"] = sd["total"]
                data[sn]["gp"] = sd["gp"]
                data[sn]["remarks"] = sd["remarks"]
                # print(summarizedResult)
                # print('Summarized Result')
            else:
                sd = detailResult2078(school, term, grade, student.reg_no, printtype)
                data[sn]["mo_th"] = sd["mo_th"]
                data[sn]["mo_pr"] = sd["mo_pr"]
                data[sn]["total"] = sd["total"]
                data[sn]["gp"] = sd["gp"]
                data[sn]["subjects"] = sd["subjects"]
                data[sn]["remarks"] = sd["remarks"]

                # print(detailResult, subjectcount)
                # print('Detail Result')

        context = {
            "school": school,
            "term": this_term,
            "year": this_term.year,
            "data": data,
            "grade": this_grade,
            "section": this_section,
            "subjects": this_grade_subjects,
            "subjectcount": subjectcount,
        }
        if printtype == 2:
            return render(request, "panel/printledgernow_summarized.html", context)
        else:
            return render(request, "panel/printledgernow_detailed_2078.html", context)
    else:
        return HttpResponseRedirect("/panel/")


@login_required
def printgradesheetnow2079(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    slogan = " &nbsp; "
    #if school.id <= 13:
    #    # Samata School
    #    slogan = "Education for all."
    #    logo = "https://cdn.hamro.com/simsnepal/logos/logo.jpg"
    if school.id == 14:
        # CSA Montessori
        slogan = "Soaring to Excellence"
        logo = "https://cdn.hamro.com/simsnepal/logos/csa.jpg"
    elif school.id == 15:
        # Paramount Children Academy
        slogan = " &nbsp; "
        logo = "https://cdn.hamro.com/simsnepal/logos/paramount.png"
    else:
        # Samata School
        slogan = "Education for all."
        logo = "https://cdn.hamro.com/simsnepal/logos/logo.jpg"

    if request.method == "POST":
        edusession = request.POST.get("edusession")
        term = request.POST.get("term")
        printtype = int(request.POST.get("printtype"))
        grade = request.POST.get("grade2", 0)
        section = request.POST.get("section2", 0)
        # printtype = request.POST.get('printtype', )  # 1 DETAIL 2 SUMMARIZED

        print("PRINTTYPE", printtype)

        if grade == 0 or grade == None or grade == "":
            return HttpResponse(
                "Sorry! something went wrong. Please take care while submitting data."
            )
        else:
            this_grade = SchoolGrade.objects.get(id=grade)
        this_session = EduSession.objects.get(id=edusession)
        this_term = SchoolTerm.objects.get(id=term)

        # subjectcount = Subject.objects.filter(branch=school, grade=this_grade, status=True).count()

        if int(section) > 0:
            this_section = Section.objects.get(id=section)
        else:
            this_section = False
        calculated_rank = ""
        subjects = Subject.objects.filter(
            branch=school, grade=this_grade, status=True
        ).order_by("id")
        this_grade_subjects = Subject.objects.filter(
            branch=school, grade=this_grade, status=True
        ).order_by("id")
        subjectcount = ""
        for subject in subjects:
            subjectcount += "1"
        if this_section == False:
            students = StudentSession.objects.filter(
                grade=this_grade, status=True
            )
            calculated_rank = calculate_rank(school.id, this_session, grade, term)
        else:
            students = StudentSession.objects.filter(
                session=this_session, grade=this_grade, section=this_section, status=True
            )
            calculated_rank = calculate_rank(
                school.id, this_session, grade, term, this_section
            )
            # print(school.id, this_session, grade, term, this_section)
            # print('calculated rank ', calculated_rank)
        sn = 0
        data = {}
        for student in students:
            sn += 1
            data[sn] = {}
            data[sn]["reg_no"] = student.student.reg_no
            data[sn]["name"] = student.student.name
            data[sn]["grade"] = student.grade
            data[sn]["section"] = student.section
            if student.student.reg_no in calculated_rank:
                data[sn]["rank"] = calculated_rank[student.student.reg_no]
            else:
                data[sn]["rank"] = "-"

            if printtype == 2:
                # sd = summarizedResult(school, term, grade, student.reg_no)
                sd = detailResult2078(school, term, grade, student.student.reg_no, printtype)
                data[sn]["mo_th"] = sd["mo_th"]
                data[sn]["mo_pr"] = sd["mo_pr"]
                data[sn]["total"] = sd["total"]
                data[sn]["gp"] = sd["gp"]
                data[sn]["remarks"] = sd["remarks"]
                # print(summarizedResult)
                # print('Summarized Result')
            else:
                sd = detailResult2078(school, term, grade, student.student.reg_no, printtype, edusession=edusession)
                # sd = detailResult2078(school, term, grade, student.student.reg_no, printtype)
                data[sn]["mo_th"] = sd["mo_th"]
                data[sn]["mo_pr"] = sd["mo_pr"]
                data[sn]["total"] = sd["total"]
                data[sn]["gp"] = sd["gp"]
                data[sn]["subjects"] = sd["subjects"]
                data[sn]["remarks"] = sd["remarks"]

                # print(detailResult, subjectcount)
                # print('Detail Result')
        scount = 13 - subjects.count()
        subjectcount = range(scount)

        context = {
            "school": school,
            "term": this_term,
            "year": this_term.year,
            "data": data,
            "grade": this_grade,
            "section": this_section,
            "subjects": this_grade_subjects,
            "subjectcount": subjectcount,
            "std_list": data,
            "slogan": slogan,
            "logo": logo,
        }
        if printtype == 2:
            return render(request, "panel/gradesheetall_077.html", context)
        else:
            return render(request, "panel/gradesheetall_077.html", context)
    else:
        return HttpResponseRedirect("/panel/")


def termmanagement(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)

    try:
        branchuser = BranchUser.objects.get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )

    # gradelevel= GradeLevel.objects.get(id=level)
    schoolbranch = SchoolBranch.objects.get(id=branchuser.school_id)

    this_session = get_current_session()

    grade_level = GradeLevel.objects.all()
    grades = SchoolGrade.objects.filter(school=schoolbranch).order_by("id")

    school_terms = SchoolTerm.objects.filter(
        school=school, year=this_session
    )
    term_status = SchoolTermStatus.objects.all()
    term_calculation = ResultManagement.objects.filter(school=schoolbranch, year=this_session)
    
    tc_dic = dict()
    for tc in term_calculation:
        tc_dic[str(tc.school_term_id)] = dict()
        calc = json.loads(tc.term_calculation)
        for item in calc:
            tc_dic[str(tc.school_term_id)][str(item)] = calc[item]

    tc_dic = json.dumps(tc_dic)

    if request.method == "POST":
        termname = request.POST.get("termname")
        term_name_in_short = request.POST.get("term_name_in_short", "")
        url = request.POST.get("redurl")
        status = request.POST.get("termStatus")
        active_status = request.POST.get("activeStatus", "1")
        final_term = request.POST.get("final_term") == "yes"
        final_term_name = request.POST.get("final_term_name", "")

        termname = termname.title()
        term_status = SchoolTermStatus.objects.get(id=status)
        active_status = True if str(active_status) == "1" else False
        if not final_term:
            final_term_name = ""
        if (
                SchoolTerm.objects.filter(
                    year=this_session, school=school, term_name=termname
                ).count()
                == 1
        ):
            term = SchoolTerm.objects.get(
                year=this_session, school=school, term_name=termname
            )
            term.term_name = termname
            term.name_in_short = term_name_in_short
            term.active = active_status
            term.status = term_status
            term.final_term = final_term
            term.final_term_name = final_term_name
            term.save()
        else:
            term = SchoolTerm()
            term.school = school
            term.year = this_session
            term.term_name = termname
            term.name_in_short = term_name_in_short
            term.active = active_status
            term.status = term_status
            term.final_term = final_term
            term.final_term_name = final_term_name
            term.save()

            all_terms = SchoolTerm.objects.filter(year=this_session, school=school, active=True)

            result_calc = ResultManagement()
            result_calc.school = school
            result_calc.year = this_session
            result_calc.school_term = term

            term_mgmt = dict()
            for this_term in all_terms:
                term_mgmt[str(this_term.id)] = 100

            term_mgmt = json.dumps(term_mgmt)
            result_calc.term_calculation = term_mgmt

            result_calc.save()

        return HttpResponseRedirect(url)

    addterm = False
    listterm = False
    change_name = False
    result_calc = False
    term_name = ""

    if request.method == "GET" and "action" in request.GET:
        action = request.GET["action"]

        if action == "addterm":
            addterm = True
        elif action == "listterm":
            listterm = True
        elif action == "result_calc":
            result_calc = True
    else:
        if "cn" not in request.GET:
            return HttpResponseRedirect("/panel/terms/?action=listterm")

    if request.method == "GET" and "cn" in request.GET:
        cn = request.GET['cn']
        term_name = SchoolTerm.objects.get(id=cn)
        if term_name.school == branchuser.school:
            change_name = True

    # if request.method == "GET" and "" in request.GET:

    context = {
        "grade_level": grade_level,
        "grades": grades,
        "branchuser": branchuser,
        "school": school,
        "terms": school_terms,
        "addterm": addterm,
        "listterm": listterm,
        "change_name": change_name,
        "term_name": term_name,
        "term_status": term_status,
        "result_calc": result_calc,
        "tc_dic": tc_dic,
    }
    return render(request, "panel/termmanagement.html", context)


@login_required
def weighted_result_calculation(request):
    user = request.user
    try:
        branchuser = BranchUser.objects.get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )

    school = SchoolBranch.objects.get(id=branchuser.school.id)
    this_session = get_current_session()

    grade_level = GradeLevel.objects.all()
    grades = SchoolGrade.objects.filter(school=school).order_by("id")
    terms = SchoolTerm.objects.filter(school=school, year=this_session).order_by("id")

    live_result = LiveResult.objects.filter(school=school).first()
    live_calc_type = getattr(live_result, "calculation_type", "legacy") if live_result else "legacy"

    wc_dic = {}
    weighted_configs = WeightedResultManagement.objects.filter(
        school=school, year=this_session
    )
    for result in weighted_configs:
        config = result.weight_config or {}
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except Exception:
                config = {}

        # Handle various legacy and current config shapes
        if "weights" in config:
            weights_block = config.get("weights", {})
            config = weights_block.get(str(result.school_term_id), {}) or weights_block.get(result.school_term_id, {})

        # Meta data for the term (plan, target_fm_th, target_fm_pr)
        wc_dic[str(result.school_term_id) + "_meta"] = {
            "plan": config.get("plan", "direct"),
            "target_fm_th": config.get("target_fm_th", config.get("target_fm", 100)),
            "target_fm_pr": config.get("target_fm_pr", config.get("target_fm", 100))
        }

        # Source term results
        sources = config.get("sources", config)
        wc_dic[str(result.school_term_id)] = sources

        for term_key, value in sources.items():
            try:
                term_id = int(term_key)
            except Exception:
                continue
            if isinstance(value, (int, float)):
                wc_dic[str(result.school_term_id)][str(term_id)] = {
                    "th_th": value,
                    "th_pr": value,
                    "pr_th": value,
                    "pr_pr": value,
                }
            elif isinstance(value, dict):
                th_block = value.get("th", None)
                pr_block = value.get("pr", None)
                has_nested = isinstance(th_block, dict) or isinstance(pr_block, dict)
                if ("th" in value or "pr" in value) and not has_nested:
                    wc_dic[str(result.school_term_id)][str(term_id)] = {
                        "th_th": value.get("th", 0),
                        "th_pr": value.get("pr", 0),
                        "pr_th": value.get("th", 0),
                        "pr_pr": value.get("pr", 0),
                    }
                else:
                    wc_dic[str(result.school_term_id)][str(term_id)] = {
                        "th_th": (th_block or {}).get("th", 0) if isinstance(th_block, dict) else 0,
                        "th_pr": (th_block or {}).get("pr", 0) if isinstance(th_block, dict) else 0,
                        "pr_th": (pr_block or {}).get("th", 0) if isinstance(pr_block, dict) else 0,
                        "pr_pr": (pr_block or {}).get("pr", 0) if isinstance(pr_block, dict) else 0,
                    }

    context = {
        "grade_level": grade_level,
        "grades": grades,
        "branchuser": branchuser,
        "school": school,
        "terms": terms,
        "wc_dic": json.dumps(wc_dic),
        "live_calc_type": live_calc_type,
    }
    return render(request, "panel/result_calc_weighted.html", context)


@login_required
def weighted_term_calculation(request):
    user = request.user
    try:
        branchuser = BranchUser.objects.get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )

    if request.method != "POST":
        return HttpResponseRedirect("/panel/terms/weighted-calculation/")

    school = SchoolBranch.objects.get(id=branchuser.school.id)
    this_session = get_current_session()
    term_id = request.POST.get("term_id")

    try:
        term_id = int(term_id)
    except Exception:
        return HttpResponseRedirect("/panel/terms/weighted-calculation/")

    def _safe_float(value):
        try:
            return float(value)
        except Exception:
            return 0.0

    # Global Plan and Target FMs (applies to the entire calculation for this target term)
    global_plan = request.POST.get("global_plan", "direct")
    global_target_fm_th = _safe_float(request.POST.get("global_target_fm_th", 100))
    global_target_fm_pr = _safe_float(request.POST.get("global_target_fm_pr", 100))

    sources = {}
    all_terms = SchoolTerm.objects.filter(year=this_session, school=school)
    for term in all_terms:
        if term.id > term_id:
            continue
        th_th = _safe_float(request.POST.get(f"th_th_{term.id}", 0))
        th_pr = _safe_float(request.POST.get(f"th_pr_{term.id}", 0))
        pr_th = _safe_float(request.POST.get(f"pr_th_{term.id}", 0))
        pr_pr = _safe_float(request.POST.get(f"pr_pr_{term.id}", 0))

        if th_th != 0 or th_pr != 0 or pr_th != 0 or pr_pr != 0:
            sources[str(term.id)] = {
                "th": {
                    "th": th_th, 
                    "pr": th_pr
                },
                "pr": {
                    "th": pr_th, 
                    "pr": pr_pr
                },
            }

    config = {
        "sources": sources,
        "plan": global_plan,
        "target_fm_th": global_target_fm_th,
        "target_fm_pr": global_target_fm_pr
    }
    school_term = SchoolTerm.objects.get(id=term_id)
    WeightedResultManagement.objects.update_or_create(
        year=this_session,
        school=school,
        school_term=school_term,
        defaults={"weight_config": config},
    )

    return HttpResponseRedirect("/panel/terms/weighted-calculation/")


@login_required
def activate_weighted_calculation(request):
    if request.method != "POST":
        return HttpResponseRedirect("/panel/terms/weighted-calculation/")

    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    
    calc_type = request.POST.get("calculation_type", "legacy")
    
    LiveResult.objects.update_or_create(
        school=school,
        defaults={"calculation_type": calc_type}
    )
    
    return HttpResponseRedirect("/panel/terms/weighted-calculation/")

@login_required
def resultmanagement(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)

    try:
        branchuser = BranchUser.objects.get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )

    schoolbranch = SchoolBranch.objects.get(id=branchuser.school_id)
    grade_level = GradeLevel.objects.all()
    grades = SchoolGrade.objects.filter(school=schoolbranch).order_by("id")

    this_session = get_current_session()

    exam_types = SchoolTerm.objects.filter(school=branchuser.school)

    live_result_status_count = LiveResult.objects.filter(school=school).count()
    if live_result_status_count == 1:
        live_result_status = LiveResult.objects.get(school=school)
        live_result_status = live_result_status.status
    else:
        live_result_status = False

    if request.method == "POST":
        if request.POST.get("submittype"):

            data = request.POST.get("submittype")

            if data == "resulttype":
                percent_or_grade = request.POST.get("percentorgrade")

                if percent_or_grade == "percent":
                    print("percent")
                    result = 1
                elif percent_or_grade == "grade":
                    print("grade")
                    result = 2

                if (
                        SchoolResultType.objects.filter(
                            school=school, session=this_session
                        ).count()
                        > 0
                ):
                    print("result found")
                else:
                    print("result not found")

                    schoolresulttype = SchoolResultType()
                    schoolresulttype.school = school
                    schoolresulttype.session = this_session
                    schoolresulttype.result_type = result
                    schoolresulttype.save()

            elif data == "termandgrades":
                examtype = request.POST.get("examtype")
                print(examtype)
                # for grade in grades:
                #     isit = request.POST.get(grade.id)
                #     print(grade.grade_name, isit)

                # checks =
                publishresultswitch = request.POST.get("publishresultswitch")
                if publishresultswitch == "on":
                    livestatus = True
                else:
                    livestatus = False
                print("publishresultswitch: ", publishresultswitch)
                calculation_type = request.POST.get("calculation_type", "legacy")
                checks = request.POST.getlist("checks[]")
                # checks = int(checks)

                checks = [int(i) for i in checks]

                print(checks)

                checks = json.dumps(checks)
                print(checks)
                if LiveResult.objects.filter(school=school).count() == 0:
                    liveresult = LiveResult()
                    liveresult.school = school
                    liveresult.term = examtype
                    liveresult.grade_list = checks
                    liveresult.status = livestatus
                    liveresult.calculation_type = calculation_type
                    liveresult.save()

                    live_result_status = liveresult.status
                else:
                    liveresult = LiveResult.objects.get(school=school)
                    liveresult.school = school
                    liveresult.term = examtype
                    liveresult.grade_list = checks
                    liveresult.status = livestatus
                    liveresult.calculation_type = calculation_type
                    liveresult.save()

                    live_result_status = liveresult.status
            # print(request.POST.get('resulttype'))

        # if request.POST.get('termtype'):
        #     for key, value in request.POST.items():
        #         print('Key: %s' % (key) )
        #         # print(f'Key: {key}') in Python >= 3.7
        #         print('Value %s' % (value) )
        #         # print(f'Value: {value}') in Python >= 3.7

    if SchoolResultType.objects.filter(school=school, session=this_session).count() > 0:
        schoolresulttype = True
        sr = SchoolResultType.objects.get(school=school, session=this_session)
    else:
        schoolresulttype = False
        sr = ""

    print("after schoolresulttype")

    if ResultManagement.objects.filter(school=school, year=this_session).count() > 0:
        resultmanagement = True
        rm = ResultManagement.objects.filter(school=school, year=this_session)
        # rm = json.loads(rm.term_calculation)
        # T
        term_count = 0
        term_fn = dict()

        print(rm)
        for items in rm:
            print(items)
            print(items.term_calculation)
            mark_ratio = json.loads(items.term_calculation)
            term_count += 1
            term_fn[term_count] = dict()
            term_fn[term_count]["name"] = items.school_term.term_name
            term_fn[term_count]["calculations"] = dict()

            for key, value in mark_ratio.items():
                print(key, value)
                term_fn[term_count]["calculations"]["term"] = key
                term_fn[term_count]["calculations"]["percentage"] = value

        print(rm)
        print(term_fn)
    else:
        resultmanagement = False
        print("Nothing FOund in ResultManagement")
        rm = ""

    if LiveResult.objects.filter(school=school).count() == 0:
        liveresult = False
        gradelist = ""
        live_calc_type = "legacy"
    else:
        liveresult = True
        lr = LiveResult.objects.get(school=school)

        lr_term = SchoolTerm.objects.get(id=lr.term)

        print(lr_term)

        gradelist = json.loads(lr.grade_list)
        live_calc_type = getattr(lr, "calculation_type", "legacy")

        # gradelist = tuple(gradelist)

        for grade in grades:
            if grade.id in gradelist:
                print(grade)
            # schoolgrade = SchoolGrade.objects.get(id=i)
            # print(i)

    context = {
        "grade_level": grade_level,
        "grades": grades,
        "gradelist": gradelist,
        "branchuser": branchuser,
        "exam_types": exam_types,
        "schoolresulttype": schoolresulttype,
        "sr": sr,
        "live_result_status": live_result_status,
        "resultmanagement": resultmanagement,
        "rm": rm,
        "school": school,
        "live_calc_type": live_calc_type,
    }
    return render(request, "panel/resultmanagement.html", context)


@login_required
def thepanel(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)

    try:
        branchuser = BranchUser.objects.get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )

    # gradelevel= GradeLevel.objects.get(id=level)
    schoolbranch = SchoolBranch.objects.get(id=branchuser.school_id)

    grade_level = GradeLevel.objects.all()
    grades = SchoolGrade.objects.filter(school=schoolbranch).order_by("id")

    this_session = get_current_session()

    resulttype = SchoolResultType.objects.filter(school=school, session=this_session)
    schoolresulttype = False
    if resulttype.count() == 0:
        resulttype_exists = False
    else:
        resulttype_exists = True
        schoolresulttype = SchoolResultType.objects.get(
            school=school, session=this_session
        )

    context = {
        "grade_level": grade_level,
        "grades": grades,
        "branchuser": branchuser,
        "resulttype_exists": resulttype_exists,
        "schoolresulttype": schoolresulttype,
        "school": school,
    }
    return render(request, "panel/resultmanagement.html", context)


def resultapi(request):
    this_session = get_current_session()
    if request.method == "POST":
        regno = request.POST.get("regno")
        code = request.POST.get("scode")
        try:
            code = int(code)
        except:
            context = {
                "message": "Sorry the security code of the student did not match."
            }
            return render(request, "panel/resultform.html", context)
        if Student.objects.filter(reg_no=regno).count() == 1:
            student = Student.objects.get(reg_no=int(regno))
            if student.pin_code != int(code):
                context = {
                    "message": "Sorry the security code of the student did not match."
                }
                return render(request, "panel/resultform.html", context)
            elif student.status != True:
                context = {
                    "message": "Sorry the account of the student with registration number "
                               + str(regno)
                               + " has been disabled."
                }
                return render(request, "panel/resultform.html", context)
            elif student.publish_result != True:
                context = {
                    "message": "Sorry the result of "
                               + str(student)
                               + " has been disabled. For more information Please contact on School."
                }
                return render(request, "panel/resultform.html", context)
            else:
                resultstatus = LiveResult.objects.get(school=student.school)
                gradelist = json.loads(resultstatus.gradelist)
                term = resultstatus.term
                this_term = SchoolTerm.objects.get(id=term)
                if student.grade.id not in gradelist:
                    message = (
                            "Sorry the result of Grade "
                            + student.grade.grade_name
                            + " has not been published yet. For more information please contact on School."
                    )
                    context = {"message": message}
                    return render(request, "panel/resultform.html", context)
        else:
            context = {
                "message": "Sorry student with the registration number could not be found."
            }
            return render(request, "panel/resultform.html", context)

        # sc
        mo_dict = dict()
        grade_subjects = Subject.objects.filter(
            grade=student.grade, branch=student.school, status=True
        )
        total_std = Student.objects.filter(
            school=student.school, grade=student.grade, status=1
        ).count()

        marks_obtained = MarkObtained.objects.filter(
            student=student.reg_no,
            session=this_session,
            grade=student.grade.id,
            term=term,
        )
        sub_count = 1
        total = dict()
        credithour = 0
        totalm = 0
        totaltm = 0
        totalpm = 0
        totaltmo = 0
        totalpmo = 0
        position = 0
        fail = 0
        totalstudent = Student.objects.filter(
            grade=student.grade, section=student.section
        ).count()
        # for calculating rank

        # req_rank = calculaterank(school=student.school.id, session=this_session, grade=int(student.grade.id), term=term,
        #                         section=student.section, regno=student.reg_no)
        req_rank = ""
        # print(req_rank)

        ## rank calculation ends

        # print(mod)
        subcount = 0
        cgpa = 0
        for subject in grade_subjects:
            for mo in marks_obtained:
                if subject.id == mo.subject:
                    subcount += 1
                    print(subcount)
                    mo_dict[sub_count] = dict()
                    this_subject = Subject.objects.get(id=int(mo.subject))
                    mo_dict[sub_count]["subject_name"] = this_subject
                    mo_dict[sub_count]["theory_fm"] = 4

                    credithour += 4

                    gfm = GradeFullMarks.objects.get(
                        subject=this_subject, term=this_term
                    )

                    totaltm += gfm.th_fm
                    totalpm += gfm.pr_fm
                    totaltmo += mo.th_mo
                    totalpmo += mo.pr_mo

                    if mo.th_mo > 0:
                        mth = mo.th_mo * 100 / gfm.th_fm
                        mthg = grading(mth)[0]
                        mthgp = grading(mth)[1]

                    elif gfm.th_fm == 0:
                        mthg = ""
                        mthgp = 0
                    else:
                        mthg = "N"
                        fail += 1
                        mthgp = 0

                    if mo.pr_mo > 0:
                        mpr = mo.pr_mo * 100 / gfm.pr_fm
                        mprg = grading(mpr)[0]
                        mprgp = grading(mpr)[1]
                    elif gfm.pr_fm == 0:
                        mprg = ""
                        mprgp = 0
                    else:
                        mprg = "N"
                        fail += 1
                        mprgp = 0

                    totfm = gfm.th_fm + gfm.pr_fm
                    totmo = mo.th_mo + mo.pr_mo
                    if gfm.pr_fm != 0 and gfm.th_fm != 0:
                        totmogp = round((mthgp + mprgp) / 2, 2)
                        totmogp = grading(
                            (mo.th_mo + mo.pr_mo) * 100 / (gfm.th_fm + gfm.pr_fm)
                        )[1]

                    else:
                        totmogp = mthgp + mprgp

                    cgpa += totmogp

                    if totmo > 0:
                        totmop = totmo * 100 / totfm
                        mo_dict[sub_count]["total_mo"] = grading(totmop)[0]
                    else:
                        mo_dict[sub_count]["total_mo"] = "N"

                    mo_dict[sub_count]["theory_mo"] = mthg  # mo.th_mo  # mthg
                    mo_dict[sub_count]["prac_mo"] = mprg
                    mo_dict[sub_count]["gradepoint"] = totmogp

                    sub_count += 1

        # cgpa = grading(totmo*100/totfm)[1]
        cgpa = round(cgpa / subcount, 2)

        totaltm += gfm.th_fm
        totalpm += gfm.pr_fm
        totalm = totaltm + totalpm
        totalmo = totaltmo + totalpmo
        totalg = totalmo * 100 / totalm

        totaltmog = totaltmo * 100 / totaltm

        if totalpmo > 0:
            totalpmog = totalpmo * 100 / totalpm
            total["og_pr"] = grading(totalpmog)[0]
        else:
            totalpmog = ""
            total["og_pr"] = totalpmog

        total["credithour"] = credithour
        total["og_th"] = grading(totaltmog)[0]
        total["tog"] = grading(totalg)[0]
        totalgpa = grading(totalg)[1]
        # total[''] =

        remark = remarks(cgpa)

        context = {
            "year": this_session.year,
            "term": this_term,
            "student": student,
            "mo_dict": mo_dict,
            "total": total,
            "totalgpa": totalgpa,
            "totalstudent": totalstudent,
            "fail": fail,
            "position": position,
            "req_rank": req_rank,
            "cgpa": cgpa,
            "remarks": remark,
        }
        if student.school.id == 14 or student.school.id == 15:
            return render(request, "panel/result77.html", context)
        else:
            return render(request, "panel/samatapr2077.html", context)
    else:
        return render(request, "panel/resultform.html", )
        # return HttpResponse('Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.')


def resultapinew(request):
    this_session = get_current_session()
    if request.method == "POST":
        regno = request.POST.get("regno")
        code = request.POST.get("scode")

        if Student.objects.filter(reg_no=regno).count() == 1:
            student = Student.objects.get(reg_no=int(regno))
            if student.pin_code != int(code):
                context = {
                    "message": "Sorry the security code of the student did not match."
                }
                return render(request, "panel/resultform.html", context)
            elif student.status != True:
                context = {
                    "message": "Sorry the account of the student with registration number "
                               + str(regno)
                               + " has been disabled."
                }
                return render(request, "panel/resultform.html", context)
            elif student.publish_result != True:
                context = {
                    "message": "Sorry the result of "
                               + str(student)
                               + " has been disabled. For more information Please contact on School."
                }
                return render(request, "panel/resultform.html", context)
            else:
                resultstatus = LiveResult.objects.get(school=student.school)
                gradelist = json.loads(resultstatus.gradelist)
                term = resultstatus.term
                this_term = SchoolTerm.objects.get(id=term)
                if student.grade.id not in gradelist:
                    message = (
                            "Sorry the result of Grade "
                            + student.grade.grade_name
                            + " has not been published yet. For more information please contact on School."
                    )
                    context = {"message": message}
                    return render(request, "panel/resultform.html", context)
        else:
            context = {
                "message": "Sorry student with the registration number could not be found."
            }
            return render(request, "panel/resultform.html", context)

        # sc
        mo_dict = dict()
        grade_subjects = Subject.objects.filter(
            grade=student.grade, branch=student.school, status=True
        ).order_by("id")
        total_std = Student.objects.filter(
            school=student.school, grade=student.grade, status=1
        ).count()

        marks_obtained = MarkObtained.objects.filter(
            student=student.reg_no,
            session=this_session,
            grade=student.grade.id,
            term=term,
        )
        sub_count = 1
        total = dict()
        credithour = 0
        totalm = 0
        totaltm = 0
        totalpm = 0
        totaltmo = 0
        totalpmo = 0
        position = 0
        fail = 0
        totalgpa = 0
        totalstudent = Student.objects.filter(
            grade=student.grade, section=student.section
        ).count()
        # for calculating rank

        # req_rank = calculaterank(school=student.school.id, session=this_session, grade=int(student.grade.id), term=term,
        #                         section=student.section, regno=student.reg_no)
        req_rank = ""
        # print(req_rank)

        ## rank calculation ends

        # print(mod)
        sub_count = 0
        cgpa = 0
        gp16count = 0
        for subject in grade_subjects:
            sub_count += 1
            mo_dict[sub_count] = {}
            subject_marks_obtained = MarkObtained.objects.get(
                student=student.reg_no,
                session=this_session,
                grade=student.grade.id,
                term=term,
                subject=subject.id,
            )
            gfm = GradeFullMarks.objects.get(subject=subject.id, term=this_term)

            mo_dict[sub_count]["subject_name"] = subject.subject

            if gfm.th_fm > 0:
                if gfm.pr_fm > 0:
                    # Both Theory and practical Marks
                    mth = subject_marks_obtained.th_mo * 100 / gfm.th_fm
                    mpr = subject_marks_obtained.pr_mo * 100 / gfm.pr_fm
                else:
                    # Only theory Marks
                    mth = subject_marks_obtained.th_mo * 100 / gfm.th_fm
                    mpr = 0
            # elif gfm.pr_fm > 0:
            #     # Only Practical Marks
            #     mpr = subject_marks_obtained.th_mo * 100 / gfm.pr_fm
            #     mth = 0

            total_fm = gfm.th_fm + gfm.pr_fm
            total_mo = subject_marks_obtained.th_mo + subject_marks_obtained.pr_mo

            if total_mo > 0:
                totmop = total_mo * 100 / total_fm
                mo_dict[sub_count]["total_mo"] = grading(totmop)[0]
                totmogp = grading(totmop)[1]
                totalmog = grading(totmop)[0]
                if subject.heavy_weight:
                    if int(totmogp) <= 1.6:
                        print("TOTMOGP: ", totmogp)
                        gp16count += 1
            else:
                mo_dict[sub_count]["total_mo"] = "N"
                totmogp = 0
                gp16count += 1

            cgpa += totmogp

            mthg = grading(mth)[0]
            if gfm.pr_fm > 0:
                mprg = grading(mpr)[0]
            else:
                mprg = ""

            mo_dict[sub_count]["theory_mo"] = mthg  # mo.th_mo  # mthg
            mo_dict[sub_count]["prac_mo"] = mprg
            mo_dict[sub_count]["gradepoint"] = totmogp

        try:
            cgpa = round(cgpa / sub_count, 2)
        except ZeroDivisionError as error:
            cgpa = "Value is 0"

        the_remarks = samataFinalRemarks(gp16count)
        print(the_remarks)

        # totaltm += gfm.th_fm
        # totalpm += gfm.pr_fm
        # totalm = totaltm + totalpm
        # totalmo = totaltmo + totalpmo
        # totalg = totalmo * 100 / totalm

        # totaltmog = totaltmo * 100 / totaltm

        # if totalpmo > 0:
        #     totalpmog = totalpmo * 100 / totalpm
        #     total['og_pr'] = grading(totalpmog)[0]
        # else:
        #     totalpmog = ''
        #     total['og_pr'] = totalpmog

        # total['credithour'] = credithour
        # total['og_th'] = grading(totaltmog)[0]
        # total['tog'] = grading(totalg)[0]
        # totalgpa = grading(totalg)[1]
        # total[''] =

        context = {
            "year": this_session.year,
            "term": this_term,
            "student": student,
            "mo_dict": mo_dict,
            "total": total,
            "totalgpa": totalgpa,
            "totalstudent": totalstudent,
            "fail": fail,
            "position": position,
            "req_rank": req_rank,
            "cgpa": cgpa,
            "remarks": the_remarks,
        }
        if student.school.id == 14 or student.school.id == 15:
            return render(request, "panel/result77.html", context)
        else:
            return render(request, "panel/samatapr2077.html", context)
    else:
        return render(request, "panel/resultform.html", )
        # return HttpResponse('Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.')


def privatesultnew(request, regno):
    # if request.method == 'POST':
    # regno = request.POST.get('regno')
    # code = request.POST.get('scode')
    this_session = get_current_session()
    regno = regno

    if Student.objects.filter(reg_no=regno).count() == 1:
        student = Student.objects.get(reg_no=int(regno))
        # if student.pin_code != int(code):
        #     context = {'message': 'Sorry the security code of the student did not match.'}
        #     return render(request, 'panel/resultform.html', context)
        # el
        if student.status != True:
            context = {
                "message": "Sorry the account of the student with registration number "
                           + str(regno)
                           + " has been disabled."
            }
            return render(request, "panel/resultform.html", context)
        # elif student.publish_result != True:
        #     context = {'message': 'Sorry the result of ' + str(
        #         student) + ' has been disabled. For more information Please contact on School.'}
        #     return render(request, 'panel/resultform.html', context)
        else:
            resultstatus = LiveResult.objects.get(school=student.school)
            gradelist = json.loads(resultstatus.gradelist)
            term = resultstatus.term
            this_term = SchoolTerm.objects.get(id=term)
            if student.grade.id not in gradelist:
                message = (
                        "Sorry the result of Grade "
                        + student.grade.grade_name
                        + " has not been published yet. For more information please contact on School."
                )
                context = {"message": message}
                return render(request, "panel/resultform.html", context)
    else:
        context = {
            "message": "Sorry student with the registration number could not be found."
        }
        return render(request, "panel/resultform.html", context)

    # sc
    mo_dict = dict()
    grade_subjects = Subject.objects.filter(
        grade=student.grade, branch=student.school, status=True
    ).order_by("id")
    total_std = Student.objects.filter(
        school=student.school, grade=student.grade, status=1
    ).count()

    marks_obtained = MarkObtained.objects.filter(
        student=student.reg_no, session=this_session, grade=student.grade.id, term=term
    )
    sub_count = 1
    total = dict()
    credithour = 0
    totalm = 0
    totaltm = 0
    totalpm = 0
    totaltmo = 0
    totalpmo = 0
    position = 0
    fail = 0
    totalgpa = 0
    totalstudent = Student.objects.filter(
        grade=student.grade, section=student.section
    ).count()
    # for calculating rank

    # req_rank = calculaterank(school=student.school.id, session=this_session, grade=int(student.grade.id), term=term,
    #                         section=student.section, regno=student.reg_no)
    req_rank = ""
    # print(req_rank)

    ## rank calculation ends

    # print(mod)
    sub_count = 0
    cgpa = 0
    gp16count = 0
    for subject in grade_subjects:
        sub_count += 1
        mo_dict[sub_count] = {}
        subject_marks_obtained = MarkObtained.objects.get(
            student=student.reg_no,
            session=this_session,
            grade=student.grade.id,
            term=term,
            subject=subject.id,
        )
        gfm = GradeFullMarks.objects.get(subject=subject.id, term=this_term)

        mo_dict[sub_count]["subject_name"] = subject.subject

        if gfm.th_fm > 0:
            if gfm.pr_fm > 0:
                # Both Theory and practical Marks
                mth = subject_marks_obtained.th_mo * 100 / gfm.th_fm
                mpr = subject_marks_obtained.pr_mo * 100 / gfm.pr_fm
            else:
                # Only theory Marks
                mth = subject_marks_obtained.th_mo * 100 / gfm.th_fm
                mpr = 0
        # elif gfm.pr_fm > 0:
        #     # Only Practical Marks
        #     mpr = subject_marks_obtained.th_mo * 100 / gfm.pr_fm
        #     mth = 0

        total_fm = gfm.th_fm + gfm.pr_fm
        total_mo = subject_marks_obtained.th_mo + subject_marks_obtained.pr_mo

        if total_mo > 0:
            totmop = total_mo * 100 / total_fm
            mo_dict[sub_count]["total_mo"] = grading(totmop)[0]
            totmogp = grading(totmop)[1]
            totalmog = grading(totmop)[0]
            if subject.heavy_weight:
                if int(totmogp) <= 1.6:
                    print("TOTMOGP: ", totmogp)
                    gp16count += 1
        else:
            mo_dict[sub_count]["total_mo"] = "N"
            totmogp = 0
            gp16count += 1

        cgpa += totmogp

        mthg = grading(mth)[0]
        if gfm.pr_fm > 0:
            mprg = grading(mpr)[0]
        else:
            mprg = ""

        mo_dict[sub_count]["theory_mo"] = mthg  # mo.th_mo  # mthg
        mo_dict[sub_count]["prac_mo"] = mprg
        mo_dict[sub_count]["gradepoint"] = totmogp

    try:
        cgpa = round(cgpa / sub_count, 2)
    except ZeroDivisionError as error:
        cgpa = "Value is 0"

    the_remarks = samataFinalRemarks(gp16count)
    print(the_remarks)

    # totaltm += gfm.th_fm
    # totalpm += gfm.pr_fm
    # totalm = totaltm + totalpm
    # totalmo = totaltmo + totalpmo
    # totalg = totalmo * 100 / totalm

    # totaltmog = totaltmo * 100 / totaltm

    # if totalpmo > 0:
    #     totalpmog = totalpmo * 100 / totalpm
    #     total['og_pr'] = grading(totalpmog)[0]
    # else:
    #     totalpmog = ''
    #     total['og_pr'] = totalpmog

    # total['credithour'] = credithour
    # total['og_th'] = grading(totaltmog)[0]
    # total['tog'] = grading(totalg)[0]
    # totalgpa = grading(totalg)[1]
    # total[''] =

    the_space = ""
    spacing = 14 - sub_count
    for i in range(spacing):
        the_space += "a"

    context = {
        "year": this_year,
        "term": this_term,
        "student": student,
        "mo_dict": mo_dict,
        "total": total,
        "totalgpa": totalgpa,
        "totalstudent": totalstudent,
        "fail": fail,
        "position": position,
        "req_rank": req_rank,
        "cgpa": cgpa,
        "remarks": the_remarks,
        "the_space": the_space,
    }
    if student.school.id == 14 or student.school.id == 15:
        return render(request, "panel/result77.html", context)
    else:
        # return render(request, 'panel/samatapr2077.html', context)
        # return render(request, 'panel/privategradesheet2077.html', context)
        return render(request, "panel/pgs2077.html", context)
    # else:
    #     return render(request, 'panel/resultform.html', )
    # return HttpResponse('Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.')


def grading(percent):
    if percent > 100:
        return ("SOMETHING WRONG", 4.0)
    if 90 <= percent <= 100:
        return ("A+", 4.0, "Excellent")
    elif 80 <= percent < 90:
        return ("A", 3.6, "Very Nice")
        # return(result)
    elif 70 <= percent < 80:
        return ("B+", 3.2, "Nice")
        # return(result)
    elif 60 <= percent < 70:
        return ("B", 2.8, "Good")
        # return(result)
    elif 50 <= percent < 60:
        return ("C+", 2.4, "Study More")
        # return(result)
    elif 40 <= percent < 50:
        return ("C", 2.0, "Pay Attention")
        # return(result)
    elif 30 <= percent < 40:
        return ("D+", 1.6, "Labour Hard")
    elif 20 <= percent < 30:
        return ("D", 1.2, "Labour Hard")
        # return(result)
    elif percent >= 1 and percent < 20:
        return ("E", 0.8, "Labour Hardrder")
        # return(result)
    elif percent == 0:
        return ("N", 0, "Try Next Time")
        # return(result)

"""
def search(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)

    try:
        branchuser = BranchUser.objects.get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )

    # gradelevel= GradeLevel.objects.get(id=level)
    schoolbranch = SchoolBranch.objects.get(id=branchuser.school_id)

    grade_level = GradeLevel.objects.all()
    grades = SchoolGrade.objects.filter(school=schoolbranch).order_by("id")

    resulttype = SchoolResultType.objects.filter(school=school, session=this_session)
    schoolresulttype = False
    if resulttype.count() == 0:
        resulttype_exists = False
    else:
        resulttype_exists = True
        schoolresulttype = SchoolResultType.objects.get(
            school=school, session=this_session
        )

    data = request.GET.get("q")
    # print(data)
    if data.isdigit() == True:
        # print('True')
        # exam_years = Examyears.objects.all().order_by('-id')
        # exam_types = Examtypes.objects.all()
        # year = s['year']
        students = (
            Student.objects.all()
                .filter(reg_no__contains=data, school=schoolbranch)
                .order_by("reg_no")
        )
    else:
        # exam_years = Examyears.objects.all().order_by('-id')
        # exam_types = Examtypes.objects.all()
        # year = s['year']
        students = (
            Student.objects.all()
                .filter(name__icontains=data, school=schoolbranch)
                .order_by("reg_no")
        )

    paginator = Paginator(students, 100)
    page = request.GET.get("page", 1)
    try:
        student = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first pa
        student = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        student = paginator.page(paginator.num_pages)

    result = {
        "data": data,
        "students": student,
        "grade_level": grade_level,
        "grades": grades,
        "branchuser": branchuser,
        "resulttype_exists": resulttype_exists,
        "schoolresulttype": schoolresulttype,
    }  # 'exam_years': exam_years, 'exam_types': exam_types, 'year':year,}
    return render(request, "panel/search1.html", result)
"""

def search(request):
    this_session = get_current_session()
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)

    try:
        branchuser = BranchUser.objects.get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )

    # gradelevel= GradeLevel.objects.get(id=level)
    schoolbranch = SchoolBranch.objects.get(id=branchuser.school_id)

    grade_level = GradeLevel.objects.all()
    grades = SchoolGrade.objects.filter(school=schoolbranch).order_by("id")

    resulttype = SchoolResultType.objects.filter(school=school, session=this_session)
    schoolresulttype = False
    if resulttype.count() == 0:
        resulttype_exists = False
    else:
        resulttype_exists = True
        schoolresulttype = SchoolResultType.objects.get(
            school=school, session=this_session
        )

    data = request.GET.get("q")
    # print(data)
    if data.isdigit():
        # print('True')
        # exam_years = Examyears.objects.all().order_by('-id')
        # exam_types = Examtypes.objects.all()
        # year = s['year']
        students = (StudentSession.objects.all().filter(student__reg_no__contains=data, session=this_session, student__school=schoolbranch,  status=True).order_by("student"))
            # Student.objects.all().filter(reg_no__contains=data, school=schoolbranch).order_by("reg_no")
    else:
        # exam_years = Examyears.objects.all().order_by('-id')
        # exam_types = Examtypes.objects.all()
        # year = s['year']
        students = (
            StudentSession.objects.all().filter(student__name__icontains=data, session=this_session, student__school=schoolbranch, status=True).order_by("student"))

    paginator = Paginator(students, 100)
    page = request.GET.get("page", 1)

    try:
        student = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first pa
        student = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        student = paginator.page(paginator.num_pages)

    result = {
        "data": data,
        "students": student,
        "grade_level": grade_level,
        "grades": grades,
        "branchuser": branchuser,
        "resulttype_exists": resulttype_exists,
        "schoolresulttype": schoolresulttype,
        "school": school,
    }  # 'exam_years': exam_years, 'exam_types': exam_types, 'year':year,}
    return render(request, "panel/search1.html", result)

@login_required
def school_private(request, regno):
    this_session = get_current_session()
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    # if request.method == 'POST':
    regno = regno

    if Student.objects.filter(reg_no=regno).count() == 1:
        student = Student.objects.get(reg_no=int(regno))

        if student.school != school:
            message = (
                    "Sorry you are not authorized to directly view the result of student from another school. Please fill the form to view the result of "
                    + student.name
                    + "."
            )
            context = {"message": message}
            return render(request, "panel/resultform.html", context)

        result_status = LiveResult.objects.get(school=student.school)
        grade_list = json.loads(result_status.grade_list)
        term = result_status.term
        this_term = SchoolTerm.objects.get(id=term)

        std_session = StudentSession.objects.get(student=student, status=True)

        if std_session.grade.id not in grade_list:
            message = (
                    "Sorry the result of Grade "
                    + std_session.grade.grade_name
                    + " has not been published yet. For more information please contact on School."
            )
            context = {"message": message}
            return render(request, "panel/resultform.html", context)
    else:
        context = {
            "message": "Sorry student with the registration number could not be found."
        }
        return render(request, "panel/resultform.html", context)

    # sc
    mo_dict = dict()
    grade_subjects = Subject.objects.filter(
        grade=std_session.grade, branch=student.school, status=True
    )
    total_std = StudentSession.objects.filter(
        grade=std_session.grade, status=1
    ).count()

    marks_obtained = MarkObtained.objects.filter(
        student=std_session.student.reg_no, session=this_session, grade=std_session.grade, term=term
    )
    sub_count = 1
    total = dict()
    credithour = 0
    totalm = 0
    totaltm = 0
    totalpm = 0
    totaltmo = 0
    totalpmo = 0
    position = 0
    fail = 0
    totalstudent = StudentSession.objects.filter(
        grade=std_session.grade, section=std_session.section
    ).count()
    # for calculating rank
    print("MARKS OBTAINED ")
    print(marks_obtained)

    req_rank = calculate_rank(
        school=student.school.id,
        session=this_session,
        grade=int(std_session.grade.id),
        term=term,
        section=std_session.section,
        regno=std_session.student.reg_no,
    )

    # print(req_rank)

    ## rank calculation ends

    # print(mod)
    subcount = 0
    cgpa = 0
    for subject in grade_subjects:
        for mo in marks_obtained:
            if subject.id == mo.subject:
                subcount += 1
                mo_dict[sub_count] = dict()
                this_subject = Subject.objects.get(id=int(mo.subject))
                mo_dict[sub_count]["subject_name"] = this_subject
                mo_dict[sub_count]["theory_fm"] = 4

                credithour += 4

                gfm = GradeFullMarks.objects.get(subject=this_subject, term=this_term)

                totaltm += gfm.th_fm
                totalpm += gfm.pr_fm
                totaltmo += mo.th_mo
                totalpmo += mo.pr_mo

                if mo.th_mo > 0:
                    mth = mo.th_mo * 100 / gfm.th_fm
                    mthg = grading(mth)[0]
                    mthgp = grading(mth)[1]
                elif gfm.th_fm == 0:
                    mthg = ""
                    mthgp = 0
                else:
                    mthg = "N"
                    fail += 1
                    mthgp = 0

                if mo.pr_mo > 0:
                    mpr = mo.pr_mo * 100 / gfm.pr_fm
                    mprg = grading(mpr)[0]
                    mprgp = grading(mpr)[1]
                elif gfm.pr_fm == 0:
                    mprg = ""
                    mprgp = 0
                else:
                    mprg = "N"
                    fail += 1
                    mprgp = 0

                totfm = gfm.th_fm + gfm.pr_fm
                totmo = mo.th_mo + mo.pr_mo
                if gfm.pr_fm != 0 and gfm.th_fm != 0:
                    totmogp = (mthgp + mprgp) / 2
                    totmogp = grading(
                        (mo.th_mo + mo.pr_mo) * 100 / (gfm.th_fm + gfm.pr_fm)
                    )[1]

                else:
                    totmogp = mthgp + mprgp

                cgpa += totmogp

                if totmo > 0:
                    totmop = totmo * 100 / totfm
                    mo_dict[sub_count]["total_mo"] = grading(totmop)[0]
                else:
                    mo_dict[sub_count]["total_mo"] = "N"

                mo_dict[sub_count]["theory_mo"] = mthg
                mo_dict[sub_count]["prac_mo"] = mprg
                mo_dict[sub_count]["gradepoint"] = totmogp

                sub_count += 1
        print("CGPA: ")
        print(cgpa)
        print("SUBCOUNT")
        print(sub_count)
        # cgpa = grading(totmo*100/totfm)[1]

        cgpa = 1# cgpa = round(cgpa / subcount, 2)

        totaltm += gfm.th_fm
        totalpm += gfm.pr_fm
        totalm = totaltm + totalpm
        totalmo = totaltmo + totalpmo
        totalg = totalmo * 100 / totalm

        totaltmog = totaltmo * 100 / totaltm

    if totalpmo > 0:
        totalpmog = totalpmo * 100 / totalpm
        total["og_pr"] = grading(totalpmog)[0]
    else:
        totalpmog = ""
        total["og_pr"] = totalpmog

    total["credithour"] = credithour
    total["og_th"] = grading(totaltmog)[0]
    total["tog"] = grading(totalg)[0]
    totalgpa = grading(totalg)[1]
    # total[''] =

    context = {
        "year": this_year,
        "term": this_term,
        "student": student,
        "mo_dict": mo_dict,
        "total": total,
        "totalgpa": totalgpa,
        "totalstudent": totalstudent,
        "fail": fail,
        "position": position,
        "req_rank": req_rank,
        "cgpa": cgpa,
    }
    return render(request, "panel/result.html", context)


@login_required
def marksgradesheet(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    edusession = EduSession.objects.all().order_by("-year")
    current_session = get_current_session()
    this_session = current_session  # Default for GET path; overridden in POST
    exam_types = SchoolTerm.objects.filter(school=school, active=True)
    grades = SchoolGrade.objects.filter(school=school, active=True).order_by("id")

    section_list = {}
    for session in edusession:
        s_id = str(session.id)
        section_list[s_id] = {}
        for grade in grades:
            sections = Section.objects.filter(grade=grade, session=session)
            grade_dict = {str(s.id): s.section for s in sections}
            section_list[s_id][str(grade.id)] = grade_dict

    section_list = json.dumps(section_list)

    try:
        branchuser = BranchUser.objects.get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )

    schoolbranch = SchoolBranch.objects.get(id=branchuser.school_id)
    grade_level = GradeLevel.objects.all()
    grades = SchoolGrade.objects.filter(school=schoolbranch).order_by("id")

    exam_types = SchoolTerm.objects.filter(school=branchuser.school, active=True)

    # term_list mapping for year-wise filtering
    term_dict = {}
    for term in exam_types:
        year_id = str(term.year.id)
        if year_id not in term_dict:
            term_dict[year_id] = []
        term_dict[year_id].append({
            'id': term.id,
            'name': f"{term.term_name.upper()} {term.year.year}"
        })
    term_list = json.dumps(term_dict)

    lr_qs = LiveResult.objects.filter(school=school)
    if lr_qs.exists():
        lr = lr_qs.first()
        live_result_status = lr.status
        live_calc_type = getattr(lr, "calculation_type", "legacy")
    else:
        live_result_status = False
        live_calc_type = "legacy"

    if request.method == "POST":
        term = request.POST.get("term")
        submitted_session = request.POST.get("edusession")
        grade = request.POST.get("grade2")
        pass_filter = request.POST.get("filter")
        print("SCHOOL", school, " GRADE: ", grade)
        this_grade = SchoolGrade.objects.get(id=grade)
        this_term = SchoolTerm.objects.get(id=term)

        print("TERM", this_term, " GRADE: ", this_grade)
        this_session = EduSession.objects.get(id=submitted_session)
        students = Student.objects.filter(school=school, grade=this_grade, status=True)
        subjects = Subject.objects.filter(
            branch=schoolbranch, grade=this_grade, status=True
        )
        additional_td = 13 - subjects.count()
        print("OOOOOOOOOOOOOOOOOOOOOOOOo", "SUBJECT COUNT", subjects.count())

        std_list = {}
        for student in students:
            std_list[student.reg_no] = {}
            std_list[student.reg_no]["name"] = student.name
            std_list[student.reg_no]["grade"] = student.grade
            std_list[student.reg_no]["section"] = student.section

            mo_dict = {}
            count = 1
            for subject in subjects:
                mo_dict[count] = {}
                mo_dict[count]["subject_name"] = subject.subject

                # Safe defaults in case marks are missing
                grade_th = ("N", 0, "")
                grade_pr = ("", 0, "")

                try:
                    this_marks = MarkObtained.objects.get(
                        student=int(student.reg_no),
                        session=this_session,
                        grade=this_grade.id,
                        term=this_term.id,
                        subject=subject.id,
                    )

                    gfm = GradeFullMarks.objects.get(
                        grade=this_grade.id, term=this_term.id, subject=subject.id,
                    )
                    the_fm = gfm.th_fm + gfm.pr_fm

                    if gfm.th_fm > 0:
                        if gfm.pr_fm > 0:
                            percent_th = (this_marks.th_mo * 100 / gfm.th_fm) if this_marks.th_mo > 0 else 0
                            percent_pr = (this_marks.pr_mo * 100 / gfm.pr_fm) if this_marks.pr_mo > 0 else 0
                            percent_total = (this_marks.th_mo + this_marks.pr_mo) * 100 / the_fm
                            grade_th = grading(percent_th)
                            grade_pr = grading(percent_pr)
                        else:
                            percent_th = (this_marks.th_mo * 100 / gfm.th_fm) if this_marks.th_mo > 0 else 0
                            percent_total = percent_th
                            grade_th = grading(percent_th)
                            grade_pr = ("", 0, "")

                    th_mo = this_marks.th_mo
                    pr_mo = this_marks.pr_mo
                except:
                    th_mo = 0
                    pr_mo = 0
                mo_dict[count]["theory_mo"] = grade_th[0]
                mo_dict[count]["prac_mo"] = grade_pr[0]
                mo_dict[count]["gradepoint"] = 3.2
                count += 1

            std_list[student.reg_no]["mo_dict"] = mo_dict

        context = {
            "std_list": std_list,
            "school": schoolbranch,
            "slogan": True,
            "term": this_term,
            "additional_td": additional_td,
        }
        return render(request, "panel/gradesheetall.html", context)

    if SchoolResultType.objects.filter(school=school, session=this_session).count() > 0:
        schoolresulttype = True
        sr = SchoolResultType.objects.get(school=school, session=this_session)
    else:
        schoolresulttype = False
        sr = ""

    if LiveResult.objects.filter(school=school).count() == 0:
        liveresult = False
        gradelist = ""
    else:
        liveresult = True
        lr = LiveResult.objects.get(school=school)
        lr_term = SchoolTerm.objects.get(id=lr.term)
        gradelist = json.loads(lr.grade_list)

    context = {
        "edusession": edusession,
        "current_session": current_session,
        "exam_types": exam_types,
        "section_list": section_list,
        "term_list": term_list,
        "school": school,
        "grade_level": grade_level,
        "grades": grades,
        "gradelist": gradelist,
        "branchuser": branchuser,
        "schoolresulttype": schoolresulttype,
        "sr": sr,
        "live_result_status": live_result_status,
        "live_calc_type": live_calc_type,
    }
    return render(request, "panel/marksgradesheet.html", context)


def disablestudent(request, regno=None):
    if regno == None:
        return redirect("/panel/")
    else:
        user = request.user
        branchuser = BranchUser.objects.get(user=user)
        reg_finder = Student.objects.filter(reg_no=regno)
        message = False
        if reg_finder.count() == 1:
            student = Student.objects.get(reg_no=regno)
            if branchuser.school == student.school:
                # avaiablesections = Section.objects.filter(grade=student.grade)
                if request.method == "POST":
                    print(request.POST)
                    # studentname = request.POST.get('studentname')
                    # rollno = request.POST.get('rollno')
                    status = int(request.POST.get("status"))
                    result = int(request.POST.get("result"))

                    print(status, result)

                    status = True if status == 1 else False
                    student.status = status
                    student.publish_result = result

                    print(student.status, student.publish_result)
                    try:
                        student.save()

                    except:
                        return HttpResponse(
                            'Sorry! something went wrong. Click <a href="/panel/">Here</a> to go the panel.'
                        )

                    success = True
                    student = Student.objects.get(reg_no=regno)
                    message = (
                            "Details of Student " + student.name + " has been updated."
                    )

                    context = {
                        "student": student,
                        "message": message,
                        "success": success,
                    }
                    return render(request, "panel/enabledisable_byreg_no.html", context)

                else:
                    context = {
                        "student": student,
                    }
                    return render(request, "panel/enabledisable_byreg_no.html", context)
            else:
                return HttpResponse(
                    'Sorry! something went wrong. You have no access to edit information of this Student. Click <a href="/panel/">Here</a> to go the panel.'
                )
        else:
            return HttpResponse(
                'Sorry! something went wrong. We could not find the Registration Number. Click <a href="/">Here</a> to go the homepage.'
            )


def printallstudents2020(request):
    students = Student.objects.filter(school=1).order_by("reg_no")
    dictstudent = {}
    count = 1
    for student in students:
        dictstudent[count] = dict()
        dictstudent[count]["reg_no"] = [student.reg_no]
        dictstudent[count]["name"] = student.name
        count += 1
    dictstudent = json.dumps(dictstudent)
    return HttpResponse(dictstudent)


@login_required
def importstudent(request):
    user = request.user
    gradelevel = 117
    section_id = 153

    all_students = [
        "Kristina Nepal",
        "Arisha Budathoki",
        "Aayusha Thandar",
        "Samikshya Majhi",
        "Kavya Pandeya",
        "Arisha Puri",
        "Siyona Basnet",
        "Dipak Rajbanshi",
        "Subarna Niraula",
        "Pranita Sharma",
        "Oman Luitel",
        "Sugam Dahal",
        "Saina Rajbanshi",
        "Aarav Rajbanshi",
        "Suman Koirala",
        "Samridha Misra",
        "Aarav Khawas",
        "Anupam Bista",
        "Subash Sardar",
        "Prashant Dahal",
        "Komal Poudel",
        "Barsha Koirala",
        "Ram kumar Kamat",
        "Sujita Risidev",
        "Dikshya Rajbanshi",
    ]
    student_count = 1
    for new_student in all_students:
        studentname = new_student
        rollno = student_count
        gender = 1

        grade = SchoolGrade.objects.get(id=gradelevel)
        userbranch = BranchUser.objects.get(user=user)
        section = Section.objects.get(id=section_id)

        new_reg_no = findNewRegNo(userbranch.school.id)
        pincode = randint(1000, 9999)

        student = Student()
        student.reg_no = new_reg_no
        student.pin_code = pincode
        student.roll_no = rollno
        student.name = studentname
        student.gender = 1
        student.grade = grade
        student.section = section
        student.school = userbranch.school
        print("going to save student")
        print(gradelevel, studentname, rollno, section)
        student.save()
        student_count += 1

        print(new_reg_no)
        # print('ADD STUDENT')
        # print(gradelevel, studentname, gender)#, username, gradelevel, userbranch.school.id, section)
        # print(userbranch.school)

        # BranchUser.objects.filter()

        # Subject.objects.get_or_create(branch=userbranch.school, grade=grade,subject=subject.upper())

        # Section.objects.get_or_create(grade=grade,section=sectionname.upper())
    return HttpResponse("STUDENTS ADDED SUCCESSFULLY")


@login_required
def subjectmanagement(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    schoolbranch = SchoolBranch.objects.get(id=branchuser.school_id)
    grades = SchoolGrade.objects.filter(school=schoolbranch, active=True).order_by("id")

    for grade in grades:
        subjects = Subject.objects.filter(branch=schoolbranch, grade=grade, status=True)
        print(grade, subjects)

    context = {"grades": grades}
    return render(request, "panel/subjectmanagement.html", context)


@login_required
def schoolprivate2077(request, regno):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    regno = regno

    if Student.objects.filter(reg_no=regno).count() == 1:
        student = Student.objects.get(reg_no=int(regno))

        if student.school != school:
            message = (
                    "Sorry you are not authorized to directly view the result of student from another school. Please fill the form to view the result of "
                    + student.name
                    + "."
            )
            context = {"message": message}
            return render(request, "panel/resultform.html", context)

        resultstatus = LiveResult.objects.get(school=branchuser.school)
        gradelist = json.loads(resultstatus.gradelist)
        term = resultstatus.term
        this_term = SchoolTerm.objects.get(id=term)
        if student.grade.id not in gradelist:
            message = (
                    "Sorry the result of Grade "
                    + student.grade.grade_name
                    + " has not been published yet. For more information please contact on School."
            )
            context = {"message": message}
            return render(request, "panel/resultform.html", context)
    else:
        context = {
            "message": "Sorry student with the registration number could not be found."
        }
        return render(request, "panel/resultform.html", context)

    slogan = " &nbsp; "
    if school.id <= 13:
        # Samata School
        slogan = "Education for all."
        logo = "https://cdn.hamro.com/simsnepal/logos/logo.jpg"
    elif school.id == 14:
        # CSA Montessori
        slogan = "Soaring to Excellence"
        logo = "https://cdn.hamro.com/simsnepal/logos/csa.jpg"
    elif school.id == 15:
        # Paramount Children Academy
        slogan = " &nbsp; "
    elif school.id >= 16 and school.id <= 17:
        # Samata School
        slogan = "Education for all."
        logo = "https://cdn.hamro.com/simsnepal/logos/paramount.png"

    # if request.method == 'POST':
    #     edusession = request.POST.get('edusession')
    #     term = request.POST.get('term')
    #     printtype = int(request.POST.get('printtype'))
    #     grade = request.POST.get('grade2', 0)
    #     section = request.POST.get('section2', 0)
    #     # printtype = request.POST.get('printtype', )  # 1 DETAIL 2 SUMMARIZED

    #     print('PRINTTYPE', printtype)

    # if grade == 0 or grade == None or grade == '':
    #     return HttpResponse('Sorry! something went wrong. Please take care while submitting data.')
    # else:
    #     this_grade = SchoolGrade.objects.get(id=grade)
    this_session = EduSession.objects.get(year=2077)
    this_term = SchoolTerm.objects.get(id=term)
    grade = student.grade
    this_grade = student.grade
    printtype = 2

    # subjectcount = Subject.objects.filter(branch=school, grade=this_grade, status=True).count()

    # if int(section) > 0:
    #     this_section = Section.objects.get(id=section)
    # else:
    #     this_section = False
    this_section = False
    calculated_rank = ""
    subjects = Subject.objects.filter(
        branch=school, grade=this_grade, status=True
    ).order_by("id")
    this_grade_subjects = Subject.objects.filter(
        branch=school, grade=this_grade, status=True
    ).order_by("id")
    subjectcount = ""
    for subject in subjects:
        subjectcount += "1"
    # if this_section == False:
    #     students = Student.objects.filter(school=school, grade=this_grade, status=True)
    #     calculated_rank = calculaterank(school.id, this_session, grade, term)
    # else:
    # students = Student.objects.filter(school=school, grade=this_grade, section=this_section, status=True)
    # calculated_rank = calculaterank(school.id, this_session, grade, term, this_section)
    # print(school.id, this_session, grade, term, this_section)
    # print('calculated rank ', calculated_rank)
    sn = 0
    data = {}

    sn += 1
    data[sn] = {}
    data[sn]["reg_no"] = student.reg_no
    data[sn]["name"] = student.name
    data[sn]["grade"] = student.grade
    data[sn]["section"] = student.section
    if student.reg_no in calculated_rank:
        data[sn]["rank"] = calculated_rank[student.reg_no]
    else:
        data[sn]["rank"] = "-"

    if printtype == 2:
        # sd = summarizedResult(school, term, grade, student.reg_no)
        sd = detailResult2078(school, term, grade, student.reg_no, printtype)
        data[sn]["mo_th"] = sd["mo_th"]
        data[sn]["mo_pr"] = sd["mo_pr"]
        data[sn]["total"] = sd["total"]
        data[sn]["gp"] = sd["gp"]
        data[sn]["remarks"] = sd["remarks"]
        # print(summarizedResult)
        # print('Summarized Result')
    else:
        sd = detailResult2078(school, term, grade, student.reg_no, printtype)
        data[sn]["mo_th"] = sd["mo_th"]
        data[sn]["mo_pr"] = sd["mo_pr"]
        data[sn]["total"] = sd["total"]
        data[sn]["gp"] = sd["gp"]
        data[sn]["subjects"] = sd["subjects"]
        data[sn]["remarks"] = sd["remarks"]

        # print(detailResult, subjectcount)
        # print('Detail Result')

    scount = 13 - subjects.count()
    subjectcount = range(scount)

    context = {
        "school": school,
        "term": this_term,
        "year": this_term.year,
        "data": data,
        "grade": this_grade,
        "section": this_section,
        "subjects": this_grade_subjects,
        "subjectcount": subjectcount,
        "std_list": data,
        "slogan": slogan,
        "logo": logo,
    }
    if printtype == 2:
        return render(request, "panel/gradesheetall_077.html", context)
    else:
        return render(request, "panel/gradesheetall_077.html", context)
    # else:
    #     return HttpResponseRedirect('/panel/')


@login_required()
def add_guardian(request):
    user = User.objects.get(id=request.user.id)
    message = ""
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")

        try:
            obj, created = User.objects.get_or_create(username=username)
            if created:
                obj.password = make_password(password)
                obj.first_name = first_name
                obj.last_name = last_name
                # if email != 'default@hamro.com':
                obj.email = email
                obj.save()

                obj = User.objects.get(username=username)

                cu = CreatedUsers()
                cu.added_by = user
                cu.guardian = obj
                cu.save()
                message = "Guardian Login Account Created Successfully. "
            else:
                message = "Guardian Login Account Already Exists. "
        except Exception as e:
            message = "Sorry something went wrong. Please Contact Hamro Support. REF: " + str(e)
    else:
        print("GET")
    context = {'message': message}
    return render(request, "panel/add_guardian.html", context)


def print_parents(request):
    user = request.user
    try:
        branch_user = BranchUser.objects.get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )
    grade_level = GradeLevel.objects.all()
    school_branch = SchoolBranch.objects.get(id=branch_user.school_id)
    grades = SchoolGrade.objects.filter(school=school_branch).order_by("id")
    parents = CreatedUsers.objects.filter(added_by=request.user)

    for parent in parents:
        print(parent)

    context = {'parents': parents, 'branch_user': branch_user, 'grade_level': grade_level, 'grades': grades,
               'school_branch': school_branch, 'school': school_branch}
    return render(request, "panel/print_guardians.html", context)


def edit_parent(request, pid):
    message = change_message = False
    user = request.user
    try:
        branch_user = BranchUser.objects.get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )
    if request.method == 'POST':
        username = request.POST.get("username")
        email = request.POST.get("email")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        action = request.POST.get("action")
        required_parent = User.objects.get(id=pid)
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if action == 'edit_information':
            required_parent.username = username
            required_parent.email = email
            required_parent.first_name = first_name
            required_parent.last_name = last_name

            try:
                required_parent.save()
                message = "Gurdian Information Updated Successfully"
            except Exception as e:
                message = "Unable to update Gurdian Information. REF: "+ e

        elif action == 'change_password':
            if password == confirm_password:
                required_parent.password = make_password(password)

                try:
                    required_parent.save()
                    change_message = "Gurdian Password Updated Successfully"
                except Exception as e:
                    change_message = "Unable to update Gurdian Password. REF: "+ e
            else:
                change_message = "Password Doensnot Match, Please try again"
    grade_level = GradeLevel.objects.all()
    school_branch = SchoolBranch.objects.get(id=branch_user.school_id)
    grades = SchoolGrade.objects.filter(school=school_branch).order_by("id")

    if User.objects.filter(id=pid).count() == 1:
        parent_user = User.objects.get(id=pid)
        parent = CreatedUsers.objects.get(guardian=parent_user)
    else:
        parent = False

    context = {'message': message, 'change_message': change_message, 'parent': parent, 'branch_user': branch_user, 'grade_level': grade_level, 'grades': grades,
               'school_branch': school_branch, "school": school_branch,}
    return render(request, "panel/edit_guardian.html", context)


def print_teachers(request):
    user = request.user
    try:
        branch_user = BranchUser.objects.get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )
    grade_level = GradeLevel.objects.all()
    school_branch = SchoolBranch.objects.get(id=branch_user.school_id)
    grades = SchoolGrade.objects.filter(school=school_branch).order_by("id")
    teachers = Teacher.objects.filter(added_by=request.user).select_related('teacher', 'teacher__hamro_profile')

    subject_access = dict()

    for teacher in teachers:
        subject_access[teacher.id] = dict()

       # teacher_subject_access = TeacherSubjectAccess.objects.filter(session=this_session, teacher=teacher.teacher)
       # for tsa in teacher_subject_access:
       #     if teacher_subject_access.grade.school == school_branch.id:
       #         subject_access[teacher.id][tsa.id] = tsa

    context = {'teachers': teachers, 'branch_user': branch_user, 'grade_level': grade_level, 'grades': grades,
               'school_branch': school_branch, 'school': school_branch, "subject_access": subject_access}
    return render(request, "panel/print_teachers.html", context)


def edit_teacher(request, tid):
    message = change_message = False
    user = request.user
    try:
        branch_user = BranchUser.objects.get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )
    if request.method == 'POST':
        username = request.POST.get("username")
        email = request.POST.get("email")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        action = request.POST.get("action")
        required_teacher = User.objects.get(id=tid)
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if action == 'edit_information':
            required_teacher.username = username
            required_teacher.email = email
            required_teacher.first_name = first_name
            required_teacher.last_name = last_name

            try:
                required_teacher.save()
                message = "Teacher Information Updated Successfully"
            except Exception as e:
                message = "Unable to update Teacher Information. REF: "+ e

        elif action == 'change_password':
            if password == confirm_password:
                required_teacher.password = make_password(password)

                try:
                    required_teacher.save()
                    change_message = "Teacher Password Updated Successfully"
                except Exception as e:
                    change_message = "Unable to update Teacher Password. REF: "+ e
            else:
                change_message = "Password Doensnot Match, Please try again"
    grade_level = GradeLevel.objects.all()
    school_branch = SchoolBranch.objects.get(id=branch_user.school_id)
    grades = SchoolGrade.objects.filter(school=school_branch).order_by("id")

    if User.objects.filter(id=tid).count() == 1:
        teacher_user = User.objects.get(id=tid)
        teacher = Teacher.objects.get(teacher=teacher_user)
    else:
        parent = False

    context = {'message': message, 'change_message': change_message, 'teacher': teacher, 'branch_user': branch_user, 'grade_level': grade_level, 'grades': grades,
               'school_branch': school_branch, "school": school_branch,}
    return render(request, "panel/edit_teacher.html", context)

# def change_parent_password(request, pid):
#     if request.method == 'POST':
#         password = request.POST.get("password")
#         confirm_password = request.POST.get("confirm_password")
#
#         if password == confirm_password:
#             parent_user = User.objects.get(id=pid)
#             parent_user.password = make_password(password)
#             parent_user.save()
#
#             message =
#
#
#     url = "/panel/edit/parent/" + pid + "/"
#     return redirect(url)


def guardian(request):
    return HttpResponse('Hi')


# @login_required()
# def add_teacher(request):
#     import requests
#     import secrets
#     from django.conf import settings
#     user = User.objects.get(id=request.user.id)
#     message = ""
#     found_user = None
#     search_query = request.GET.get("search_phone", "").strip()

#     if search_query:
#         api_key = getattr(settings, 'HAMRO_BUSINESS_API_KEY', 'hamro_sys_key_789')
#         headers = {
#             'X-System-API-Key': api_key,
#             'Content-Type': 'application/json',
#             'Accept': 'application/json'
#         }
#         payload = {
#             'contacts': [search_query]
#         }
#         api_base_url = getattr(settings, 'HAMRO_API_BASE_URL', 'https://serverin.hamro.com').rstrip('/')
#         try:
#             # Query the user from the Hamro Ecosystem API via POST request
#             resp = requests.post(
#                 f'{api_base_url}/api/v1/system/contacts/find',
#                 json=payload,
#                 headers=headers,
#                 timeout=5,
#                 verify=False
#             )
#             print(resp)
#             print(resp.json())
#             if resp.status_code == 200:
#                 data = resp.json()
#                 print(data)
#                 results = data.get('data', [])
#                 if results and len(results) > 0:
#                     first_result = results[0]
#                     if first_result.get('found'):
#                         user_data = first_result.get('user', {})
#                         if user_data:
#                             # Map user_data according to the new API schema
#                             # Split name into first and last name
#                             name_parts = user_data.get('name', '').strip().split(' ', 1)
#                             first_name = name_parts[0] if name_parts else ''
#                             last_name = name_parts[1] if len(name_parts) > 1 else ''
                            
#                             found_user = {
#                                 "username": user_data.get('username', ''),
#                                 "hamro_uuid": user_data.get('id', ''),
#                                 "avatar_url": user_data.get('avatar_url', ''),
#                                 "first_name": first_name,
#                                 "last_name": last_name,
#                                 "email": user_data.get('email', ''),
#                                 "phone": user_data.get('mobile_number', '')
#                             }
#                         else:
#                             message = "User data missing from response."
#                     else:
#                         message = "User not found in Hamro Ecosystem."
#                 else:
#                     message = "Invalid response format received from Ecosystem."
#             else:
#                 # Fallback to local mock for offline development testing ONLY for specific test accounts
#                 if search_query in ["9876543210", "teacher@example.com", "iostest@hamro.com", "iostest"]:
#                     if search_query in ["iostest@hamro.com", "iostest"]:
#                         found_user = {
#                             "username": "iostest@hamro.com",
#                             "first_name": "IOS",
#                             "last_name": "Test",
#                             "email": "iostest@hamro.com",
#                             "phone": "9801234568"
#                         }
#                     else:
#                         found_user = {
#                             "username": "9876543210" if "@" not in search_query else search_query.split("@")[0],
#                             "first_name": "Hari",
#                             "last_name": "Bahadur",
#                             "email": search_query if "@" in search_query else f"hari_{search_query}@hamro.com",
#                             "phone": search_query if "@" not in search_query else "9876543210"
#                         }
#                 else:
#                     message = f"User with identifier '{search_query}' not found."
#         except Exception as e:
#             # Fallback to local mock for offline development testing ONLY for specific test accounts
#             if search_query in ["9876543210", "teacher@example.com", "iostest@hamro.com", "iostest"]:
#                 if search_query in ["iostest@hamro.com", "iostest"]:
#                     found_user = {
#                         "username": "iostest@hamro.com",
#                         "first_name": "IOS",
#                         "last_name": "Test",
#                         "email": "iostest@hamro.com",
#                         "phone": "9801234568"
#                     }
#                 else:
#                     found_user = {
#                         "username": "9876543210" if "@" not in search_query else search_query.split("@")[0],
#                         "first_name": "Hari",
#                         "last_name": "Bahadur",
#                         "email": search_query if "@" in search_query else f"hari_{search_query}@hamro.com",
#                         "phone": search_query if "@" not in search_query else "9876543210"
#                     }
#             else:
#                 message = f"Ecosystem connection failed: {str(e)}"

#     if request.method == "POST":
#         action = request.POST.get("action")
#         if action == "add_sso_teacher":
#             username = request.POST.get("username")
#             email = request.POST.get("email")
#             first_name = request.POST.get("first_name")
#             last_name = request.POST.get("last_name")
#             hamro_uuid = request.POST.get("hamro_uuid")
#             avatar_url = request.POST.get("avatar_url")
#             mobile_number = request.POST.get("mobile_number")
            
#             # SSO User password can be randomized since login is via SSO
#             rand_pwd = secrets.token_urlsafe(16)
#             try:
#                 obj, created = User.objects.get_or_create(username=username, defaults={
#                     "email": email,
#                     "first_name": first_name,
#                     "last_name": last_name,
#                     "password": make_password(rand_pwd)
#                 })
                
#                 if hamro_uuid:
#                     from sso.models import HamroUserProfile
#                     HamroUserProfile.objects.update_or_create(
#                         user=obj,
#                         defaults={
#                             'hamro_uuid': hamro_uuid,
#                             'avatar_url': avatar_url,
#                             'mobile_number': mobile_number
#                         }
#                     )
                
#                 teacher, t_created = Teacher.objects.get_or_create(teacher=obj, defaults={"added_by": user})
                
#                 # Associate the teacher with the admin's current school branch via BranchUser
#                 admin_branch = BranchUser.objects.filter(user=user, status=True).first()
#                 if admin_branch:
#                     BranchUser.objects.get_or_create(
#                         school=admin_branch.school,
#                         user=obj,
#                         defaults={
#                             "admin_status": False,
#                             "status": True,
#                             "added_by": admin_branch.added_by
#                         }
#                     )
#                     # Automatically assign subjects for mock teachers for testing convenience
#                     if username in ["iostest@hamro.com", "teacher", "9876543210"]:
#                         current_session = get_current_session()
#                         if current_session:
#                             subjects = Subject.objects.filter(branch=admin_branch.school, session=current_session)
#                             for sub in subjects:
#                                 TeacherSubjectAccess.objects.get_or_create(
#                                     session=current_session,
#                                     teacher=obj,
#                                     grade=sub.grade,
#                                     section=sub.section,
#                                     subject=sub,
#                                     defaults={"status": True}
#                                 )
                
#                 if t_created:
#                     message = f"Teacher '{first_name} {last_name}' registered successfully from Hamro Ecosystem."
#                 else:
#                     message = f"Teacher '{first_name} {last_name}' is already registered as a teacher."
#             except Exception as e:
#                 message = "Error registering teacher: " + str(e)

#         elif action == "create_manual":
#             username = request.POST.get("username")
#             email = request.POST.get("email")
#             first_name = request.POST.get("first_name")
#             last_name = request.POST.get("last_name")

#             try:
#                 # No manual password needed as teachers authenticate strictly using SSO
#                 rand_pwd = secrets.token_urlsafe(16)
#                 obj, created = User.objects.get_or_create(username=username, defaults={
#                     "email": email,
#                     "first_name": first_name,
#                     "last_name": last_name,
#                     "password": make_password(rand_pwd)
#                 })
#                 if created:
#                     teacher = Teacher()
#                     teacher.added_by = user
#                     teacher.teacher = obj
#                     teacher.save()
                    
#                     # Associate the teacher with the admin's current school branch via BranchUser
#                     admin_branch = BranchUser.objects.filter(user=user, status=True).first()
#                     if admin_branch:
#                         BranchUser.objects.get_or_create(
#                             school=admin_branch.school,
#                             user=obj,
#                             defaults={
#                                 "admin_status": False,
#                                 "status": True,
#                                 "added_by": admin_branch.added_by
#                             }
#                         )
#                         # Automatically assign subjects for mock teachers for testing convenience
#                         if username in ["iostest@hamro.com", "teacher", "9876543210"]:
#                             current_session = get_current_session()
#                             if current_session:
#                                 subjects = Subject.objects.filter(branch=admin_branch.school, session=current_session)
#                                 for sub in subjects:
#                                     TeacherSubjectAccess.objects.get_or_create(
#                                         session=current_session,
#                                         teacher=obj,
#                                         grade=sub.grade,
#                                         section=sub.section,
#                                         subject=sub,
#                                         defaults={"status": True}
#                                     )
                    
#                     message = f"Teacher Login Account for '{first_name} {last_name}' Created Successfully."
#                 else:
#                     message = "Teacher Login Account Already Exists."
#             except Exception as e:
#                 message = "Sorry something went wrong. Please Contact Hamro Support. REF: " + str(e)
                
#     context = {
#         'message': message,
#         'found_user': found_user,
#         'search_phone': search_query
#     }
#     return render(request, "panel/add_teacher.html", context)


@login_required()
def add_teacher(request):
    user = request.user
    message = ""
    found_user = None
    search_query = request.GET.get("search_phone", "").strip()

    # ------------------- SEARCH (REAL API ONLY) -------------------
    if search_query:
        api_key = getattr(settings, 'HAMRO_SYSTEM_API_KEY', None)
        if not api_key:
            message = "System misconfiguration: Missing API key. Contact support."
        else:
            headers = {
                'X-System-API-Key': api_key,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            payload = {'contacts': [search_query]}
            api_base_url = getattr(settings, 'HAMRO_API_BASE_URL', 'https://messengerin.hamro.com').rstrip('/')
            
            try:
                resp = requests.post(
                    f'{api_base_url}/api/v1/system/contacts/find',
                    json=payload,
                    headers=headers,
                    timeout=5,
                    verify=True   # Use proper SSL verification in production
                )

                print(resp)
                print(resp.json)
                
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get('data', [])
                    if results and len(results) > 0:
                        first_result = results[0]
                        if first_result.get('found'):
                            user_data = first_result.get('user', {})
                            if user_data:
                                name_parts = user_data.get('name', '').strip().split(' ', 1)
                                first_name = name_parts[0] if name_parts else ''
                                last_name = name_parts[1] if len(name_parts) > 1 else ''
                                
                                is_already_registered = False
                                existing_user = User.objects.filter(username=user_data.get('username', '')).first()
                                if existing_user:
                                    admin_branch = BranchUser.objects.filter(user=request.user, status=True).first()
                                    if admin_branch and BranchUser.objects.filter(user=existing_user, school=admin_branch.school).exists():
                                        is_already_registered = True

                                found_user = {
                                    "username": user_data.get('username', ''),
                                    "hamro_uuid": user_data.get('id', ''),
                                    "avatar_url": user_data.get('avatar_url', ''),
                                    "first_name": first_name,
                                    "last_name": last_name,
                                    "email": user_data.get('email', ''),
                                    "phone": user_data.get('mobile_number', ''),
                                    "is_already_registered": is_already_registered
                                }
                            else:
                                message = "User data missing from Ecosystem response."
                        else:
                            message = "User not found in Hamro Ecosystem."
                    else:
                        message = "Invalid response format from Ecosystem."
                else:
                    logger.error(f"Ecosystem API error {resp.status_code}: {resp.text}")
                    message = f"Ecosystem service error (HTTP {resp.status_code}). Please try again later."
                    
            except requests.exceptions.Timeout:
                logger.error("Timeout connecting to Hamro Ecosystem API")
                message = "Ecosystem service timeout. Please try again."
            except requests.exceptions.ConnectionError:
                logger.error("Connection error to Hamro Ecosystem API")
                message = "Cannot reach Ecosystem service. Check your network."
            except Exception as e:
                logger.exception("Unexpected error during Ecosystem lookup")
                message = f"Technical error: {str(e)}"

    # ------------------- FORM HANDLING (ADD TEACHER) -------------------
    if request.method == "POST":
        action = request.POST.get("action")
        
        if action == "add_sso_teacher":
            username = request.POST.get("username")
            email = request.POST.get("email")
            first_name = request.POST.get("first_name")
            last_name = request.POST.get("last_name")
            hamro_uuid = request.POST.get("hamro_uuid")
            avatar_url = request.POST.get("avatar_url")
            mobile_number = request.POST.get("mobile_number")
            
            rand_pwd = secrets.token_urlsafe(16)
            try:
                obj, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "email": email,
                        "first_name": first_name,
                        "last_name": last_name,
                        "password": make_password(rand_pwd)
                    }
                )
                
                if hamro_uuid:
                    HamroUserProfile.objects.update_or_create(
                        user=obj,
                        defaults={
                            'hamro_uuid': hamro_uuid,
                            'avatar_url': avatar_url,
                            'mobile_number': mobile_number
                        }
                    )
                
                teacher, t_created = Teacher.objects.get_or_create(
                    teacher=obj,
                    defaults={"added_by": user}
                )
                
                admin_branch = BranchUser.objects.filter(user=user, status=True).first()
                if admin_branch:
                    BranchUser.objects.get_or_create(
                        school=admin_branch.school,
                        user=obj,
                        defaults={
                            "admin_status": False,
                            "status": True,
                            "added_by": admin_branch.added_by
                        }
                    )
                    # Optional: auto-assign subjects only in development (remove for production)
                    if settings.DEBUG and username in ["iostest@hamro.com", "teacher", "9876543210"]:
                        current_session = get_current_session()
                        if current_session:
                            subjects = Subject.objects.filter(branch=admin_branch.school, session=current_session)
                            for sub in subjects:
                                TeacherSubjectAccess.objects.get_or_create(
                                    session=current_session,
                                    teacher=obj,
                                    grade=sub.grade,
                                    section=sub.section,
                                    subject=sub,
                                    defaults={"status": True}
                                )
                
                if t_created:
                    message = f"Teacher '{first_name} {last_name}' registered successfully from Hamro Ecosystem."
                else:
                    message = f"Teacher '{first_name} {last_name}' is already registered."
                    
            except Exception as e:
                logger.exception("Teacher creation failed")
                message = f"Error registering teacher: {str(e)}"
        
        elif action == "create_manual":
            username = request.POST.get("username")
            email = request.POST.get("email")
            first_name = request.POST.get("first_name")
            last_name = request.POST.get("last_name")
            
            rand_pwd = secrets.token_urlsafe(16)
            try:
                obj, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "email": email,
                        "first_name": first_name,
                        "last_name": last_name,
                        "password": make_password(rand_pwd)
                    }
                )
                if created:
                    teacher = Teacher(added_by=user, teacher=obj)
                    teacher.save()
                    
                    admin_branch = BranchUser.objects.filter(user=user, status=True).first()
                    if admin_branch:
                        BranchUser.objects.get_or_create(
                            school=admin_branch.school,
                            user=obj,
                            defaults={
                                "admin_status": False,
                                "status": True,
                                "added_by": admin_branch.added_by
                            }
                        )
                        if settings.DEBUG and username in ["iostest@hamro.com", "teacher", "9876543210"]:
                            current_session = get_current_session()
                            if current_session:
                                subjects = Subject.objects.filter(branch=admin_branch.school, session=current_session)
                                for sub in subjects:
                                    TeacherSubjectAccess.objects.get_or_create(
                                        session=current_session,
                                        teacher=obj,
                                        grade=sub.grade,
                                        section=sub.section,
                                        subject=sub,
                                        defaults={"status": True}
                                    )
                    
                    message = f"Teacher account for '{first_name} {last_name}' created successfully."
                else:
                    message = "Teacher login account already exists."
            except Exception as e:
                logger.exception("Manual teacher creation failed")
                message = f"Sorry, something went wrong. Reference: {str(e)}"

    context = {
        'message': message,
        'found_user': found_user,
        'search_phone': search_query
    }
    return render(request, "panel/add_teacher.html", context)


@login_required
def addsection(request):
    this_session = get_current_session()
    if request.method == 'POST':
        gradelevel = request.POST.get('gradelevel')
        redurl = request.POST.get('redurl')
        sectionname = request.POST.get('sectionname')
        # Retrieve grade object
        try:
            grade = SchoolGrade.objects.get(id=gradelevel)
        except (ValueError, SchoolGrade.DoesNotExist):
            return HttpResponse("Grade not found.")
        # Get branch user info
        branchuser, err = get_branch_info(request.user)
        if err:
            return HttpResponse(err)
        # Security check: ensure grade belongs to user's school
        resp = ensure_branch_user(request, grade)
        if resp:
            return resp
        # Create or get Section with required fields (ensure school_id is set)
        Section.objects.get_or_create(
            session=this_session,
            school_id=branchuser.school.id,
            grade=grade,
            section=sectionname.upper()
        )
        # Redirect back to the referring page (preserve query parameters)
        if redurl:
            return HttpResponseRedirect(redurl)
        else:
            return HttpResponseRedirect(f"/panel/grades/{grade.id}/?add=section")
    else:
        return HttpResponse('Sorry! Something went wrong. Click <a href="/">Here</a> to go the homepage.')



@login_required
def addsubject(request):
    this_session = get_current_session()
    user = request.user
    if request.method == 'POST':
        gradelevel = request.POST.get('gradelevel')
        redurl = request.POST.get('redurl')
        subject_master_id = request.POST.get('subject_master')
        section_id = request.POST.get('section')
        internal_name = request.POST.get('subjectname', '').strip()

        try:
            grade = SchoolGrade.objects.get(id=gradelevel)
        except (ValueError, SchoolGrade.DoesNotExist):
            return HttpResponse("Grade not found.")

        try:
            userbranch = BranchUser.objects.get(user=user)
        except BranchUser.DoesNotExist:
            return HttpResponse("Branch user not found.")

        try:
            sm = SubjectMaster.objects.get(id=subject_master_id)
        except (ValueError, TypeError, SubjectMaster.DoesNotExist):
            messages.error(request, "Invalid Standard Subject selected.")
            return HttpResponseRedirect(redurl)

        # Fallback to canonical name if custom internal name is empty
        if not internal_name:
            internal_name = sm.canonical_name

        # Resolve section if provided
        section = None
        if section_id:
            try:
                section = Section.objects.get(id=section_id)
            except (ValueError, TypeError, Section.DoesNotExist):
                pass

        subject_upper = internal_name.strip().upper()

        # Check unique constraint: (session, branch, grade, section, subject)
        if Subject.objects.filter(
            session=this_session,
            branch=userbranch.school,
            grade=grade,
            section=section,
            subject=subject_upper
        ).exists():
            messages.error(request, f"Subject '{subject_upper}' is already assigned to this grade/section in the current session.")
        else:
            Subject.objects.create(
                session=this_session,
                branch=userbranch.school,
                grade=grade,
                section=section,
                subject_master=sm,
                subject=subject_upper
            )
            messages.success(request, f"Subject '{subject_upper}' added successfully.")

        return HttpResponseRedirect(redurl)

    else:
        return HttpResponse('Sorry! Something went wrong. Click <a href="/">Here</a> to go the homepage.')


def edsubject(request):
    this_session = get_current_session()
    user = request.user
    if request.method == 'POST':
        redurl = request.POST.get('redurl')
        gradelevel = request.POST.get('gradelevel')
        edsubjectid = request.POST.get('edsubjectid')

        schoolgrade = SchoolGrade.objects.get(id=gradelevel)
        try:
            branchuser = BranchUser.objects.get(user=user)
        except BranchUser.DoesNotExist:
            return HttpResponse(
                'Sorry! You are not allowed to access this page. Click <a href="/panel/">Here</a> to go the Panel.')

        if schoolgrade.school == branchuser.school:
            subject = Subject.objects.get(id=edsubjectid, session=this_session)
            if subject.status == 1:
                subject.status = 0
            else:
                subject.status = 1
            subject.save()
            return redirect(redurl)
        else:
            return HttpResponse(
                'Sorry! You are not allowed to access this page. Click <a href="/panel/">Here</a> to go the Panel.')

        print(gradelevel, gradelevel, edsubjectid)
        return HttpResponse('Hi')
    else:
        return HttpResponse('Sorry! Something went wrong. Click <a href="/panel/">Here</a> to go the homepage.')


def hwsubject(request):
    this_session = get_current_session()
    user = request.user
    if request.method == 'POST':
        redurl = request.POST.get('redurl')
        gradelevel = request.POST.get('gradelevel')
        hwsubjectid = request.POST.get('hwsubjectid')

        schoolgrade = SchoolGrade.objects.get(id=gradelevel)
        try:
            branchuser = BranchUser.objects.get(user=user)
        except BranchUser.DoesNotExist:
            return HttpResponse(
                'Sorry! You are not allowed to access this page. Click <a href="/panel/">Here</a> to go the Panel.')

        if schoolgrade.school == branchuser.school:
            subject = Subject.objects.get(id=hwsubjectid, session=this_session)
            if subject.heavy_weight == 1:
                subject.heavy_weight = 0
            else:
                subject.heavy_weight = 1
            subject.save()
            return redirect(redurl)
        else:
            return HttpResponse(
                'Sorry! You are not allowed to access this page. Click <a href="/panel/">Here</a> to go the Panel.')

        print(gradelevel, gradelevel, edsubjectid)
        return HttpResponse('Hi')
    else:
        return HttpResponse('Sorry! Something went wrong. Click <a href="/panel/">Here</a> to go the homepage.')


@login_required
def add_student_by_reg(request):
    this_session = get_current_session()
    user = request.user
    if request.method == 'POST':
        gradelevel = request.POST.get('gradelevel')
        redurl = request.POST.get('redurl')

        # gradelevel = SchoolGrade.objects.get(id=gradelevel)
        regno = request.POST.get('regno')
        rollno = request.POST.get('rollno', 1)
        section = request.POST.get('section')
        
        grade = SchoolGrade.objects.get(id=gradelevel)
        userbranch = BranchUser.objects.get(user=user)
        section = Section.objects.get(id=section)
        school = userbranch.school

        try:
            student = Student.objects.get(reg_no= regno)
        except:
            return HttpResponseRedirect(redurl)
        
        if StudentSession.objects.filter(session=this_session, student=student).count() == 0:
            student_session = StudentSession()
            student_session.session = this_session
            student_session.student = student
            student_session.grade = grade
            student_session.section = section
            student_session.roll_no = rollno

            student_session.save()
        else:
            if StudentSession.objects.filter(session=this_session, student=student, status=True).count() == 0:
                if StudentSession.objects.filter(session=this_session, student=student, grade=grade).count() == 1:
                    student_session = StudentSession.objects.get(session=this_session, student=student, grade=grade)
                    student_session.section = section
                    student_session.roll_no = rollno
                    student_session.status = True
                    student_session.save()
                    
            else:
                student_session = StudentSession.objects.get(session=this_session, student=student, status=True)
                student_session.status = False
                student_session.save()

                student_session = StudentSession()
                student_session.session = this_session
                student_session.student = student
                student_session.grade = grade
                student_session.section = section
                student_session.roll_no = rollno

                student_session.save()

        for key, value in request.POST.items():
            print('Key: %s' % (key))
            # print(f'Key: {key}') in Python >= 3.7
            print('Value %s' % (value))
            # print(f'Value: {value}') in Python >= 3.7

        return HttpResponseRedirect(redurl)

    else:
        return HttpResponse('Sorry! Something went wrong. Click <a href="/">Here</a> to go the homepage.')

@login_required()
def printentrancecard(request):
    user = request.user
    if user.id != 16:
        width = 55
        logo = "https://cdn.hamro.com/simsnepal/logos/samata_logo_black.png"
    else:
        width = 55
        logo = "http://school3.nep.onl/wp-content/uploads/sites/8/2019/12/51150449_1650894705012798_8214025074135531520_n.png"
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)

    print(school)
    grade_section = list()

    # school_grade = SchoolGrade.objects.filter(school=school, session=this_session.id, active=True).order_by('grade_weight')
    # print(school_grade.count())
    # if school_grade.count() > 0:
    #     for sg in school_grade:
    #         student_in_session = StudentSession.objects.filter(session=this_session, grade=sg, status=True).order_by('section', 'roll_no')
    #         print('students')
    #         print(student_in_session)
    #         school_section = Section.objects.filter(session=this_session, grade=sg).order_by('id')
    #         if school_section.count() > 0:
    #             for sc in school_section:
    #                 grade_section.append(sc.id)

    # print('Printing Grade Section')
    # # print(school_grade)
    # # print(grade_section)
    students = {}
    count = 0
    # for gs in grade_section:
    #     print(gs)

    current_session = get_current_session()
    if request.method == 'POST':
        term = request.POST.get('term')
        whattype = request.POST.get('whattype')

        std_reg = OrderedDict()
        school_grade = SchoolGrade.objects.filter(school=school, active=True).order_by(
            'grade_weight')
        if school_grade.count() > 0:
            for sg in school_grade:
                if StudentSession.objects.filter(session=current_session, grade=sg, status=True).count() > 0:
                    student_in_session = StudentSession.objects.filter(session=current_session, grade=sg, status=True)\
                        .order_by('section', 'roll_no', 'student')
                    for sis in student_in_session:
                        count += 1
                        std_reg[sis.student.reg_no] = {}
                        std_reg[sis.student.reg_no]['reg_no'] = sis.student.reg_no
                        std_reg[sis.student.reg_no]['name'] = sis.student.name
                        std_reg[sis.student.reg_no]['grade'] = sis.grade.grade_name
                        std_reg[sis.student.reg_no]['section'] = sis.section
                        std_reg[sis.student.reg_no]['roll_no'] = sis.roll_no

        term_exam = SchoolTerm.objects.get(id=term)

        if whattype == 'detail':
            context = {'school': school, 'students': students, 'count': count, 'term_exam': term_exam,
                       'year': current_session.year, 'logo': logo, 'width': width, 'blankcount': '12345678', 'std_reg': std_reg}

            if school.id in exam_board:
            	return render(request, 'panel/entrancecard_dict_exam_board.html', context)
            else:
            	return render(request, 'panel/entrancecard_dict.html', context)
        elif whattype == 'blank':
            context = {'school': school, 'term_exam': term_exam, 'year': current_session.year,
                       'logo': logo, 'width': width, 'blankcount': '12345678', 'std_reg': std_reg}
            if school.id in exam_board:
            	return render(request, 'panel/entrancecardblank_exam_board.html', context)
            else:
            	return render(request, 'panel/entrancecardblank.html', context)

        else:
            context = {'school': school, 'students': students, 'count': count, 'term_exam': term_exam,
                       'year': current_session.year, 'logo': logo, 'width': width, 'blankcount': '12345678', 'std_reg': std_reg}

            if school.id in exam_board:
            	return render(request, 'panel/entrancecard_dict_exam_board.html', context)
            else:
            	return render(request, 'panel/entrancecard_dict_with_image.html', context)

    exam_types = SchoolTerm.objects.filter(school=branchuser.school, year=current_session)
    grades = SchoolGrade.objects.filter(school=branchuser.school, session=current_session)

    context = {'grades': grades, 'school': school, 'exam_types': exam_types}
    return render(request, 'panel/entrancecardbase.html', context)
    #pdf = render_to_pdf('panel/entrancecardbase.html', context)
    #return HttpResponse(pdf, content_type='application/pdf')
    

def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html  = template.render(context_dict)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("ISO-8859-1")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return None

@login_required
def edit_student(request, regno):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    reg_finder = Student.objects.filter(reg_no=regno)
    message = False
    if reg_finder.count() == 1:
        student = Student.objects.get(reg_no=regno)
        if branchuser.school == student.school:
            # avaiablesections = Section.objects.filter(grade=student.grade)
            if request.method == 'POST':
                studentname = request.POST.get('studentname')
                rollno = request.POST.get('rollno')
                gender = request.POST.get('gender')

                dateofbirth = request.POST.get('dateofbirth', '')

                tempaddr = request.POST.get('tempaddr', '')
                peraddr = request.POST.get('peraddr', '')

                fathersname = request.POST.get('fathersname', '')
                fathersphone = request.POST.get('fathersphone', None)
                fathersemail = request.POST.get('fathersemail', None)

                mothersname = request.POST.get('mothersname', '')
                mothersphone = request.POST.get('mothersphone', None)
                mothersemail = request.POST.get('mothersemail', None)

                gurdainsname = request.POST.get('guardiansname', '')
                gurdainsphone = request.POST.get('guardiansphone', None)
                gurdainsemail = request.POST.get('guardiansemail', None)

                student.name = studentname
                student.gender = gender

                student.dob = dateofbirth  # datetime.strptime(dateofbirth, '%y/%m/%d')
                student.temporary_address = tempaddr
                student.permanent_address = peraddr
                # student.grade = grade
                # student.section = section
                student.fathers_name = fathersname
                try:
                    fathersphone = int(fathersphone)
                    student.fathers_phone = fathersphone
                except:
                    fathersphone = None
                    student.fathers_phone = fathersphone

                student.fathers_email = fathersemail

                student.mothers_name = mothersname
                student.mothers_email = mothersemail
                try:
                    mothersphone = int(mothersphone)
                    student.mothers_phone = mothersphone
                except:
                    mothersphone = None
                    student.mothers_phone = mothersphone

                student.guardian_name = gurdainsname
                try:
                    gurdainsphone = int(gurdainsphone)
                    student.guardian_phone = gurdainsphone
                except:
                    gurdainsphone = None
                    student.guardian_phone = gurdainsphone

                student.guardian_email = gurdainsemail

                print("going to save student")
                try:
                    student.save()
                except Exception as err:
                    mes = 'Sorry! something went wrong. Click <a href="/panel/">Here</a> to go the panel.'+ err
                    return HttpResponse(mes)

                success = True
                student = Student.objects.get(reg_no=regno)
                message = 'Details of Student ' + student.name + ' has been updated.'

                context = {'student': student, 'message': message, 'success': success}
                return render(request, 'panel/editstudent_byreg_no.html', context)

            else:
                context = {'student': student}
                return render(request, 'panel/editstudent_byreg_no.html', context)
        else:
            return HttpResponse(
                'Sorry! something went wrong. You have no access to edit information of this Student. Click <a href="/panel/">Here</a> to go the panel.')
    else:
        return HttpResponse(
            'Sorry! something went wrong. We could not find the Registration Number. Click <a href="/">Here</a> to go the homepage.')


@login_required()
def flip_status_student(request, regno, session_id):
    this_session = get_current_session()
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    student = Student.objects.get(reg_no=regno)
    if branchuser.school == student.school:
        if StudentSession.objects.filter(session=this_session, student=student, id=session_id).count() == 1:

            reg_finder = StudentSession.objects.get(id=session_id)
            if not reg_finder.status:
                other_session = StudentSession.objects.filter(session=this_session, student=student)
                
                for sess in other_session:
                    sess.status = False
                    sess.save()
            reg_finder.status = not reg_finder.status
            reg_finder.save()

    return_url = request.GET.get('return_path')
    return HttpResponseRedirect(return_url)


@login_required()
def flip_status_result(request, regno):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    student = Student.objects.get(reg_no=regno)
    if branchuser.school == student.school:
        student.publish_result = not student.publish_result
        student.save()

    return_url = request.GET.get('return_path')
    return HttpResponseRedirect(return_url)


def edit_student_session(request, regno):
    current_session = get_current_session()
    if Student.objects.filter(reg_no=regno).count() == 1:
        this_student = Student.objects.get(reg_no=regno)
    else:
        return HttpResponse("Student with that reg no not found.")
    if StudentSession.objects.filter(student=this_student, session=current_session, status=True).count() == 1:
        student_session = StudentSession.objects.get(student=this_student, session=current_session, status=True)
        available_sections = Section.objects.filter(grade=student_session.grade)
        available_houses = House.objects.filter(school=this_student.school)
        ret_url = request.GET.get('return_path')
        print("Ret URL: ")
        print(ret_url)

        if request.method == 'POST':
            rollno = request.POST.get('rollno', 1)
            section = request.POST.get('section')
            return_url = request.POST.get('redurl')
            house = request.POST.get('house')

            section = Section.objects.get(id=section)
            student_session.section = section
            student_session.roll_no = rollno
            student_session.house = house
            student_session.save()

            print('Return URL: ')
            print(return_url)

            return_url+= '?list=student'

            return HttpResponseRedirect(return_url)

    else:
        return HttpResponse("Reg No not found")

    context = {'student': student_session, 'avaiablesections': available_sections, 'return_url': ret_url, 'available_houses':available_houses}
    return render(request, "panel/edit_student_session.html", context)


def assign_subject(request, tid):
    teacher = Teacher.objects.get(id=tid)

    context = {
        'teacher': teacher,
               }

    return render(request, "panel/assign_subject.html", context)


@login_required
def assign_teacher(request):
    this_session = get_current_session()
    if request.method == 'POST':
        gradelevel = request.POST.get('gradelevel')
        req_teacher = request.POST.get('req_teacher')
        section = request.POST.get('section')
        subject = request.POST.get('subject')

        teacher = User.objects.get(id=req_teacher)
        grade = SchoolGrade.objects.get(id=gradelevel)
        section = Section.objects.get(id=section)
        subject = Subject.objects.get(id=subject)

        TeacherSubjectAccess.objects.get_or_create(session=this_session, teacher=teacher, grade=grade, section=section, subject=subject)

        ret_url = request.POST.get("redurl")
        return redirect(ret_url)
        # return HttpResponse("HI")
    else:
        return redirect("/panel/")

@login_required
def inputfullmarksredirector(request):
    if request.method == 'POST':
        user = request.user
        try:
            branchuser = BranchUser.objects.get(user=user)
        except BranchUser.DoesNotExist:
            return HttpResponse(
                'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.')

        term = request.POST.get('term')
        grade = request.POST.get('grade')

        url = '/panel/addfullmarks/' + grade + '/' + term + '/'

        return HttpResponseRedirect(url)

    else:
        return HttpResponseRedirect('/')


@login_required
def addfullmarks(request, grade, term):
    user = request.user
    try:
        branchuser = BranchUser.objects.get(user=user)

    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.')

    school = SchoolBranch.objects.get(id=branchuser.school.id)
    exam_term = SchoolTerm.objects.get(id=term)
    grade = SchoolGrade.objects.get(id=grade)
    edusession = get_current_session()

    subjects = Subject.objects.filter(
        session=edusession, branch=school, grade=grade, status=True).order_by('id')

    if GradeFullMarks.objects.filter(session=edusession, school=school, grade=grade, term=exam_term).count() == 0:
        gs = False
    else:
        gs = True

        subjects = GradeFullMarks.objects.filter(
            session=edusession, school=school, grade=grade, term=exam_term).order_by('id')

    if request.method == 'POST':
        for subject in subjects:
            this_subject = str(subject.id)
            th_full = request.POST.get(this_subject + '_th_full')
            pr_full = request.POST.get(this_subject + '_pr_full')

            th_pass = request.POST.get(this_subject + '_th_pass')
            pr_pass = request.POST.get(this_subject + '_pr_pass')

            if GradeFullMarks.objects.filter(session=edusession, school=school, grade=grade, term=exam_term,
                                             subject=subject).count() == 0:
                gfm = GradeFullMarks()

                gfm.session = edusession
                gfm.school = school
                gfm.grade = grade
                gfm.term = exam_term
                gfm.subject = subject
                gfm.th_fm = th_full
                gfm.pr_fm = pr_full
                gfm.th_pm = th_pass
                gfm.pr_pm = pr_pass

                gfm.save()

    context = {'grade': grade, 'school': school, 'exam_term': exam_term, 'edusession': edusession, 'subjects': subjects,
               'gs': gs}

    return render(request, 'panel/addfullmarks.html', context)



def addfullmarksedit(request, grade, term):
    the_grade = grade
    the_term = term
    user = request.user
    try:
        branchuser = BranchUser.objects.get(user=user)

    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.')

    school = SchoolBranch.objects.get(id=branchuser.school.id)
    exam_term = SchoolTerm.objects.get(id=term)
    grade = SchoolGrade.objects.get(id=grade)
    edusession = get_current_session()

    subjects = Subject.objects.filter(
        session=edusession, branch=school, grade=grade, status=True).order_by('id')

    if GradeFullMarks.objects.filter(session=edusession, school=school, grade=grade, term=exam_term).count() == 0:
        gs = False
    else:
        gs = True

    if request.method == 'POST':
        for subject in subjects:
            print(subject.id, subject.subject)
            this_subject = str(subject.id)
            th_full = request.POST.get(this_subject + '_th_full', 0)
            pr_full = request.POST.get(this_subject + '_pr_full', 0)
            th_pass = request.POST.get(this_subject + '_th_pass', 0)
            pr_pass = request.POST.get(this_subject + '_pr_pass', 0)

            if GradeFullMarks.objects.filter(session=edusession, school=school, grade=grade, term=exam_term,
                                             subject=subject).count() == 1:
                gfm = GradeFullMarks.objects.get(session=edusession, school=school, grade=grade, term=exam_term,
                                                 subject=subject)

                gfm.session = edusession
                gfm.school = school
                gfm.grade = grade
                gfm.term = exam_term
                gfm.subject = subject
                gfm.th_fm = th_full
                gfm.pr_fm = pr_full
                gfm.th_pm = th_pass
                gfm.pr_pm = pr_pass

                gfm.save()
            else:
                gfm = GradeFullMarks()

                gfm.session = edusession
                gfm.school = school
                gfm.grade = grade
                gfm.term = exam_term
                gfm.subject = subject
                gfm.th_fm = th_full
                gfm.pr_fm = pr_full
                gfm.th_pm = th_pass
                gfm.pr_pm = pr_pass

                gfm.save()

        url = '/panel/addfullmarks/' + the_grade + '/' + the_term + '/'

        return HttpResponseRedirect(url)

    subjects = GradeFullMarks.objects.filter(
        session=edusession, school=school, grade=grade, term=exam_term).order_by('id')

    context = {'grade': grade, 'school': school, 'exam_term': exam_term, 'edusession': edusession, 'subjects': subjects,
               'gs': gs, "school": school,}

    return render(request, 'panel/addfullmarksedit.html', context)

@login_required
def rename_subject(request):
    if request.method == 'POST':
        sid = request.POST.get('sid')
        subject = Subject.objects.get(id=sid)
        subject_name = request.POST.get('subjectname')

        subject.subject = subject_name
        try:
            subject.save()
            redurl = request.POST.get('redurl')
            return redirect(redurl)
        except Exception as e:
            return HttpResponse("Sorry Something Went Wrong. REF: "+ str(e))
    else:
        return redirect("/panel/")


@login_required
def rename_term(request):
    if request.method == 'POST':
        tid = request.POST.get('tid')
        if SchoolTerm.objects.filter(id=tid).count() == 1:
            term = SchoolTerm.objects.get(id=tid)
            term_name = request.POST.get('term_name')
            status = request.POST.get('termStatus')
            active = request.POST.get('activeStatus')

            name_in_short = request.POST.get('term_name_in_short')
            final_term = request.POST.get('final_term', None)
            final_term_name = request.POST.get('final_term_name')

            term_status = SchoolTermStatus.objects.get(id=status)

            if final_term in ["yes"]:
                term.final_term = True
            else:
                term.final_term = False


            term.term_name = term_name
            term.status = term_status
            term.active = active

            term.name_in_short = name_in_short
            #term.final_term = final_term
            term.final_term_name = final_term_name
            try:
                term.save()
                red_url = request.POST.get('red_url')
                return redirect(red_url)
            except Exception as e:
                return HttpResponse("Sorry Something Went Wrong. REF: "+ str(e))
        else:
            return HttpResponse("Term not found. Click  <a href='/panel'>Here</a> to go home.")
    else:
        return redirect("/panel/")


@login_required
def printgradesheetnow2078(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    slogan = " &nbsp; "
    if school.id <= 13:
        # Samata School
        slogan = "Education for all."
        logo = "https://cdn.hamro.com/simsnepal/logos/samata_logo_black.png"
    elif school.id == 14:
        # CSA Montessori
        slogan = "Soaring to Excellence"
        logo = "https://cdn.hamro.com/simsnepal/logos/csa.jpg"
    elif school.id == 15:
        # Paramount Children Academy
        slogan = " &nbsp; "
        logo = "https://cdn.hamro.com/simsnepal/logos/paramount.png"
    elif school.id >= 16 and school.id <= 22:
        # Samata School
        slogan = "Education for all."
        logo = "https://cdn.hamro.com/simsnepal/logos/samata_logo_black.png"

    if request.method == "POST":
        edusession = request.POST.get("edusession")
        term = request.POST.get("term")
        printtype = int(request.POST.get("printtype"))
        grade = request.POST.get("grade2", 0)
        section = request.POST.get("section2", 0)
        # printtype = request.POST.get('printtype', )  # 1 DETAIL 2 SUMMARIZED

        # print("PRINTTYPE", printtype)

        if grade == 0 or grade == None or grade == "":
            return HttpResponse(
                "Sorry! something went wrong. Please take care while submitting data."
            )
        else:
            this_grade = SchoolGrade.objects.get(id=grade)
        this_session = EduSession.objects.get(id=edusession)
        this_term = SchoolTerm.objects.get(id=term)

        # subjectcount = Subject.objects.filter(branch=school, grade=this_grade, status=True).count()

        if int(section) > 0:
            this_section = Section.objects.get(id=section)
        else:
            this_section = False
        calculated_rank = ""
        subjects = Subject.objects.filter(
            branch=school, grade=this_grade, status=True
        ).order_by("id")
        this_grade_subjects = Subject.objects.filter(
            branch=school, grade=this_grade, status=True
        ).order_by("id")
        subjectcount = ""
        for subject in subjects:
            subjectcount += "1"
        if this_section == False:
            students = StudentSession.objects.filter(
                grade=this_grade, status=True
            )

            calculated_rank = calculaterank2078(school.id, this_session, grade, term)

        else:
            # students = Student.objects.filter(
            #     grade=this_grade, section=this_section, status=True
            # )
            students = StudentSession.objects.filter(grade=this_grade, section=this_section, session=this_session, status=True)
            calculated_rank = calculaterank2078(
                school.id, this_session, grade, term, this_section
            )
            # print(school.id, this_session, grade, term, this_section)
            # print('calculated rank ', calculated_rank)
        sn = 0
        data = {}
        for student in students:
            sn += 1
            data[sn] = {}
            data[sn]["reg_no"] = student.student.reg_no
            data[sn]["name"] = student.student.name
            data[sn]["grade"] = student.grade
            data[sn]["section"] = student.section
            if student.student.reg_no in calculated_rank:
                data[sn]["rank"] = calculated_rank[student.student.reg_no]
            else:
                data[sn]["rank"] = "-"

            if printtype == 2:
                # sd = summarizedResult(school, term, grade, student.reg_no)
                sd = detailResult2078(
                    school, term, grade, student.student.reg_no, printtype
                )
                data[sn]["mo_th"] = sd["mo_th"]
                data[sn]["mo_pr"] = sd["mo_pr"]
                data[sn]["total"] = sd["total"]
                data[sn]["gp"] = sd["gp"]
                data[sn]["remarks"] = sd["remarks"]
                # print(summarizedResult)
                # print('Summarized Result')
            else:
                sd = detailResult2078(
                    school, term, grade, student.student.reg_no, printtype
                )
                data[sn]["mo_th"] = sd["mo_th"]
                data[sn]["mo_pr"] = sd["mo_pr"]
                data[sn]["total"] = sd["total"]
                data[sn]["gp"] = sd["gp"]
                data[sn]["subjects"] = sd["subjects"]
                data[sn]["remarks"] = sd["remarks"]

                # print(detailResult, subjectcount)
                # print('Detail Result')
        scount = 13 - subjects.count()
        subjectcount = range(scount)

        context = {
            "school": school,
            "term": this_term,
            "year": this_term.year,
            "data": data,
            "grade": this_grade,
            "section": this_section,
            "subjects": this_grade_subjects,
            "subjectcount": subjectcount,
            "std_list": data,
            "slogan": slogan,
            "logo": logo,
        }
        if printtype == 2:
            return render(request, "panel/gradesheetall_078.html", context)
        else:
            return render(request, "panel/gradesheetall_078.html", context)
    else:
        return HttpResponseRedirect("/panel/")


@login_required
def term_calculation(request):
    this_session = get_current_session()
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    if request.method == "POST":
        term_id = request.POST.get("term_id")
        all_terms = SchoolTerm.objects.filter(year=this_session, school=school, active=True)

        school_term = SchoolTerm.objects.get(id=term_id)
        result_calc, created = ResultManagement.objects.get_or_create(year=this_session, school=school, school_term=school_term)
        term_mgmt = dict()
        result_calc.term_calculation = json.dumps(term_mgmt)
        result_calc.save()

        for term in all_terms:
            if term.id <= int(term_id):
                term_mgmt[str(term.id)] = int(request.POST.get(str(term.id)))
        
        term_mgmt = json.dumps(term_mgmt)
        result_calc.term_calculation = term_mgmt
        result_calc.save()

        #return HttpResponse(request.POST.get(term_id))
        return HttpResponseRedirect("/panel/terms/?action=result_calc")
    else:
        return HttpResponseRedirect("/panel/terms/?action=result_calc")


@login_required
def new_public_result_2079(request):
    if request.method == "POST":

        regno = request.POST.get("regno")
        code = request.POST.get("scode")
        no_of_terms = 0

        if Student.objects.filter(reg_no=regno).count() == 1:
            student = Student.objects.get(reg_no=int(regno))

            if student.pin_code != int(code):
                message = (
                        "Sorry pincode doesnot match for "
                        + student.name
                        + "."
                )
                context = {"message": message}
                return render(request, "panel/resultform.html", context)

            result_status = LiveResult.objects.get(school=student.school)
            grade_list = json.loads(result_status.grade_list)
            term = result_status.term
            this_term = SchoolTerm.objects.get(id=term)
            calc_type = getattr(result_status, "calculation_type", "legacy")
            weighted_cfg = None
            if calc_type == "weighted":
                weighted_cfg = WeightedResultManagement.objects.filter(
                    school=student.school, year=this_term.year, school_term=this_term
                ).first()
            std_session = StudentSession.objects.get(student=student, status=True)

            if std_session.grade.id not in grade_list:
                message = (
                        "Sorry the result of Grade "
                        + std_session.grade.grade_name
                        + " has not been published yet. For more information please contact on School."
                )
                context = {"message": message}
                return render(request, "panel/resultform.html", context)
        else:
            context = {
                "message": "Sorry student with the registration number could not be found."
            }
            return render(request, "panel/resultform.html", context)

        if student.school.id <= 13:            
            # Samata School
            slogan = "Education for all."        
            logo = "https://cdn.hamro.com/simsnepal/logos/samata_logo_black.png"    
        elif student.school.id == 14:             
            # CSA Montessori
            slogan = "Soaring to Excellence"                                                                                            
            logo = "https://cdn.hamro.com/simsnepal/logos/csa.jpg"
        elif student.school.id == 15:                                                                                                                    # Paramount Children Academy
            slogan = " &nbsp; "                           
            logo = "https://cdn.hamro.com/simsnepal/logos/paramount.png"
        elif student.school.id >= 16 and student.school.id <= 22:
            # Samata School
            slogan = "Education for all."                                               
            logo = "https://cdn.hamro.com/simsnepal/logos/samata_logo_black.png"

        # sc
        mo_dict = dict()
        grade_subjects = Subject.objects.filter(
            grade=std_session.grade, branch=student.school, status=True
        )
        all_students = StudentSession.objects.filter(grade=std_session.grade, status=1)
        total_student = all_students.count()

        if calc_type == "weighted":
            weight_config = weighted_cfg.weight_config if weighted_cfg else {}
            weights = _parse_weighted_term_config(weight_config, this_term.id, include_current=True)
            term_list = sorted(set([this_term.id] + list(weights.keys())))
            no_of_terms = len(term_list)

            mo_dict, _ = build_weighted_mo_dict_for_students(
                school=student.school,
                this_session=this_term.year,
                this_grade=std_session.grade,
                target_term=this_term,
                students=[std_session],
                subjects=grade_subjects,
                term_list=term_list,
                weight_config=weight_config,
            )

            student_session = std_session
            spacing = max(0, 14 - grade_subjects.count())
            the_space = "a" * spacing
            context = {
                "term_list": term_list,
                "no_of_terms": no_of_terms,
                "no_of_terms_range": range(no_of_terms),
                "no_of_terms_marks_count": no_of_terms * 2,
                "gpa_colspan": 3 + (no_of_terms * 2),
                "year": this_term.year,
                "term": this_term,
                "student": student_session,
                "grade_subjects": grade_subjects,
                "mo_dict": json.dumps(mo_dict),
                "the_space": the_space,
                "slogan": slogan,
                "logo": logo,
            }
            return render(request, "panel/result79_updated.html", context)

        # Getting Term Calculation
        term_calculation = ResultManagement.objects.get(school_term=this_term)
        term_list = []
        total_gpa_calculation = dict()
        # total_gpa_calculation[student.reg_no] = dict()
        for key, value in json.loads(term_calculation.term_calculation).items():
            if value > 0:
                no_of_terms += 1
                this_term = SchoolTerm.objects.get(id=key)
                # term_list.append(this_term)
                term_list.append(key)

                print("Percent Calculation")

                marks_obtained = MarkObtained.objects.filter(
                    student=student, term=key)

                for mo in marks_obtained:
                    print("TERM ", mo.term.id)
                    print("SUBJECT \t", mo.subject.id, "NAME: \t", mo.subject)
                    print("Percentage ", value)
                    # Getting Fullmark of the term
                    gfm = GradeFullMarks.objects.get(term=mo.term, subject=mo.subject)
                    print(gfm, gfm.th_fm, gfm.pr_fm)
                    print("+++++++")

                    # Calculating marks according to Percentage
                    if gfm.th_fm > 0:
                        cal_th_mo = (value/100) * mo.th_mo
                        cal_th_fm = (value/100) * gfm.th_fm
                        cal_th_pm = (value/100) * gfm.th_pm
                    else:
                        cal_th_mo = 0
                        cal_th_fm = 0
                        cal_th_pm = 0

                    if gfm.pr_fm > 0:
                        cal_pr_mo = (value/100) * mo.pr_mo
                        cal_pr_fm = (value/100) * gfm.pr_fm
                        cal_pr_pm = (value/100) * gfm.pr_pm
                    else:
                        cal_pr_mo = 0
                        cal_pr_fm = 0
                        cal_pr_pm = 0

                    if str(str(student.reg_no)+"_"+str(mo.subject.id)) not in total_gpa_calculation:
                        total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)] = dict()

                    pre_text = str(student.reg_no)+"_"+str(mo.subject.id)+"_"+str(mo.term.id)
                    pre_total = str(student.reg_no)+"_"+str(mo.subject.id)

                    # FUll Marks
                    if "th_mo" in total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]:
                        total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["th_mo"] += cal_th_mo
                        total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["th_fm"] += cal_th_fm
                        total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["th_pm"] += cal_th_pm
                    else:
                        total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["th_mo"] = cal_th_mo
                        total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["th_fm"] = cal_th_fm
                        total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["th_pm"] = cal_th_pm

                    if "pr_mo" in total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]:
                        total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["pr_mo"] += cal_pr_mo
                        total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["pr_fm"] += cal_pr_fm
                        total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["pr_pm"] += cal_pr_pm
                    else:
                        total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["pr_mo"] = cal_pr_mo
                        total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["pr_fm"] = cal_pr_fm
                        total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["pr_pm"] = cal_pr_pm

                    mo_dict[pre_text + "_th_mo"] = cal_th_mo
                    mo_dict[pre_text + "_pr_mo"] = cal_pr_mo

                    ga_gpa = GradeAndGpa(cal_th_fm, cal_pr_fm, cal_th_mo, cal_pr_mo, mo.subject.heavy_weight)
                    mo_dict[pre_text + "_th_grade"] = ga_gpa.th_grade
                    mo_dict[pre_text + "_pr_grade"] = ga_gpa.pr_grade
                    # print(ga_gpa)
                    # attrs = vars(ga_gpa)
                    # print(', '.join("%s: %s" % item for item in attrs.items()))

                    # mo_dict[pre_total + "_total_grade"] = "A"
                    # mo_dict[pre_total + "_total_grade_point"] = 4

        # Calculating GradePoint of each subject
        # for key, value in json.loads(term_calculation.term_calculation).items():
        #     if value > 0:
        #         # for key, value in mo_dict:
        #         #     print(key,value)
        #         print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
        #         print(mo_dict)
        total_gp = 0
        for subject in grade_subjects:
            if str(str(student.student.reg_no) + "_" + str(subject.id)) in total_gpa_calculation:
                th_fm = total_gpa_calculation[str(student.student.reg_no) + "_" + str(subject.id)]["th_fm"]
            else:
                return HttpResponse(f"For {student.student.reg_no}, Data regarding {subject} is missing. ",
                                        f"Please contact on school.")
            th_fm = total_gpa_calculation[str(student.reg_no) + "_" + str(subject.id)]["th_fm"]
            pr_fm = total_gpa_calculation[str(student.reg_no) + "_" + str(subject.id)]["pr_fm"]
            th_mo = total_gpa_calculation[str(student.reg_no) + "_" + str(subject.id)]["th_mo"]
            pr_mo = total_gpa_calculation[str(student.reg_no) + "_" + str(subject.id)]["pr_mo"]

            g_gpa = GradeAndGpa(th_fm, pr_fm, th_mo, pr_mo, 1)
            mo_dict[str(student.reg_no)+"_"+str(subject.id)+"_total_grade"] = g_gpa.total_grade
            mo_dict[str(student.reg_no)+"_"+str(subject.id)+"_total_grade_point"] = g_gpa.total_point
            mo_dict[str(student.student.reg_no) + "_" + str(subject.id) + "_total_symbol"] = g_gpa.total_symbol

            total_gp +=g_gpa.total_point

        mo_dict[str(student.reg_no)+"_gpa"] = round(total_gp/grade_subjects.count(), 2)
        
        student_session = StudentSession.objects.get(student=int(regno), status=True)
        the_space = ""
        spacing = 14 - grade_subjects.count()
        for i in range(spacing):
            the_space += "a"
        context = {
            "term_list": term_list,
            "no_of_terms": no_of_terms,
            "no_of_terms_range": range(no_of_terms),
            "no_of_terms_marks_count": no_of_terms*2,
            "gpa_colspan": 3 + (no_of_terms*2),
            "year": this_year,
            "term": this_term,
            "student": student_session,
            "grade_subjects": grade_subjects,
            "mo_dict": json.dumps(mo_dict),
            "the_space": the_space,
            "slogan": slogan,
            "logo": logo,
        }
        return render(request, "panel/result79_updated.html", context)
    else:
        return render(request, "panel/resultform.html")


@login_required
def new_private_result_2079(request, regno):
    no_of_terms = 0
    fail = 0
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)

    if Student.objects.filter(reg_no=regno).count() == 1:
        student = Student.objects.get(reg_no=int(regno))

        if student.school != school:
            message = (
                    "Sorry you are not allowed to view result of student from another school."
            )
            context = {"message": message}
            return render(request, "panel/resultform.html", context)

        result_status = LiveResult.objects.get(school=student.school)
        grade_list = json.loads(result_status.grade_list)
        term = result_status.term
        this_term = SchoolTerm.objects.get(id=term)
        calc_type = getattr(result_status, "calculation_type", "legacy")
        weighted_cfg = None
        if calc_type == "weighted":
            weighted_cfg = WeightedResultManagement.objects.filter(
                school=student.school, year=this_term.year, school_term=this_term
            ).first()
        std_session = StudentSession.objects.get(student=student, status=True)

        if std_session.grade.id not in grade_list:
            message = (
                    "Sorry the result of Grade "
                    + std_session.grade.grade_name
                    + " has not been published yet. For more information please contact on School."
            )
            context = {"message": message}
            return render(request, "panel/resultform.html", context)
    else:
        context = {
            "message": "Sorry student with the registration number could not be found."
        }
        return render(request, "panel/resultform.html", context)

    if student.school.id <= 13:
        # Samata School
        slogan = "Education for all."
        logo = "https://cdn.hamro.com/simsnepal/logos/samata_logo_black.png"
    elif student.school.id == 14:
        # CSA Montessori
        slogan = "Soaring to Excellence"
        logo = "https://cdn.hamro.com/simsnepal/logos/csa.jpg"
    elif student.school.id == 15:
        # Paramount Children Academy
        slogan = " &nbsp; "
        logo = "https://cdn.hamro.com/simsnepal/logos/paramount.png"
    elif student.school.id >= 16 and student.school.id <= 26:
        # Samata School
        slogan = "Education for all."
        logo = "https://cdn.hamro.com/simsnepal/logos/samata_logo_black.png"
    # sc
    mo_dict = dict()
    grade_subjects = Subject.objects.filter(
        grade=std_session.grade, branch=student.school, status=True
    )
    all_students = StudentSession.objects.filter(grade=std_session.grade, status=1)
    total_student = all_students.count()

    if calc_type == "weighted":
        weight_config = weighted_cfg.weight_config if weighted_cfg else {}
        weights = _parse_weighted_term_config(weight_config, this_term.id, include_current=True)
        term_list = sorted(set([this_term.id] + list(weights.keys())))
        no_of_terms = len(term_list)

        mo_dict, _ = build_weighted_mo_dict_for_students(
            school=student.school,
            this_session=this_term.year,
            this_grade=std_session.grade,
            target_term=this_term,
            students=[std_session],
            subjects=grade_subjects,
            term_list=term_list,
            weight_config=weight_config,
        )

        student_session = std_session
        spacing = max(0, 14 - grade_subjects.count())
        the_space = "a" * spacing
        context = {
            "term_list": term_list,
            "no_of_terms": no_of_terms,
            "no_of_terms_range": range(no_of_terms),
            "no_of_terms_marks_count": no_of_terms * 2,
            "gpa_colspan": 3 + (no_of_terms * 2),
            "year": this_term.year,
            "term": this_term,
            "student": student_session,
            "grade_subjects": grade_subjects,
            "mo_dict": json.dumps(mo_dict),
            "the_space": the_space,
            "slogan": slogan,
            "logo": logo,
        }
        return render(request, "panel/result79_updated.html", context)

    # Getting Term Calculation
    term_calculation = ResultManagement.objects.get(school_term=this_term)
    term_list = []
    total_gpa_calculation = dict()
    # total_gpa_calculation[student.reg_no] = dict()
    for key, value in json.loads(term_calculation.term_calculation).items():
        if value > 0:
            no_of_terms += 1
            this_term = SchoolTerm.objects.get(id=key)
            # term_list.append(this_term)
            term_list.append(key)

            print("Percent Calculation")

            marks_obtained = MarkObtained.objects.filter(
                student=student, term=key)

            for mo in marks_obtained:
                print("TERM ", mo.term.id)
                print("SUBJECT \t", mo.subject.id, "NAME: \t", mo.subject)
                print("Percentage ", value)
                # Getting Fullmark of the term
                gfm = GradeFullMarks.objects.get(term=mo.term, subject=mo.subject)
                print(gfm, gfm.th_fm, gfm.pr_fm)
                print("+++++++")

                # Calculating marks according to Percentage
                if gfm.th_fm > 0:
                    cal_th_mo = (value/100) * mo.th_mo
                    cal_th_fm = (value/100) * gfm.th_fm
                    cal_th_pm = (value/100) * gfm.th_pm
                else:
                    cal_th_mo = 0
                    cal_th_fm = 0
                    cal_th_pm = 0

                if gfm.pr_fm > 0:
                    cal_pr_mo = (value/100) * mo.pr_mo
                    cal_pr_fm = (value/100) * gfm.pr_fm
                    cal_pr_pm = (value/100) * gfm.pr_pm
                else:
                    cal_pr_mo = 0
                    cal_pr_fm = 0
                    cal_pr_pm = 0

                if str(str(student.reg_no)+"_"+str(mo.subject.id)) not in total_gpa_calculation:
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)] = dict()

                pre_text = str(student.reg_no)+"_"+str(mo.subject.id)+"_"+str(mo.term.id)
                pre_total = str(student.reg_no)+"_"+str(mo.subject.id)

                # FUll Marks
                if "th_mo" in total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]:
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["th_mo"] += cal_th_mo
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["th_fm"] += cal_th_fm
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["th_pm"] += cal_th_pm
                else:
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["th_mo"] = cal_th_mo
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["th_fm"] = cal_th_fm
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["th_pm"] = cal_th_pm

                if "pr_mo" in total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]:
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["pr_mo"] += cal_pr_mo
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["pr_fm"] += cal_pr_fm
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["pr_pm"] += cal_pr_pm
                else:
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["pr_mo"] = cal_pr_mo
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["pr_fm"] = cal_pr_fm
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["pr_pm"] = cal_pr_pm

                mo_dict[pre_text + "_th_mo"] = cal_th_mo
                mo_dict[pre_text + "_pr_mo"] = cal_pr_mo

                ga_gpa = GradeAndGpa(cal_th_fm, cal_pr_fm, cal_th_mo, cal_pr_mo, mo.subject.heavy_weight)
                mo_dict[pre_text + "_th_grade"] = ga_gpa.th_grade
                mo_dict[pre_text + "_th_symbol"] = ga_gpa.th_symbol
                mo_dict[pre_text + "_pr_grade"] = ga_gpa.pr_grade
                mo_dict[pre_text + "_pr_symbol"] = ga_gpa.pr_symbol
                # print(ga_gpa)
                # attrs = vars(ga_gpa)
                # print(', '.join("%s: %s" % item for item in attrs.items()))

                # mo_dict[pre_total + "_total_grade"] = "A"
                # mo_dict[pre_total + "_total_grade_point"] = 4

    # Calculating GradePoint of each subject
    # for key, value in json.loads(term_calculation.term_calculation).items():
    #     if value > 0:
    #         # for key, value in mo_dict:
    #         #     print(key,value)
    #         print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    #         print(mo_dict)
    total_gp = 0
    for subject in grade_subjects:
        if str(str(student.reg_no) + "_" + str(subject.id)) in total_gpa_calculation:
            th_fm = total_gpa_calculation[str(student.reg_no) + "_" + str(subject.id)]["th_fm"]
        else:
            return HttpResponse(f"For {student.reg_no}, Data regarding {subject} is missing. Subject id is {subject.id}",
                                f"It can be either full marks or just marks.")
        # th_fm = total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["th_fm"]
        pr_fm = total_gpa_calculation[str(student.reg_no) + "_" + str(subject.id)]["pr_fm"]
        th_mo = total_gpa_calculation[str(student.reg_no) + "_" + str(subject.id)]["th_mo"]
        pr_mo = total_gpa_calculation[str(student.reg_no) + "_" + str(subject.id)]["pr_mo"]
        print(th_fm, pr_fm, th_mo, pr_mo, 1)
        
        g_gpa = GradeAndGpa(th_fm, pr_fm, th_mo, pr_mo, 1)
        mo_dict[str(student.reg_no)+"_"+str(subject.id)+"_total_grade"] = g_gpa.total_grade
        mo_dict[str(student.reg_no)+"_"+str(subject.id)+"_total_grade_point"] = g_gpa.total_point
        mo_dict[str(student.reg_no)+"_"+str(subject.id)+"_total_symbol"] = g_gpa.total_symbol

        total_gp +=g_gpa.total_point

    mo_gpa = round(total_gp/grade_subjects.count(), 2)
    mo_dict[str(student.reg_no)+"_gpa"] = mo_gpa
    
    if fail > 0:
        mo_dict[str(student.reg_no) + "_remarks"] = "Labour Hard"
    else:
        mo_dict[str(student.reg_no) + "_remarks"] = remarks(mo_gpa)
                
    student_session = StudentSession.objects.get(student=int(regno), status=True)
    the_space = ""
    spacing = 12 - grade_subjects.count()

    subjectcount = range(spacing)
    for i in range(spacing):
        the_space += "a"
    context = {
        "term_list": term_list,
        "no_of_terms": no_of_terms,
        "no_of_terms_range": range(no_of_terms),
        "no_of_terms_marks_count": no_of_terms*2,
        "gpa_colspan": 3 + (no_of_terms*2),
        "year": this_year,
        "term": this_term,
        "student": student_session,
        "grade_subjects": grade_subjects,
        "mo_dict": json.dumps(mo_dict),
        "the_space": the_space,
        "slogan": slogan,
        "logo": logo,
        "school": school,
        "the_space": range(spacing),
    }
    return render(request, "panel/gradesheet_private.html", context)


@login_required
def print_gradesheet(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    slogan = " &nbsp; "
    logo = ""
    no_of_terms = 0
    if school.id <= 13:
        # Samata School
        slogan = "Education for all."
        logo = "https://cdn.hamro.com/simsnepal/logos/samata_logo_black.png"
    elif school.id == 14:
        # CSA Montessori
        slogan = "Soaring to Excellence"
        logo = "https://cdn.hamro.com/simsnepal/logos/csa.jpg"
    elif school.id == 15:
        # Paramount Children Academy
        slogan = " &nbsp; "
        logo = "https://cdn.hamro.com/simsnepal/logos/paramount.png"
    elif school.id >= 16 and school.id <= 26:
        # Samata School
        slogan = "Education for all."
        logo = "https://cdn.hamro.com/simsnepal/logos/samata_logo_black.png"

    if request.method == "POST":
        edusession = request.POST.get("edusession")
        term = request.POST.get("term")
        printtype = int(request.POST.get("printtype"))
        grade = request.POST.get("grade2", 0)
        section = request.POST.get("section2", 0)
        pass_fail_filter =  int(request.POST.get("pass_fail_filter", 0))
        # printtype = request.POST.get('printtype', )  # 1 DETAIL 2 SUMMARIZED
        # result_type =  int(request.POST.get("result_type", 0))
        result_type = int(request.POST.get("result_type", 0))
        calc_type = request.POST.get("calc_type", "legacy")
        weighted_cfg = None

        print("Result type:", result_type)

        #return HttpResponse({"type":type(result_type), "value": result_type})
        #print(result_type)
        
        # #if result_type:
        # context = {"name": "gradesheetall_nongraded", "result_type": result_type}
        # render(request, "panel/gradesheetall_nongraded.html", context)

        # print("PRINTTYPE", printtype)

        if grade == 0 or grade == None or grade == "":
            return HttpResponse(
                "Sorry! something went wrong. Please take care while submitting data."
            )
        else:
            this_grade = SchoolGrade.objects.get(id=grade)
        this_session = EduSession.objects.get(id=edusession)
        this_term = SchoolTerm.objects.get(id=term)
        print(this_term)
        if this_term.final_term:
            print("this is final")
        else:
            print("this is not a final")

        # subjectcount = Subject.objects.filter(branch=school, grade=this_grade, status=True).count()

        if int(section) > 0:
            this_section = Section.objects.get(id=section)
        else:
            this_section = False
        calculated_rank = ""
        subjects = Subject.objects.filter(
            branch=school, grade=this_grade, status=True, session=this_session
        ).order_by("id")

        grade_subjects = Subject.objects.filter(
            branch=school, grade=this_grade, status=True, session=this_session
        ).order_by("id")

        subjectcount = ""
        for subject in subjects:
            subjectcount += "1"

        if this_section == False:
            students = StudentSession.objects.filter(
                grade=this_grade, status=True, session=this_session
            ).order_by("section","roll_no")

            # calculated_rank = calculaterank2078(school.id, this_session, grade, term)

        else:
            # students = Student.objects.filter(
            #     grade=this_grade, section=this_section, status=True
            # )
            students = StudentSession.objects.filter(grade=this_grade, section=this_section, session=this_session,
                                                     status=True).order_by("section","roll_no")
            #calculated_rank = calculaterank2078(
            #    school.id, this_session, grade, term, this_section
            #)
            # print(school.id, this_session, grade, term, this_section)
            # print('calculated rank ', calculated_rank)

        if calc_type == "weighted":
            weighted_cfg = WeightedResultManagement.objects.filter(
                school=school, year=this_session, school_term=this_term
            ).first()

        term_calculation = ResultManagement.objects.get(school_term=this_term)
        term_list = []
        total_gpa_calculation = dict()

        sub_total_fm_pm = dict()

        term_acronym = dict()

        sn = 0
        data = {}
        mo_dict = dict()
        terms_with_practical = set()
        final_term_count = 0

        has_practical = lambda term_id: MarkObtained.objects.filter(term=term_id, pr_mo__gt=0).exists()
        weight_config = {}
        if calc_type == "weighted":
            weight_config = weighted_cfg.weight_config if weighted_cfg else {}
            weights = _parse_weighted_term_config(weight_config, this_term.id, include_current=True)
            term_ids = sorted(set([this_term.id] + list(weights.keys())))
            terms_for_display = SchoolTerm.objects.filter(id__in=term_ids).order_by("id")
            for term_obj in terms_for_display:
                no_of_terms += 1
                term_acronym[term_obj.name_in_short or term_obj.term_name] = term_obj.term_name
                term_list.append(term_obj.id)
                if has_practical(term_obj.id):
                    terms_with_practical.add(term_obj.id)
        else:
            for key, value in json.loads(term_calculation.term_calculation).items():
                if value > 0:
                    no_of_terms += 1
                    this_term = SchoolTerm.objects.get(id=key)
                    term_acronym[this_term.name_in_short or this_term.term_name] = this_term.term_name
                    term_list.append(key)

                    if has_practical(key):
                        terms_with_practical.add(key)
        
        if calc_type == "weighted":
            students = students.select_related("student", "grade", "section")
            student_list = list(students)
            student_ids = [s.student_id for s in student_list]

            attendance_map = {}
            if student_ids:
                for att in Attendance.objects.filter(
                    reg_no_id__in=student_ids,
                    grade=this_grade,
                    session=this_session,
                    term=this_term,
                ):
                    attendance_map[att.reg_no_id] = (
                        att.no_of_school_days,
                        att.no_of_present_days,
                    )

            data = {}
            for idx, student in enumerate(student_list, start=1):
                data[idx] = {
                    "session_detail": student,
                    "student_detail": student.student,
                    "reg_no": student.student.reg_no,
                    "name": student.student.name,
                    "grade": student.grade,
                    "section": student.section,
                    "no_of_school_days": None,
                    "no_of_present_days": None,
                }
                att_vals = attendance_map.get(student.student_id)
                if att_vals:
                    data[idx]["no_of_school_days"] = att_vals[0]
                    data[idx]["no_of_present_days"] = att_vals[1]

            mo_dict, _ = build_weighted_mo_dict_for_students(
                school=school,
                this_session=this_session,
                this_grade=this_grade,
                target_term=this_term,
                students=student_list,
                subjects=grade_subjects,
                term_list=term_list,
                weight_config=weight_config,
            )

            spacing = max(0, 12 - grade_subjects.count())
            the_space = range(spacing)

            base_context = {
                "term_list": term_list,
                "no_of_terms": no_of_terms,
                "no_of_terms_range": range(no_of_terms),
                "no_of_terms_marks_count": no_of_terms * 2,
                "school": school,
                "term": this_term,
                "year": this_term.year,
                "data": data,
                "grade": this_grade,
                "section": this_section,
                "subjects": grade_subjects,
                "std_list": data,
                "slogan": slogan,
                "logo": logo,
                "mo_dict": json.dumps(mo_dict),
                "term_acronym": term_acronym,
                "the_space": the_space,
            }

            if int(result_type) == 1:
                base_context["gpa_colspan"] = 4 + (no_of_terms * 2)
                return render(request, "panel/gradesheetall_nongraded.html", base_context)

            base_context["gpa_colspan"] = 3 + (no_of_terms * 2)
            return render(request, "panel/get_marks_grade_sheet_new_grading_system_exam_updated.html", base_context)

        if int(result_type) == 1:
            context = get_marks_grade_sheet(
                no_of_terms=no_of_terms, term_list=term_list, 
                term_calculation=term_calculation, pass_fail_filter=pass_fail_filter, 
                students=students, grade_subjects=grade_subjects, this_term=this_term,
                school=school, subjects=subjects, this_grade=this_grade,
                this_section=this_section, slogan=slogan, logo=logo, term_acronym=term_acronym, this_session=this_session)
            return render(request, "panel/gradesheetall_nongraded.html", context)

        if int(result_type) == 2:
#            context = get_marks_grade_sheet_new_grading_system_deepseek(
            context = get_marks_grade_sheet_new_grading_system_exam_updated(
                no_of_terms=no_of_terms, term_list=term_list, 
                term_calculation=term_calculation, pass_fail_filter=pass_fail_filter, 
                students=students, grade_subjects=grade_subjects, this_term=this_term,
                school=school, subjects=subjects, this_grade=this_grade,
                this_section=this_section, slogan=slogan, logo=logo, term_acronym=term_acronym, this_session=this_session)
#            return render(request, "panel/gradesheetall.html", context)
#            return render(request, "panel/gradesheetall_nongraded.html", context)
            return render(request, "panel/get_marks_grade_sheet_new_grading_system_exam_updated.html", context)


        for student in students:
            sn += 1
            fail = 0
            data[sn] = {}
            data[sn]["session_detail"] = student
            data[sn]["student_detail"] = student.student
            data[sn]["reg_no"] = student.student.reg_no
            data[sn]["name"] = student.student.name
            data[sn]["grade"] = student.grade
            data[sn]["section"] = student.section

            try:
                att = Attendance.objects.get(reg_no=student.student, grade=student.grade, session=this_session, term=this_term)
                data[sn]["no_of_school_days"] = att.no_of_school_days
                data[sn]["no_of_present_days"] = att.no_of_present_days
            except:
                data[sn]["no_of_school_days"] = False
                data[sn]["no_of_present_days"] = False

            for key, value in json.loads(term_calculation.term_calculation).items():
                if value > 0:
                    marks_obtained = MarkObtained.objects.filter(
                        student=student.student, term=key)

                    for mo in marks_obtained:
                        gfm = GradeFullMarks.objects.get(term=mo.term, subject=mo.subject)
                        sub_heavy_weight = Subject.objects.get(id=mo.subject.id)
				
                        cal_th_mo = cal_th_fm = cal_th_pm = cal_pr_mo = cal_pr_fm = cal_pr_pm = 0

                        if gfm.th_fm > 0:
                            cal_th_mo = (value / 100) * mo.th_mo
                            cal_th_fm = (value / 100) * gfm.th_fm
                            cal_th_pm = (value / 100) * gfm.th_pm

                            if str(mo.subject.id)+"th_fm" not in sub_total_fm_pm:
                                sub_total_fm_pm[str(mo.subject.id)+"th_fm"] = cal_th_fm
                                sub_total_fm_pm[str(mo.subject.id)+"pr_fm"] = 0

                        if gfm.pr_fm > 0:
                            cal_pr_mo = (value / 100) * mo.pr_mo
                            cal_pr_fm = (value / 100) * gfm.pr_fm
                            cal_pr_pm = (value / 100) * gfm.pr_pm

                            if str(mo.subject.id)+"pr_fm" not in sub_total_fm_pm:
                                sub_total_fm_pm[str(mo.subject.id)+"pr_fm"] = cal_pr_fm

                        if str(str(student.student.reg_no) + "_" + str(mo.subject.id)) not in total_gpa_calculation:
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)] = dict()

                        pre_text = str(student.student.reg_no) + "_" + str(mo.subject.id) + "_" + str(mo.term.id)
                        pre_total = str(student.student.reg_no) + "_" + str(mo.subject.id)

                        # FUll Marks
                        if "th_mo" in total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]:
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["th_mo"] += cal_th_mo
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["th_fm"] += cal_th_fm
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["th_pm"] += cal_th_pm
                        else:
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["th_mo"] = cal_th_mo
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["th_fm"] = cal_th_fm
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["th_pm"] = cal_th_pm

                        if "pr_mo" in total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]:
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["pr_mo"] += cal_pr_mo
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["pr_fm"] += cal_pr_fm
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["pr_pm"] += cal_pr_pm
                        else:
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["pr_mo"] = cal_pr_mo
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["pr_fm"] = cal_pr_fm
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["pr_pm"] = cal_pr_pm

                        mo_dict[pre_text + "_th_mo"] = cal_th_mo
                        mo_dict[pre_text + "_pr_mo"] = cal_pr_mo

#                        ga_gpa = GradeAndGpa(cal_th_fm, cal_pr_fm, cal_th_mo, cal_pr_mo, mo.subject.heavy_weight)
                        ga_gpa = GradeAndGpaNew(cal_th_fm, cal_pr_fm, cal_th_mo, cal_pr_mo, mo.subject.heavy_weight,result_type=result_type)
                        mo_dict[pre_text + "_th_grade"] = ga_gpa.th_grade
                        mo_dict[pre_text + "_th_symbol"] = ga_gpa.th_symbol
                        mo_dict[pre_text + "_pr_grade"] = ga_gpa.pr_grade
                        mo_dict[pre_text + "_pr_symbol"] = ga_gpa.pr_symbol
                        mo_dict[pre_text + "_total_symbol"] = ga_gpa.total_symbol

                        #if sub_heavy_weight.heavy_weight and 
                        if mo.term.final_term:
                            final_term_count +=1

                        

            total_gp = 0
            for subject in grade_subjects:
                if str(str(student.student.reg_no) + "_" + str(subject.id)) in total_gpa_calculation:
                    th_fm = total_gpa_calculation[str(student.student.reg_no) + "_" + str(subject.id)]["th_fm"]
                    pr_fm = total_gpa_calculation[str(student.student.reg_no) + "_" + str(subject.id)]["pr_fm"]
                    th_mo = total_gpa_calculation[str(student.student.reg_no) + "_" + str(subject.id)]["th_mo"]
                    pr_mo = total_gpa_calculation[str(student.student.reg_no) + "_" + str(subject.id)]["pr_mo"]
                else:
                    #return HttpResponse(f"For {student.student.reg_no}, Data regarding {subject} is missing. ",
                    #                    f"It can be either full marks or just marks.")
                    print(subject)
                    print(f"For {student.student.reg_no}, Data regarding {subject} is missing. ",
                                       f"It can be either full marks or just marks.")
                    if str(subject.id)+"th_fm" in sub_total_fm_pm:
                        th_fm =  sub_total_fm_pm[str(subject.id)+"th_fm"]
                    else:
                        th_fm =  0                       
                    
                    if str(subject.id)+"pr_fm" in sub_total_fm_pm:
                        pr_fm = sub_total_fm_pm[str(subject.id)+"pr_fm"]
                    else:
                        pr_fm = 0
                    
                    th_mo = 0 
                    pr_mo = 0

                # th_fm = total_gpa_calculation[str(student.student.reg_no) + "_" + str(subject.id)]["th_fm"]
                

                #print("Subject " + str(subject) + "in grade subjects")
                #print(subject, th_fm, pr_fm, th_mo, pr_mo)
                #print("HEAVY WEIGHT: ")
                #print(subject.heavy_weight)

                g_gpa = GradeAndGpa(th_fm, pr_fm, th_mo, pr_mo, subject.heavy_weight)
                #if this_term.final_term and subject.heavy_weight:
                    #if float(g_gpa.total_point) <1.6:
                        #fail += 1
                        #g_gpa.total_grade += "FAIL"
                        
                mo_dict[str(student.student.reg_no) + "_" + str(subject.id) + "_total_grade"] = g_gpa.total_grade
                mo_dict[str(student.student.reg_no) + "_" + str(subject.id) + "_total_grade_point"] = g_gpa.total_point
                mo_dict[str(student.student.reg_no) + "_" + str(subject.id) + "_total_symbol"] = g_gpa.total_symbol
                total_gp += g_gpa.total_point

                #if this_term.final_term and subject.heavy_weight:
                if int(result_type) == 2:
                    if g_gpa.fail > 0:  # If failed in TH/PR in this subject
                        g_gpa.total_point = 0
                        g_gpa.total_grade = "NG"
                        g_gpa.total_symbol = "NG"
                        fail += 1
                else:
                    if subject.heavy_weight:
                        if float(g_gpa.total_point) < 1.6:
                            fail += 1

                

            mo_gpa = round(total_gp / grade_subjects.count(), 2)
            if int(result_type) == 2 and fail > 0:
                mo_dict[str(student.student.reg_no) + "_gpa"] = 0
            else:
                mo_dict[str(student.student.reg_no) + "_gpa"] = mo_gpa

            term = request.POST.get("term")
            this_term = SchoolTerm.objects.get(id=term)

            if this_term.final_term:
                if  fail > 0:
                    if fail >= 2:
                        mo_dict[str(student.student.reg_no) + "_remarks"] = "Re-examination required for further consideration" #"Failed, Complicated to upgrade."
                        mo_dict[str(student.student.reg_no) + "_fail_status"] = True
                        if pass_fail_filter == 0 or pass_fail_filter == 2:
                           data[sn]["show_data"] = True
                           data[sn]["fail_count"] = fail
                        else:
                           data[sn]["show_data"] = False 
                           data[sn]["fail_count"] = fail
                    else:
                        mo_dict[str(student.student.reg_no) + "_remarks"] = "Can be promoted upon meeting conditions" #"Can not upgrade, Contact for re exam."
                        mo_dict[str(student.student.reg_no) + "_fail_status"] = True
                        if pass_fail_filter == 0 or pass_fail_filter == 2:
                            data[sn]["show_data"] = True
                            data[sn]["fail_count"] = fail
                        else:
                            data[sn]["show_data"] = False 
                            data[sn]["fail_count"] = fail
                    #mo_dict[str(student.student.reg_no) + "_remarks"] = "Upgraded With Condition"
                else:
                    mo_dict[str(student.student.reg_no) + "_remarks"] = "Congratulations, You have been promoted" #"Congratulations, You have been upgraded."
                    mo_dict[str(student.student.reg_no) + "_fail_status"] = False
                    if pass_fail_filter == 0 or pass_fail_filter == 1:
                        data[sn]["show_data"] = True
                        data[sn]["fail_count"] = fail
                    else:
                        data[sn]["show_data"] = False
                        data[sn]["fail_count"] = fail 
            else:
                if fail > 0:
                    mo_dict[str(student.student.reg_no) + "_remarks"] = "Labour Hard"
                    mo_dict[str(student.student.reg_no) + "_fail_status"] = True
                    if pass_fail_filter == 0 or pass_fail_filter == 2:
                        data[sn]["show_data"] = True
                        data[sn]["fail_count"] = fail
                    else:
                        data[sn]["show_data"] = False 
                        data[sn]["fail_count"] = fail
                    #mo_dict[str(student.student.reg_no) + "_remarks"] = "Upgraded With Condition"
                else:
                    mo_dict[str(student.student.reg_no) + "_remarks"] = remarks(mo_gpa)
                    mo_dict[str(student.student.reg_no) + "_fail_status"] = False
                    if pass_fail_filter == 0 or pass_fail_filter == 1:
                        data[sn]["show_data"] = True
                        data[sn]["fail_count"] = fail
                    else:
                        data[sn]["show_data"] = False
                        data[sn]["fail_count"] = fail
                    #mo_dict[str(student.student.reg_no) + "_remarks"] = "Congratulations! Upgraded to Grade EIGHT"
                # data[sn]["mo_dict"] = mo_dict

                # data[sn]["mo_dict"] = mo_dict


        board = True if school.id in exam_board else False 

        if board:
            spacing = 8 - subjects.count()
        elif school.id == 15:
            spacing = 12 - subjects.count()
        else:
            spacing = 10 - subjects.count()
        
        subjectcount = range(spacing)
        

        context = {
            "term_list": term_list,
            "no_of_terms": no_of_terms,
            "no_of_terms_range": range(no_of_terms),
            "no_of_terms_marks_count": no_of_terms * 2,
            "gpa_colspan": 3 + (no_of_terms * 2),
            "school": school,
            "term": this_term,
            "year": this_term.year,
            "data": data,
            "grade": this_grade,
            "section": this_section,
            "subjects": grade_subjects,
            "subjectcount": subjectcount,
            "std_list": data,
            "slogan": slogan,
            "logo": logo,
            "the_space": range(spacing),
            "mo_dict": json.dumps(mo_dict),
            "no_of_subjects": subjects.count(),
            "th_pr_count": subjects.count()*2,
            "board": board,
            "term_acronym": term_acronym,
        }
        if printtype == 2:
            if board:
                return render(request, "panel/grade_sheet_board.html", context)
            else:
                return render(request, "panel/gradesheetall.html", context)
        else:
            if board:
                return render(request, "panel/grade_sheet_board.html", context)
            else:
                return render(request, "panel/gradesheetall.html", context)
    else:
        return HttpResponseRedirect("/panel/")



@login_required
def print_grade_ledger1(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    slogan = " &nbsp; "
    logo = ""
    no_of_terms = 0
    if school.id <= 13:
        # Samata School
        slogan = "Education for all."
        logo = "https://cdn.hamro.com/simsnepal/logos/samata_logo_black.png"
    elif school.id == 14:
        # CSA Montessori
        slogan = "Soaring to Excellence"
        logo = "https://cdn.hamro.com/simsnepal/logos/csa.jpg"
    elif school.id == 15:
        # Paramount Children Academy
        slogan = " &nbsp; "
        logo = "https://cdn.hamro.com/simsnepal/logos/paramount.png"
    elif school.id >= 16 and school.id <= 26:
        # Samata School
        slogan = "Education for all."
        logo = "https://cdn.hamro.com/simsnepal/logos/samata_logo_black.png"

    if request.method == "POST":
        edusession = request.POST.get("edusession")
        term = request.POST.get("term")
        printtype = int(request.POST.get("printtype"))
        grade = request.POST.get("grade2", 0)
        section = request.POST.get("section2", 0)
        # printtype = request.POST.get('printtype', )  # 1 DETAIL 2 SUMMARIZED

        # print("PRINTTYPE", printtype)

        if grade == 0 or grade == None or grade == "":
            return HttpResponse(
                "Sorry! something went wrong. Please take care while submitting data."
            )
        else:
            this_grade = SchoolGrade.objects.get(id=grade)
        this_session = EduSession.objects.get(id=edusession)
        this_term = SchoolTerm.objects.get(id=term)
        term_info = SchoolTerm.objects.get(id=term)

        # subjectcount = Subject.objects.filter(branch=school, grade=this_grade, status=True).count()

        if int(section) > 0:
            this_section = Section.objects.get(id=section)
        else:
            this_section = False
        calculated_rank = ""
        subjects = Subject.objects.filter(
            branch=school, grade=this_grade, status=True
        ).order_by("id")

        grade_subjects = Subject.objects.filter(
            branch=school, grade=this_grade, status=True
        ).order_by("id")

        subjectcount = ""
        for subject in subjects:
            subjectcount += "1"

        if this_section == False:
            students = StudentSession.objects.filter(
                grade=this_grade, status=True, session=this_session
            )

            # calculated_rank = calculaterank2078(school.id, this_session, grade, term)

        else:
            # students = Student.objects.filter(
            #     grade=this_grade, section=this_section, status=True
            # )
            students = StudentSession.objects.filter(grade=this_grade, section=this_section, session=this_session,
                                                     status=True)
            #calculated_rank = calculaterank2078(
            #    school.id, this_session, grade, term, this_section
            #)
            # print(school.id, this_session, grade, term, this_section)
            # print('calculated rank ', calculated_rank)

        term_calculation = ResultManagement.objects.get(school_term=this_term)
        term_list = []
        total_gpa_calculation = dict()

        sn = 0
        data = {}
        mo_dict = dict()
        for key, value in json.loads(term_calculation.term_calculation).items():
            if value > 0:
                no_of_terms += 1
                this_term = SchoolTerm.objects.get(id=key)
                term_list.append(key)

        std_list = dict()
        for student in students:
            sn += 1
            fail = 0
            total_mo = 0
            data[sn] = {}
            data[sn]["reg_no"] = student.student.reg_no
            data[sn]["name"] = student.student.name
            data[sn]["grade"] = student.grade
            data[sn]["section"] = student.section

            for key, value in json.loads(term_calculation.term_calculation).items():
                if value > 0:
                    marks_obtained = MarkObtained.objects.filter(
                        student=student.student, term=key)

                    for mo in marks_obtained:
                        gfm = GradeFullMarks.objects.get(term=mo.term, subject=mo.subject)

                        cal_th_mo = cal_th_fm = cal_th_pm = cal_pr_mo = cal_pr_fm = cal_pr_pm = 0

                        if gfm.th_fm > 0:
                            cal_th_mo = (value / 100) * mo.th_mo
                            cal_th_fm = (value / 100) * gfm.th_fm
                            cal_th_pm = (value / 100) * gfm.th_pm

                        if gfm.pr_fm > 0:
                            cal_pr_mo = (value / 100) * mo.pr_mo
                            cal_pr_fm = (value / 100) * gfm.pr_fm
                            cal_pr_pm = (value / 100) * gfm.pr_pm

                        if str(str(student.student.reg_no) + "_" + str(mo.subject.id)) not in total_gpa_calculation:
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)] = dict()

                        pre_text = str(student.student.reg_no) + "_" + str(mo.subject.id) + "_" + str(mo.term.id)
                        pre_total = str(student.student.reg_no) + "_" + str(mo.subject.id)

                        # FUll Marks
                        if "th_mo" in total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]:
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["th_mo"] += cal_th_mo
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["th_fm"] += cal_th_fm
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["th_pm"] += cal_th_pm
                        else:
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["th_mo"] = cal_th_mo
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["th_fm"] = cal_th_fm
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["th_pm"] = cal_th_pm

                        if "pr_mo" in total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]:
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["pr_mo"] += cal_pr_mo
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["pr_fm"] += cal_pr_fm
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["pr_pm"] += cal_pr_pm
                        else:
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["pr_mo"] = cal_pr_mo
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["pr_fm"] = cal_pr_fm
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["pr_pm"] = cal_pr_pm

                        mo_dict[pre_text + "_th_mo"] = cal_th_mo
                        mo_dict[pre_text + "_pr_mo"] = cal_pr_mo

                        ga_gpa = GradeAndGpa(cal_th_fm, cal_pr_fm, cal_th_mo, cal_pr_mo, mo.subject.heavy_weight)
                        mo_dict[pre_text + "_th_grade"] = ga_gpa.th_grade
                        mo_dict[pre_text + "_pr_grade"] = ga_gpa.pr_grade

                        mo_dict[pre_text + "_th_symbol"] = ga_gpa.th_symbol
                        mo_dict[pre_text + "_pr_symbol"] = ga_gpa.pr_symbol

            total_gp = 0
            for subject in grade_subjects:
                if str(str(student.student.reg_no) + "_" + str(subject.id)) in total_gpa_calculation:
                    th_fm = total_gpa_calculation[str(student.student.reg_no) + "_" + str(subject.id)]["th_fm"]
                else:
                    return HttpResponse(f"For {student.student.reg_no}, Data regarding {subject} is missing.<br/> ",
                                        f"It can be either full marks or just marks.")
                # th_fm = total_gpa_calculation[str(student.student.reg_no) + "_" + str(subject.id)]["th_fm"]
                pr_fm = total_gpa_calculation[str(student.student.reg_no) + "_" + str(subject.id)]["pr_fm"]
                th_mo = total_gpa_calculation[str(student.student.reg_no) + "_" + str(subject.id)]["th_mo"]
                pr_mo = total_gpa_calculation[str(student.student.reg_no) + "_" + str(subject.id)]["pr_mo"]

                print("Subject " + str(subject) + "in grade subjects")
                print(subject, th_fm, pr_fm, th_mo, pr_mo)

                g_gpa = GradeAndGpa(th_fm, pr_fm, th_mo, pr_mo, 1)
                mo_dict[str(student.student.reg_no) + "_" + str(subject.id) + "_total_grade"] = g_gpa.total_grade
                mo_dict[str(student.student.reg_no) + "_" + str(subject.id) + "_total_grade_point"] = g_gpa.total_point
                mo_dict[str(student.student.reg_no) + "_" + str(subject.id) + "_total_symbol"] = g_gpa.total_symbol

                total_gp += g_gpa.total_point

                #if g_gpa.fail:
                #    fail += 1

                total_mo += g_gpa.total_mo

            #for subject in grade_subjects:
            #    if  mo_dict[str(student.student.reg_no) + "_" + str(subject.id) + "_total_grade_point"] < 1.6:
            #        fail +=1

            mo_gpa = round(total_gp / grade_subjects.count(), 2)
            mo_dict[str(student.student.reg_no) + "_gpa"] = mo_gpa
          

            if term_info.final_term:
                if  fail > 0:
                    if fail >= 2:
                        mo_dict[str(student.student.reg_no) + "_remarks"] = "Re-examination required for further consideration" #"Failed, Complicated to upgrade."
                    else:
                        mo_dict[str(student.student.reg_no) + "_remarks"] = "Can be promoted upon meeting conditions" #"Can not upgrade, Contact for re exam."
                else:
                    mo_dict[str(student.student.reg_no) + "_remarks"] = "Congratulations, You have been promoted" #"Congratulations, You have been upgraded."

            else:
                if fail > 0:
                    mo_dict[str(student.student.reg_no) + "_remarks"] = "Labour Hard"
                else: 
                    mo_dict[str(student.student.reg_no) + "_remarks"] = remarks(mo_gpa)
                    std_list[student.student.reg_no] = total_mo
            # data[sn]["mo_dict"] = mo_dict

            print(student.student.reg_no, fail)

        sorted_d = sorted(std_list.items(), key=lambda x: x[1], reverse=True)

        high_mark = 0
        stat_rank = 0
        sorted_rank = []
        std_dict = dict()
        for calc in sorted_d:
            if calc[1] == high_mark:
                high_mark = calc[1]
                reg_no = calc[0]
                std_dict[reg_no] = stat_rank
            else:
                stat_rank += 1
                high_mark = calc[1]
                reg_no = calc[0]
                std_dict[reg_no] = stat_rank

        for rank_reg_no in std_dict:
            mo_dict[str(rank_reg_no)+"_rank"] = std_dict[rank_reg_no]

        spacing = 13 - subjects.count()
        subjectcount = range(spacing)

        board = True if school.id in exam_board else False

        context = {
            "term_list": term_list,
            "no_of_terms": no_of_terms,
            "no_of_terms_range": range(no_of_terms),
            "no_of_terms_marks_count": no_of_terms * 2,
            "gpa_colspan": 3 + (no_of_terms * 2),
            "school": school,
            "term": term_info,
            "year": this_term.year,
            "data": data,
            "grade": this_grade,
            "section": this_section,
            "subjects": grade_subjects,
            "subjectcount": subjectcount,
            "std_list": data,
            "slogan": slogan,
            "logo": logo,
            "the_space": range(spacing),
            "mo_dict": json.dumps(mo_dict),
            "no_of_subjects": subjects.count(),
            "th_pr_count": subjects.count()*2,
            "board": board,
        }
        if printtype == 2:
            return render(request, "panel/grade_ledger_all.html", context)
        else:
            return render(request, "panel/grade_ledger_all.html", context)
    else:
        return HttpResponseRedirect("/panel/")


@login_required
def print_grade_ledger(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    slogan = " &nbsp; "
    logo = ""
    no_of_terms = 0
    if school.id <= 13:
        # Samata School
        slogan = "Education for all."
        logo = "https://cdn.hamro.com/simsnepal/logos/samata_logo_black.png"
    elif school.id == 14:
        # CSA Montessori
        slogan = "Soaring to Excellence"
        logo = "https://cdn.hamro.com/simsnepal/logos/csa.jpg"
    elif school.id == 15:
        # Paramount Children Academy
        slogan = " &nbsp; "
        logo = "https://cdn.hamro.com/simsnepal/logos/paramount.png"
    elif school.id >= 16 and school.id <= 26:
        # Samata School
        slogan = "Education for all."
        logo = "https://cdn.hamro.com/simsnepal/logos/samata_logo_black.png"

    if request.method == "POST":
        edusession = request.POST.get("edusession")
        term = request.POST.get("term")
        printtype = int(request.POST.get("printtype"))
        grade = request.POST.get("grade2", 0)
        section = request.POST.get("section2", 0)
        data_filter = request.POST.get("filter", 0)
        data_order = request.POST.get("data_order", 1)

        grading_type = int(request.POST.get("grading_type"))

        print("DATA ORDER: "+str(data_order)+"data_filter: "+str(data_filter));
        # printtype = request.POST.get('printtype', )  # 1 DETAIL 2 SUMMARIZED

        # print("PRINTTYPE", printtype)

        if grade == 0 or grade == None or grade == "":
            return HttpResponse(
                "Sorry! something went wrong. Please take care while submitting data."
            )
        else:
            this_grade = SchoolGrade.objects.get(id=grade)
        this_session = EduSession.objects.get(id=edusession)
        this_term = SchoolTerm.objects.get(id=term)

        # subjectcount = Subject.objects.filter(branch=school, grade=this_grade, status=True).count()

        if int(section) > 0:
            this_section = Section.objects.get(id=section)
        else:
            this_section = False
        calculated_rank = ""
        subjects = Subject.objects.filter(
            session=this_session, branch=school, grade=this_grade, status=True
        ).order_by("id")

        grade_subjects = Subject.objects.filter(
            session=this_session, branch=school, grade=this_grade, status=True
        ).order_by("id")

        subjectcount = ""
        for subject in subjects:
            subjectcount += "1"

        if this_section == False:
            if data_order == 1:
                students = StudentSession.objects.filter(session=this_session, grade=this_grade, status=True).order_by('student__reg_no')
            else:
                students = StudentSession.objects.filter(session=this_session, grade=this_grade, status=True).order_by('roll_no')

            # calculated_rank = calculaterank2078(school.id, this_session, grade, term)

        else:
            # students = Student.objects.filter(
            #     grade=this_grade, section=this_section, status=True
            # )
            if data_order == 1:
                students = StudentSession.objects.filter(grade=this_grade, section=this_section, session=this_session,
                                                     status=True).order_by('student__reg_no')
            else:
                students = StudentSession.objects.filter(grade=this_grade, section=this_section, session=this_session,
                                                     status=True).order_by('roll_no')
#            calculated_rank = calculaterank2078(
#                school.id, this_session, grade, term, this_section
#            )
            # print(school.id, this_session, grade, term, this_section)
            # print('calculated rank ', calculated_rank)

        term_calculation = ResultManagement.objects.get(school_term=this_term)
        term_list = []
        total_gpa_calculation = dict()

        sub_total_fm_pm = dict()

        term_acronym = dict()

        sn = 0
        data = {}
        mo_dict = dict()
        final_term_count = 0
        for key, value in json.loads(term_calculation.term_calculation).items():
            if value > 0:
                no_of_terms += 1
                this_term = SchoolTerm.objects.get(id=key)
                term_acronym[this_term.name_in_short] = this_term.term_name
                term_list.append(key)
        std_list = dict()
        for student in students:
            sn += 1
            fail = 0
            total_mo = 0
            data[sn] = {}
            data[sn]["session_detail"] = student
            data[sn]["student_detail"] = student.student
            data[sn]["reg_no"] = student.student.reg_no
            data[sn]["name"] = student.student.name
            data[sn]["grade"] = student.grade
            data[sn]["section"] = student.section
            data[sn]["roll_no"] = student.roll_no

            for key, value in json.loads(term_calculation.term_calculation).items():
                if value > 0:
                    marks_obtained = MarkObtained.objects.filter(
                        student=student.student, term=key)

                    for mo in marks_obtained:
                        gfm = GradeFullMarks.objects.get(term=mo.term, subject=mo.subject)
                        sub_heavy_weight = Subject.objects.get(id=mo.subject.id)
				
                        cal_th_mo = cal_th_fm = cal_th_pm = cal_pr_mo = cal_pr_fm = cal_pr_pm = 0

                        if gfm.th_fm > 0:
                            cal_th_mo = (value / 100) * mo.th_mo
                            cal_th_fm = (value / 100) * gfm.th_fm
                            cal_th_pm = (value / 100) * gfm.th_pm

                            if str(mo.subject.id)+"th_fm" not in sub_total_fm_pm:
                                sub_total_fm_pm[str(mo.subject.id)+"th_fm"] = cal_th_fm
                                sub_total_fm_pm[str(mo.subject.id)+"pr_fm"] = 0

                        if gfm.pr_fm > 0:
                            cal_pr_mo = (value / 100) * mo.pr_mo
                            cal_pr_fm = (value / 100) * gfm.pr_fm
                            cal_pr_pm = (value / 100) * gfm.pr_pm

                            if str(mo.subject.id)+"pr_fm" not in sub_total_fm_pm:
                                sub_total_fm_pm[str(mo.subject.id)+"pr_fm"] = cal_pr_fm

                        if str(str(student.student.reg_no) + "_" + str(mo.subject.id)) not in total_gpa_calculation:
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)] = dict()

                        pre_text = str(student.student.reg_no) + "_" + str(mo.subject.id) + "_" + str(mo.term.id)
                        pre_total = str(student.student.reg_no) + "_" + str(mo.subject.id)

                        # FUll Marks
                        if "th_mo" in total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]:
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["th_mo"] += cal_th_mo
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["th_fm"] += cal_th_fm
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["th_pm"] += cal_th_pm
                        else:
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["th_mo"] = cal_th_mo
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["th_fm"] = cal_th_fm
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["th_pm"] = cal_th_pm

                        if "pr_mo" in total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]:
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["pr_mo"] += cal_pr_mo
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["pr_fm"] += cal_pr_fm
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["pr_pm"] += cal_pr_pm
                        else:
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["pr_mo"] = cal_pr_mo
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["pr_fm"] = cal_pr_fm
                            total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]["pr_pm"] = cal_pr_pm

                        mo_dict[pre_text + "_th_mo"] = cal_th_mo
                        mo_dict[pre_text + "_pr_mo"] = cal_pr_mo

                        if grading_type == 2:
                            ga_gpa = GradeAndGpaNew(cal_th_fm, cal_pr_fm, cal_th_mo, cal_pr_mo, mo.subject.heavy_weight,result_type=grading_type)
                            mo_dict[pre_text + "_th_grade"] = ga_gpa.th_grade
                            mo_dict[pre_text + "_pr_grade"] = ga_gpa.pr_grade
                            mo_dict[pre_text + "_th_symbol"] = ga_gpa.th_symbol
                            mo_dict[pre_text + "_pr_symbol"] = ga_gpa.pr_symbol
                        else:
                            ga_gpa = GradeAndGpa(cal_th_fm, cal_pr_fm, cal_th_mo, cal_pr_mo, mo.subject.heavy_weight)
                            mo_dict[pre_text + "_th_grade"] = ga_gpa.th_grade
                            mo_dict[pre_text + "_th_symbol"] = ga_gpa.th_symbol
                            mo_dict[pre_text + "_pr_grade"] = ga_gpa.pr_grade
                            mo_dict[pre_text + "_pr_symbol"] = ga_gpa.pr_symbol
                            mo_dict[pre_text + "_total_symbol"] = ga_gpa.total_symbol

                        #if sub_heavy_weight.heavy_weight and 
                        if mo.term.final_term:
                            final_term_count +=1

                        

            #for key, st in sub_total_fm_pm:
                #print(key, st)
            
            
            total_gp = 0
            for subject in grade_subjects:
                if str(str(student.student.reg_no) + "_" + str(subject.id)) in total_gpa_calculation:
                    th_fm = total_gpa_calculation[str(student.student.reg_no) + "_" + str(subject.id)]["th_fm"]
                    pr_fm = total_gpa_calculation[str(student.student.reg_no) + "_" + str(subject.id)]["pr_fm"]
                    th_mo = total_gpa_calculation[str(student.student.reg_no) + "_" + str(subject.id)]["th_mo"]
                    pr_mo = total_gpa_calculation[str(student.student.reg_no) + "_" + str(subject.id)]["pr_mo"]
                else:
                    #return HttpResponse(f"For {student.student.reg_no}, Data regarding {subject} is missing. ",
                    #                    f"It can be either full marks or just marks.")
                    th_fm = 0 #sub_total_fm_pm[str(subject.id)+"th_fm"]
                    pr_fm = 0 #sub_total_fm_pm[str(subject.id)+"pr_fm"]
                    th_mo = 0 
                    pr_mo = 0
                    #pass

                # th_fm = total_gpa_calculation[str(student.student.reg_no) + "_" + str(subject.id)]["th_fm"]
                

                print("Subject " + str(subject) + "in grade subjects")
                print(subject, th_fm, pr_fm, th_mo, pr_mo)
                print("HEAVY WEIGHT: ")
                print(subject.heavy_weight)

                g_gpa = GradeAndGpa(th_fm, pr_fm, th_mo, pr_mo, subject.heavy_weight)
                #if this_term.final_term and subject.heavy_weight:
                    #if float(g_gpa.total_point) <1.6:
                        #fail += 1
                        #g_gpa.total_grade += "FAIL"
                        
                mo_dict[str(student.student.reg_no) + "_" + str(subject.id) + "_total_grade"] = g_gpa.total_grade
                mo_dict[str(student.student.reg_no) + "_" + str(subject.id) + "_total_grade_point"] = g_gpa.total_point
                mo_dict[str(student.student.reg_no) + "_" + str(subject.id) + "_total_symbol"] = g_gpa.total_symbol
                total_gp += g_gpa.total_point

                if this_term.final_term and subject.heavy_weight:
                    if float(g_gpa.total_point) <1.6:
                        fail += 1

                elif not this_term.final_term and subject.heavy_weight:
                    if float(g_gpa.total_point) <1.6:
                        fail += 1

                total_mo += g_gpa.total_mo
            
            mo_gpa = round(total_gp / grade_subjects.count(), 2)
            if int(grading_type) == 2 and fail > 0:
                mo_dict[str(student.student.reg_no) + "_gpa"] = 0
            else:
                mo_dict[str(student.student.reg_no) + "_gpa"] = mo_gpa

            this_term = SchoolTerm.objects.get(id=term)
            data[sn]["hide"] = False
            if this_term.final_term:
                if  fail > 0:
                    data[sn]["fail"] = True
                    if fail >= 2:
                        mo_dict[str(student.student.reg_no) + "_remarks"] = "Re-examination required for further consideration" #"Failed, Complicated to upgrade."
                    else:
                        mo_dict[str(student.student.reg_no) + "_remarks"] = "Can be promoted upon meeting conditions" #"Can not upgrade, Contact for re exam."
                    #mo_dict[str(student.student.reg_no) + "_remarks"] = "Upgraded With Condition"
                    if data_filter == 1:
                        data[sn]["hide"] = True
                    elif data_filter == 2:
                        data[sn]["hide"] = False
                else:
                    data[sn]["fail"] = False
                    
                    if data_filter == 2:
                        data[sn]["hide"] = True
                    elif data_filter == 1:
                        data[sn]["hide"] = "False 3"    
                    mo_dict[str(student.student.reg_no) + "_remarks"] = "Congratulations, You have been promoted" #"Congratulations, You have been upgraded."
                    std_list[student.student.reg_no] = total_mo
            else:
                if fail > 0:
                    data[sn]["fail"] = True
                    if data_filter == 1:
                        data[sn]["hide"] = True
                    elif data_filter == 2:
                        data[sn]["hide"] = False
                    mo_dict[str(student.student.reg_no) + "_remarks"] = "Labour Hard"
                    #mo_dict[str(student.student.reg_no) + "_remarks"] = "Upgraded With Condition"
                else:
                    data[sn]["fail"] = False
                    if data_filter == 2:
                        data[sn]["hide"] = True
                    elif data_filter == 1:
                        data[sn]["hide"] = "False 3"       
                    mo_dict[str(student.student.reg_no) + "_remarks"] = remarks(mo_gpa)
                    std_list[student.student.reg_no] = total_mo
                    #mo_dict[str(student.student.reg_no) + "_remarks"] = "Congratulations! Upgraded to Grade EIGHT"
                # data[sn]["mo_dict"] = mo_dict

                # data[sn]["mo_dict"] = mo_dict

        sorted_d = sorted(std_list.items(), key=lambda x: x[1], reverse=True)
        high_mark = 0
        stat_rank = 0
        sorted_rank = []
        std_dict = dict()

        for calc in sorted_d:
            if calc[1] == high_mark:
                high_mark = calc[1]
                reg_no = calc[0]
                std_dict[reg_no] = stat_rank
            else:
                stat_rank += 1
                high_mark = calc[1]
                reg_no = calc[0]
                std_dict[reg_no] = stat_rank

        for rank_reg_no in std_dict:
            mo_dict[str(rank_reg_no)+"_rank"] = std_dict[rank_reg_no]

        board = True if school.id in exam_board else False 

        if board:
            spacing = 8 - subjects.count()
        else:
            spacing = 10 - subjects.count()
        subjectcount = range(spacing)

        this_term = SchoolTerm.objects.get(id=term)

        context = {
            "term_list": term_list,
            "no_of_terms": no_of_terms,
            "no_of_terms_range": range(no_of_terms),
            "no_of_terms_marks_count": no_of_terms * 2,
            "gpa_colspan": 3 + (no_of_terms * 2),
            "school": school,
            "term": this_term,
            "year": this_term.year,
            "data": data,
            "grade": this_grade,
            "section": this_section,
            "subjects": grade_subjects,
            "subjectcount": subjectcount,
            "std_list": data,
            "slogan": slogan,
            "logo": logo,
            "the_space": range(spacing),
            "mo_dict": json.dumps(mo_dict),
            "no_of_subjects": subjects.count(),
            "th_pr_count": subjects.count()*2,
            "board": board,
            "term_acronym": term_acronym,
        }
        if this_term.final_term:
            return render(request, "panel/grade_ledger_all_final.html", context)
        else:
            if printtype == 2:
                return render(request, "panel/grade_ledger_all.html", context)
            else:
                return render(request, "panel/grade_ledger_all.html", context)
    else:
        return HttpResponseRedirect("/panel/")

@login_required
def addAttendance(request, grade=None):
    # print(request.POST)
    this_session = get_current_session()
    if request.method == 'POST':
        grade = request.POST.get('grade')
        grade = SchoolGrade.objects.get(id=grade)
        session = this_session
        no_of_school_days = int(request.POST.get('no_of_school_days'))
        data_type = request.POST.get('data_type')
        students = StudentSession.objects.filter(grade=grade, session=this_session, status=True)
        #students = StudentSession.objects.filter(grade=gradelevel.id, session=this_session, status=True)
        term = request.POST.get('term')
        this_term = SchoolTerm.objects.get(id=term)
        thou = 1000
        for student in students:
            try:
                std_att = int(request.POST.get(str(student.student.reg_no)).strip())
            except:
                std_att = 0
            #std_att = request.POST.get(str(student.student.reg_no)).strip()
            #std_att = std_att.trim()
            print(student.student,std_att)
            #if std_att == '':
            #    std_att = 0
            #else:
            #    std_att = int(std_att)
                #try:
                #    std_att = int(std_att)
                #except:
                #    std_att = 0
            if data_type == 'present':
                school_days = no_of_school_days
                present_days = std_att
                absent_days = no_of_school_days - std_att
            else:
                school_days = no_of_school_days
                present_days = no_of_school_days - std_att
                absent_days = std_att

            # print('Student: ', student, 'Session: ', session, 'Grade: ', grade, 'School Days: ', no_of_school_days, 'Present Days: ', present_days, 'Absent Days: ', absent_days)
            try:
                created = Attendance.objects.get(
                    reg_no=student.student,
                    grade=grade,
                    session=session,
                    term = this_term,
                )
                created.no_of_school_days = no_of_school_days
                created.no_of_present_days = present_days
                created.no_of_absent_days = absent_days
                created.save()

            except:
                attend = Attendance()
                attend.reg_no = student.student
                attend.grade = grade
                attend.term = this_term
                attend.session = session
                attend.no_of_school_days = no_of_school_days
                attend.no_of_present_days = present_days
                attend.no_of_absent_days = absent_days
                attend.save()

            # print(created)
        # print(type(grade))
        return HttpResponseRedirect('/panel/grades/' + str(grade.id) + '/')
    else:
        return HttpResponseRedirect('/panel/')

@login_required
def add_house(request, house=None):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    
    # print(request.POST)
    if request.method == 'POST':
        name = request.POST.get('name')
        if 'update' in request.POST:
            house_id = request.POST.get('id')
            new_house = House.objects.get(id=int(house_id))
            new_house.name = name
            new_house.save()
        else:
            new_house = House()
            new_house.school = school
            new_house.name = name
            new_house.save()
        return HttpResponseRedirect('/panel/house/')
    else:
        houses = House.objects.filter(school=school)
        if house is not None:
            this_house = House.objects.get(id=house)
        else:
            this_house = None
        context = {
        'school': school,
        'house': houses,
        'this_house': this_house,
        }
        return render(request, "panel/add_house.html", context)


@login_required
def new_private_result_2080(request, regno):
    this_session = get_current_session()
    no_of_terms = 0
    fail = 0
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    student = Student.objects.get(reg_no = int(regno))

    if StudentSession.objects.filter(session=this_session, student=student, status=True).count() == 1:
        #student = Student.objects.get(reg_no=int(regno))

        if student.school != school:
            message = (
                    "Sorry you are not allowed to view result of student from another school."
            )
            context = {"message": message}
            return render(request, "panel/resultform.html", context)

        result_status = LiveResult.objects.get(school=student.school)
        grade_list = json.loads(result_status.grade_list)
        term = result_status.term
        this_term = SchoolTerm.objects.get(id=term)
        std_session = StudentSession.objects.get(session=this_session, student=student, status=True)

        if std_session.grade.id not in grade_list:
            message = (
                    "Sorry the result of Grade "
                    + std_session.grade.grade_name
                    + " has not been published yet. For more information please contact on School."
            )
            context = {"message": message}
            return render(request, "panel/resultform.html", context)
    else:
        context = {
            "message": "Sorry student with the registration number could not be found."
        }
        return render(request, "panel/resultform.html", context)

    if student.school.id <= 13:
        # Samata School
        slogan = "Education for all."
        logo = "https://cdn.hamro.com/simsnepal/logos/samata_logo_black.png"
    elif student.school.id == 14:
        # CSA Montessori
        slogan = "Soaring to Excellence"
        logo = "https://cdn.hamro.com/simsnepal/logos/csa.jpg"
    elif student.school.id == 15:
        # Paramount Children Academy
        slogan = " &nbsp; "
        logo = "https://cdn.hamro.com/simsnepal/logos/paramount.png"
    elif student.school.id >= 16 and student.school.id <= 26:
        # Samata School
        slogan = "Education for all."
        logo = "https://cdn.hamro.com/simsnepal/logos/samata_logo_black.png"
    # sc
    mo_dict = dict()
    grade_subjects = Subject.objects.filter(session=this_session,
        grade=std_session.grade, branch=student.school, status=True
    )
    all_students = StudentSession.objects.filter(grade=std_session.grade, status=1)
    total_student = all_students.count()

    # Getting Term Calculation
    term_calculation = ResultManagement.objects.get(school_term=this_term)
    term_list = []
    total_gpa_calculation = dict()
    # total_gpa_calculation[student.reg_no] = dict()
    for key, value in json.loads(term_calculation.term_calculation).items():
        if value > 0:
            no_of_terms += 1
            this_term = SchoolTerm.objects.get(id=key)
            # term_list.append(this_term)
            term_list.append(key)

            print("Percent Calculation")

            marks_obtained = MarkObtained.objects.filter(
                student=student, term=key)

            for mo in marks_obtained:
                print("TERM ", mo.term.id)
                print("SUBJECT \t", mo.subject.id, "NAME: \t", mo.subject)
                print("Percentage ", value)
                # Getting Fullmark of the term
                gfm = GradeFullMarks.objects.get(term=mo.term, subject=mo.subject)
                print(gfm, gfm.th_fm, gfm.pr_fm)
                print("+++++++")

                # Calculating marks according to Percentage
                if gfm.th_fm > 0:
                    cal_th_mo = (value/100) * mo.th_mo
                    cal_th_fm = (value/100) * gfm.th_fm
                    cal_th_pm = (value/100) * gfm.th_pm
                else:
                    cal_th_mo = 0
                    cal_th_fm = 0
                    cal_th_pm = 0

                if gfm.pr_fm > 0:
                    cal_pr_mo = (value/100) * mo.pr_mo
                    cal_pr_fm = (value/100) * gfm.pr_fm
                    cal_pr_pm = (value/100) * gfm.pr_pm
                else:
                    cal_pr_mo = 0
                    cal_pr_fm = 0
                    cal_pr_pm = 0

                if str(str(student.reg_no)+"_"+str(mo.subject.id)) not in total_gpa_calculation:
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)] = dict()

                pre_text = str(student.reg_no)+"_"+str(mo.subject.id)+"_"+str(mo.term.id)
                pre_total = str(student.reg_no)+"_"+str(mo.subject.id)

                # FUll Marks
                if "th_mo" in total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]:
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["th_mo"] += cal_th_mo
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["th_fm"] += cal_th_fm
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["th_pm"] += cal_th_pm
                else:
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["th_mo"] = cal_th_mo
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["th_fm"] = cal_th_fm
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["th_pm"] = cal_th_pm

                if "pr_mo" in total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]:
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["pr_mo"] += cal_pr_mo
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["pr_fm"] += cal_pr_fm
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["pr_pm"] += cal_pr_pm
                else:
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["pr_mo"] = cal_pr_mo
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["pr_fm"] = cal_pr_fm
                    total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["pr_pm"] = cal_pr_pm

                mo_dict[pre_text + "_th_mo"] = cal_th_mo
                mo_dict[pre_text + "_pr_mo"] = cal_pr_mo

                ga_gpa = GradeAndGpa(cal_th_fm, cal_pr_fm, cal_th_mo, cal_pr_mo, mo.subject.heavy_weight)
                mo_dict[pre_text + "_th_grade"] = ga_gpa.th_grade
                mo_dict[pre_text + "_th_symbol"] = ga_gpa.th_symbol
                mo_dict[pre_text + "_pr_grade"] = ga_gpa.pr_grade
                mo_dict[pre_text + "_pr_symbol"] = ga_gpa.pr_symbol
                # print(ga_gpa)
                # attrs = vars(ga_gpa)
                # print(', '.join("%s: %s" % item for item in attrs.items()))

                # mo_dict[pre_total + "_total_grade"] = "A"
                # mo_dict[pre_total + "_total_grade_point"] = 4

    # Calculating GradePoint of each subject
    # for key, value in json.loads(term_calculation.term_calculation).items():
    #     if value > 0:
    #         # for key, value in mo_dict:
    #         #     print(key,value)
    #         print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    #         print(mo_dict)
    total_gp = 0
    for subject in grade_subjects:
        if str(str(student.reg_no) + "_" + str(subject.id)) in total_gpa_calculation:
            th_fm = total_gpa_calculation[str(student.reg_no) + "_" + str(subject.id)]["th_fm"]
        else:
            return HttpResponse(f"For {student.reg_no}, Data regarding {subject} is missing. Subject id is {subject.id} year is {this_session} grade is {std_session.grade} ",
                                f"It can be either full marks or just marks.")
        # th_fm = total_gpa_calculation[str(student.reg_no)+"_"+str(mo.subject.id)]["th_fm"]
        pr_fm = total_gpa_calculation[str(student.reg_no) + "_" + str(subject.id)]["pr_fm"]
        th_mo = total_gpa_calculation[str(student.reg_no) + "_" + str(subject.id)]["th_mo"]
        pr_mo = total_gpa_calculation[str(student.reg_no) + "_" + str(subject.id)]["pr_mo"]
        print(th_fm, pr_fm, th_mo, pr_mo, 1)
        
        g_gpa = GradeAndGpa(th_fm, pr_fm, th_mo, pr_mo, 1)
        mo_dict[str(student.reg_no)+"_"+str(subject.id)+"_total_grade"] = g_gpa.total_grade
        mo_dict[str(student.reg_no)+"_"+str(subject.id)+"_total_grade_point"] = g_gpa.total_point
        mo_dict[str(student.reg_no)+"_"+str(subject.id)+"_total_symbol"] = g_gpa.total_symbol

        total_gp +=g_gpa.total_point

    mo_gpa = round(total_gp/grade_subjects.count(), 2)
    if int(result_tye) == 2:
        if true:
            mo_dict[str(student.reg_no)+"_gpa"] = 0.0
    else:
        mo_dict[str(student.reg_no)+"_gpa"] = mo_gpa
    
    if fail > 0:
        mo_dict[str(student.reg_no) + "_remarks"] = "Labour Hard"
    else:
        mo_dict[str(student.reg_no) + "_remarks"] = remarks(mo_gpa)
                
    student_session = StudentSession.objects.get(student=int(regno), status=True)
    the_space = ""
    spacing = 11 - grade_subjects.count()

    subjectcount = range(spacing)
    for i in range(spacing):
        the_space += "a"
    context = {
        "term_list": term_list,
        "no_of_terms": no_of_terms,
        "no_of_terms_range": range(no_of_terms),
        "no_of_terms_marks_count": no_of_terms*2,
        "gpa_colspan": 3 + (no_of_terms*2),
        "year": this_year,
        "term": this_term,
        "student": student_session,
        "grade_subjects": grade_subjects,
        "mo_dict": json.dumps(mo_dict),
        "the_space": the_space,
        "slogan": slogan,
        "logo": logo,
        "school": school,
        "the_space": range(spacing),
    }
    return render(request, "panel/gradesheet_private.html", context)

@login_required
def print_homeworks(request):
    user = request.user
    try:
        branch_user = BranchUser.objects.get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )
    grade_level = GradeLevel.objects.all()
    school_branch = SchoolBranch.objects.get(id=branch_user.school_id)
    grades = SchoolGrade.objects.filter(school=school_branch).order_by("id")
    teachers = Teacher.objects.filter(added_by=request.user)
    current_session = get_current_session()
    # Filter homeworks for today or newer (recently added)
    from datetime import date
    today = date.today()
    homeworks = Homework.objects.filter(session=current_session, grade__school=school_branch).order_by('-date', 'grade')
    subjects = Subject.objects.filter(session=current_session, branch=school_branch, status=True)

    gs = {}
    for subject in subjects:
        gs[str(subject.id)] = subject.subject

    # Group homeworks by date
    from collections import defaultdict
    home_works_by_date = defaultdict(list)

    for item in homeworks:
        # Use Gregorian date for grouping and ordering
        date_key = item.date.isoformat() if item.date else str(item.nepali_date)
        hw_data = {
            "id": item.id,
            "grade": item.grade,
            "section": item.section,
            "hw": {},
            "nepali_date": str(item.nepali_date),
            "date": date_key,
        }

        hw_items = json.loads(item.homework)
        for key, value in hw_items.items():
            hw_data["hw"][str(gs[key])] = value

        home_works_by_date[date_key].append(hw_data)

    # Convert to list and keep dates in order (sorted by Gregorian date descending)
    dates_ordered = sorted(home_works_by_date.keys(), reverse=True)
    home_works_list = [{"date": date, "nepali_date": next((hw["nepali_date"] for hw in home_works_by_date[date]), ""), "homeworks": home_works_by_date[date]} for date in dates_ordered]

    subject_access = dict()
    for teacher in teachers:
        subject_access[teacher.id] = dict()

    # Check if user wants to see everything for printing
    show_all = request.GET.get('all', 'false').lower() == 'true'
    
    if show_all:
        page_obj = None
        homework_days = home_works_list
    else:
        # Pagination - one day per page
        page_num = request.GET.get('page', 1)
        paginator = Paginator(home_works_list, 1)  # 1 day per page
        try:
            page_obj = paginator.page(page_num)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)
        
        # In single-page mode, homework_days will just have one day entry
        homework_days = page_obj.object_list

    today_nepali_date = str(nepali_datetime.date.today())
    context = {
        'teachers': teachers,
        'homework_days': homework_days,
        'page_obj': page_obj,
        'show_all': show_all,
        'branch_user': branch_user,
        'grade_level': grade_level,
        'grades': grades,
        'school_branch': school_branch,
        "subject_access": subject_access,
        "school": school_branch,
        "today_nepali_date": today_nepali_date,
    }
    return render(request, "panel/homeworks.html", context)
    
@login_required
def assign_house(request):
    this_session = get_current_session()
    if request.method == 'POST':
        students = request.POST.getlist('students')  # Assuming 'students' is the name of the select fields for students' registration numbers
        houses = request.POST.getlist('houses')  # Assuming 'houses' is the name of the select fields for house IDs
        redurl = request.POST.get('redurl', '/')  # Get the 'redurl' value from the form data
        gradelevel = request.POST.get('gradelevel')
        gradelevel = SchoolGrade.objects.get(id=int(gradelevel))

        students = StudentSession.objects.filter(session=this_session, grade=gradelevel)

        for student in students:
            # print(dir(student))
            print(student)
            if(request.POST.get(student.student.reg_no)):
                house = request.POST.get(student.student.reg_no)
                house = House.objects.get(id=house)
                this_student = Student.objects.get(reg_no=student.student.reg_no)
                this_student.house = house
                this_student.save()
        
        # for student_reg_no, house_id in zip(students, houses):
        #     # Retrieve the student object
        #     student = Student.objects.get(reg_no=student_reg_no)
        #     # Assign the selected house to the student
        #     student.house_id = house_id
        #     # Save the changes to the student
        #     student.save()
        
        # Redirect to the URL specified in 'redurl' or default to '/'
        return redirect(redurl)

    # Handle GET request or render initial form
    else:
        # Render your initial form here if needed
        return HttpResponse("Sorry something went wrong")

@login_required
def assign_section(request):
    this_session = get_current_session()
    if request.method == 'POST':
        students = request.POST.getlist('students')  # Assuming 'students' is the name of the select fields for students' registration numbers
        sections = request.POST.getlist('sections')  # Assuming 'sections' is the name of the select fields for section IDs
        redurl = request.POST.get('redurl', '/')  # Get the 'redurl' value from the form data
        gradelevel_id = request.POST.get('gradelevel')

        try:
            gradelevel = SchoolGrade.objects.get(id=int(gradelevel_id))
        except SchoolGrade.DoesNotExist:
            return HttpResponse("Grade level not found")

        # Ensure that `this_session` is defined somewhere in your view or passed to it.
        students = StudentSession.objects.filter(grade=gradelevel.id, session=this_session, status=True)

        for student in students:
            try:
                section_id = request.POST.get(student.student.reg_no)
                if section_id not in [0]:
                    section = Section.objects.get(id=int(section_id))
                    student_session = StudentSession.objects.get(student=student.student, grade=gradelevel, status=True, session=this_session)
                    student_session.section = section
                    student_session.save()
                    print(f"Updated student {student.student.reg_no} to section {section.name}")
            except Section.DoesNotExist:
                print(f"Section with id {section_id} does not exist")
            except StudentSession.DoesNotExist:
                print(f"Student session for student {student.student.reg_no} does not exist")
            except Exception as e:
                print(f"Error updating student {student.student.reg_no}: {e}")

        return redirect(redurl)

    else:
        return HttpResponse("Sorry, something went wrong")
    
# @login_required
# def assign_section(request):
#     if request.method == 'POST':
#         students = request.POST.getlist('students')  # Assuming 'students' is the name of the select fields for students' registration numbers
#         sections = request.POST.getlist('sections')  # Assuming 'houses' is the name of the select fields for house IDs
#         redurl = request.POST.get('redurl', '/')  # Get the 'redurl' value from the form data
#         gradelevel = request.POST.get('gradelevel')
#         gradelevel = SchoolGrade.objects.get(id=int(gradelevel))

#         #students = StudentSession.objects.filter(session=this_session, grade=gradelevel, status=True)
#         students = StudentSession.objects.filter(grade=gradelevel.id, session=this_session, status=True) #.order_by("section","roll_no")

#         for student in students:
#             # print(dir(student))
#             print('STUDENT: ',student, student.student)
#             if(request.POST.get(student.student.reg_no)):
#                 section = int(request.POST.get(student.student.reg_no))
#                 print(student.student.reg_no, section)
#                 if section:
#                     this_section = Section.objects.get(id=section)
#                     this_student = StudentSession.objects.get(student=student.student.reg_no, grade=gradelevel, status=True, session=this_session)
#                     print(this_student)
#                     this_student.section = this_section
#                     this_student.save()
#                     print(student.student.reg_no, this_section, this_student)
#                     print("=================")

        
#         # for student_reg_no, house_id in zip(students, houses):
#         #     # Retrieve the student object
#         #     student = Student.objects.get(reg_no=student_reg_no)
#         #     # Assign the selected house to the student
#         #     student.house_id = house_id
#         #     # Save the changes to the student
#         #     student.save()
        
#         # Redirect to the URL specified in 'redurl' or default to '/'
#         return redirect(redurl)

#     # Handle GET request or render initial form
#     else:
#         # Render your initial form here if needed
#         return HttpResponse("Sorry something went wrong")

@login_required
def new_session(request):
    this_year = 2083
    new_session, created = EduSession.objects.get_or_create(year=str(this_year), defaults={'status': True})
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    grade_level = GradeLevel.objects.all()
    school_branch = SchoolBranch.objects.get(id=branchuser.school_id)
    grades = SchoolGrade.objects.filter(school=school_branch).order_by("id")
    teachers = Teacher.objects.filter(added_by=request.user)

    studentsDict = OrderedDict()

    for grade in grades:
        students = StudentSession.objects.filter(session=new_session, grade=grade, status=True).order_by('roll_no') #('student__reg_no')
        studentsDict[grade] = dict()
        for student in students:
            studentsDict[grade][student.student.reg_no] = dict()
            studentsDict[grade][student.student.reg_no] = student

    
    context = {'user':user, 'grade_level':grade_level, 'school_branch':school_branch, 'grades':grades, 'teachers':teachers, 'branchuser':branchuser, 'students_dict': studentsDict}
    return render(request, "panel/new_session.html", context)    

@login_required
def migration(request):
    this_session = get_current_session()
    this_year = 2083  # Variable to specify the migration target year
    print("migration")

    old_session = EduSession.objects.get(year=this_year-1)
    new_session, created = EduSession.objects.get_or_create(year=str(this_year), defaults={'status': True})

    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    grade_level = GradeLevel.objects.all()
    school_branch = SchoolBranch.objects.get(id=branchuser.school_id)
    grades = SchoolGrade.objects.filter(school=school_branch).order_by("id")
    # teachers = Teacher.objects.filter(added_by=request.user)


    section_list = {}
    for grade in grades:
        sections = Section.objects.filter(grade=grade, session=this_session)
        new_dict = {}
        for section in sections:
            new_dict[str(section.id)] = section.section

        section_list[str(grade.id)] = new_dict

    section_list = json.dumps(section_list)

    studentsDict = OrderedDict()
    students = False
    this_grade = gradelevel = False

    if request.method == "GET" and "grade" in request.GET:
        this_grade = request.GET['grade']
        old_session = EduSession.objects.get(year=this_year-1)
        gradelevel = SchoolGrade.objects.get(id=int(this_grade))
        students = StudentSession.objects.filter(session=old_session, grade=gradelevel)

    if request.method == "POST":
        print("REQUEST METHOD IS POST")
        this_grade = request.POST.get('grade')
        print("This GRADE: "+this_grade)
        # old_session = EduSession.objects.get(year=2080)
        gradelevelq= SchoolGrade.objects.get(id=this_grade)
        students = StudentSession.objects.filter(session=old_session, grade=gradelevelq)

        new_grade = request.POST.get("new_grade")
        new_section = request.POST.get("section")

        req_grade = SchoolGrade.objects.get(id=new_grade)
        req_section = Section.objects.get(id=new_section)

        print("NEW GRADE ",new_grade," NEW SECTION ", req_section)

        for student in students:
            print(student.student.reg_no)
            rollno = request.POST.get(student.student.reg_no)
            if rollno == '' or rollno == ' ':
                print("ROLL NO IS NULL")
                continue

            print("ROll no ", rollno)

            print(student.student.reg_no, req_grade, req_section, rollno)

            this_student = Student.objects.get(reg_no=int(student.student.reg_no))

            if StudentSession.objects.filter(session=new_session, student=this_student).count() == 0:
                student_session = StudentSession()
                student_session.session = new_session
                student_session.student = student.student
                student_session.grade = req_grade
                student_session.section = req_section
                student_session.roll_no = rollno
                student_session.status = True
                student_session.save()

                print(student_session)
            else:
                print("THIS IS UPDATE")
                student_session = StudentSession.objects.get(session=new_session, student=this_student, status=True)
                student_session.status = False
                student_session.save()

                student_session = StudentSession()
                student_session.session = new_session
                student_session.student = student.student
                student_session.grade = req_grade
                student_session.section = req_section
                student_session.roll_no = rollno
                student_session.status = True
                student_session.save()

                print(student_session)



    context = {'user':user, 'grade_level':grade_level, 'school_branch':school_branch, 'grades':grades, 'branchuser':branchuser, 'students_dict': studentsDict, 'students': students, 'section_list':section_list, 'this_grade': this_grade, 'gradelevel': gradelevel}
    return render(request, "panel/migration.html", context) 



def get_marks_grade_sheet(**kwargs):
    this_session = kwargs.get('this_session', get_current_session())
    no_of_terms=kwargs['no_of_terms']
    term_list=kwargs['term_list']
    term_calculation=kwargs['term_calculation'] 
    pass_fail_filter=kwargs['pass_fail_filter']
    students = kwargs['students']
    grade_subjects = kwargs['grade_subjects']
    this_term = kwargs['this_term']
    this_grade = kwargs['this_grade']
    school = kwargs['school']
    subjects = kwargs['subjects']
    this_section = kwargs['this_section']
    slogan = kwargs['slogan']
    logo = kwargs['logo']
    term_acronym = kwargs['term_acronym']

    sn = 0
    data = {}

    mo_dict = dict()

    total_gpa_calculation = dict()
    sub_total_fm_pm = dict()
    # term_acronym = dict()

    for student in students:
        if sn == 2:
            break
        sn += 1
        fail = 0
        data[sn] = {}
        data[sn]["session_detail"] = student
        data[sn]["student_detail"] = student.student
        data[sn]["reg_no"] = student.student.reg_no
        data[sn]["name"] = student.student.name
        data[sn]["grade"] = student.grade
        data[sn]["section"] = student.section

        data[sn]['total_calculation'] = dict()

        try:
            att = Attendance.objects.get(reg_no=student.student, grade=student.grade, session=this_session, term=this_term)
            data[sn]["no_of_school_days"] = att.no_of_school_days
            data[sn]["no_of_present_days"] = att.no_of_present_days
        except:
            data[sn]["no_of_school_days"] = False
            data[sn]["no_of_present_days"] = False

        for key, value in json.loads(term_calculation.term_calculation).items():
            if value > 0:
                marks_obtained = MarkObtained.objects.filter(student=student.student, term=key)

                for mo in marks_obtained:
                    gfm = GradeFullMarks.objects.get(term=mo.term, subject=mo.subject)

                    pre_text = str(student.student.reg_no) + "_" + str(mo.subject.id) + "_" + str(mo.term.id)

                    if gfm.th_fm > 0:
                        cal_th_mo = (value / 100) * mo.th_mo
                        cal_th_fm = (value / 100) * gfm.th_fm
                        cal_th_pm = (value / 100) * gfm.th_pm

                        print(mo.subject, "TH", value)
                        print(cal_th_fm, cal_th_mo)
                        print("====")

                        ga_gpa = GradeAndGpaNonGradeTheory(cal_th_fm, cal_th_mo)

                        mo_dict[pre_text + "_th_grade"] = ga_gpa.th_grade
                        mo_dict[pre_text + "_th_symbol"] = ga_gpa.th_symbol
                        mo_dict[pre_text + "_th_point"] = ga_gpa.th_point

                        # mo_dict[pre_text + "_th_grade"] = cal_th_mo
                        # mo_dict[pre_text + "_th_symbol"] = cal_th_mo
                        # mo_dict[pre_text + "_th_point"] = cal_th_mo

                        pt_text = str(student.student.reg_no) + "_" + str(mo.subject.id)

                        if pt_text not in total_gpa_calculation:
                            total_gpa_calculation[pt_text] = dict()

                        if 'th_fm' not in total_gpa_calculation[pt_text]:
                            total_gpa_calculation[pt_text]['th_fm'] = cal_th_fm
                        else:
                            total_gpa_calculation[pt_text]['th_fm'] += cal_th_fm

                        if 'th_mo' not in total_gpa_calculation[pt_text]:
                            total_gpa_calculation[pt_text]['th_mo'] = cal_th_mo
                        else:
                            total_gpa_calculation[pt_text]['th_fm'] += cal_th_mo

                        # if str(mo.subject.id) not in data[sn]['total_calculation']:
                        #     data[sn]['total_calculation'][str(mo.subject.id)] = dict()

                        # if 'th_fm' not in data[sn]['total_calculation'][str(mo.subject.id)]:
                        #     data[sn]['total_calculation'][str(mo.subject.id)]['th_fm'] = cal_th_fm
                        # else:
                        #     data[sn]['total_calculation'][str(mo.subject.id)]['th_fm'] += cal_th_fm
                        
                        # if 'th_pm' not in data[sn]['total_calculation'][str(mo.subject.id)]:
                        #     data[sn]['total_calculation'][str(mo.subject.id)]['th_pm'] = cal_th_pm
                        # else:
                        #     data[sn]['total_calculation'][str(mo.subject.id)]['th_pm'] += cal_th_pm

                        # if 'th_mo' not in data[sn]['total_calculation'][str(mo.subject.id)]:
                        #     data[sn]['total_calculation'][str(mo.subject.id)]['th_mo'] = cal_th_mo
                        # else:
                        #     data[sn]['total_calculation'][str(mo.subject.id)]['th_mo'] += cal_th_mo


                    if gfm.pr_fm > 0:
                        cal_pr_mo = (value / 100) * mo.pr_mo
                        cal_pr_fm = (value / 100) * gfm.pr_fm
                        cal_pr_pm = (value / 100) * gfm.pr_pm

                        print(mo.subject, "PR", value)
                        print(cal_pr_fm, cal_pr_mo, cal_pr_pm)
                        print("====")

                        ga_gpa = GradeAndGpaNonGradePractical(cal_th_fm, cal_th_mo)

                        mo_dict[pre_text + "_pr_grade"] = ga_gpa.pr_grade
                        mo_dict[pre_text + "_pr_symbol"] = ga_gpa.pr_symbol
                        mo_dict[pre_text + "_pr_point"] = ga_gpa.pr_point

                        #mo_dict[pre_text + "_pr_point"] = cal_pr_mo

                        pp_text = str(student.student.reg_no) + "_" + str(mo.subject.id)

                        if pp_text not in total_gpa_calculation:
                            total_gpa_calculation[pp_text] = dict()

                        if 'pr_fm' not in total_gpa_calculation[pp_text]:
                            total_gpa_calculation[pp_text]['pr_fm'] = cal_pr_fm
                        else:
                            total_gpa_calculation[pp_text]['pr_fm'] += cal_pr_fm

                        if 'pr_mo' not in total_gpa_calculation[pp_text]:
                            total_gpa_calculation[pp_text]['pr_mo'] = cal_pr_mo
                        else:
                            total_gpa_calculation[pp_text]['pr_mo'] += cal_pr_mo

                        # if str(mo.subject.id) not in data[sn]['total_calculation']:
                        #     data[sn]['total_calculation'][str(mo.subject.id)] = dict()
                        
                        # if '' not in data[sn]['total_calculation'][str(mo.subject.id)]:
                        #     data[sn]['total_calculation'][str(mo.subject.id)]['pr_fm'] = cal_pr_fm

                        # else:
                        #     data[sn]['total_calculation'][str(mo.subject.id)]['pr_fm'] += cal_pr_fm

                        # if 'pr_pm' not in data[sn]['total_calculation'][str(mo.subject.id)]:
                        #     data[sn]['total_calculation'][str(mo.subject.id)]['pr_pm'] = cal_pr_pm
                        # else:
                        #     data[sn]['total_calculation'][str(mo.subject.id)]['pr_pm'] += cal_pr_pm

                        # if 'pr_mo' not in data[sn]['total_calculation'][str(mo.subject.id)]:
                        #     data[sn]['total_calculation'][str(mo.subject.id)]['pr_mo'] = cal_pr_mo
                        # else:
                        #     data[sn]['total_calculation'][str(mo.subject.id)]['pr_mo'] += cal_pr_mo
                    print(total_gpa_calculation)

        total_gp = 0
        for subject in grade_subjects:
            so_text = str(str(student.student.reg_no) + "_" + str(subject.id))
            if so_text in total_gpa_calculation:
                th_fm = total_gpa_calculation[so_text]["th_fm"]
                pr_fm = total_gpa_calculation[so_text]["pr_fm"]
                th_mo = total_gpa_calculation[so_text]["th_mo"]
                pr_mo = total_gpa_calculation[so_text]["pr_mo"]

                print(subject, "FULL")
                print(th_fm, th_mo, pr_fm, pr_mo)
            else:
                print(f"For {student.student.reg_no}, Data regarding {subject} is missing. ",
                                    f"It can be either full marks or just marks.")
                if str(subject.id)+"th_fm" in sub_total_fm_pm:
                    th_fm =  sub_total_fm_pm[str(subject.id)+"th_fm"]
                else:
                    th_fm =  0                       
                
                if str(subject.id)+"pr_fm" in sub_total_fm_pm:
                    pr_fm = sub_total_fm_pm[str(subject.id)+"pr_fm"]
                else:
                    pr_fm = 0
                
                th_mo = 0 
                pr_mo = 0

            t_gpa = GradeAndGpaNonGradeTheory(th_fm, th_mo)
            mo_dict[so_text + "_th_mo_grade"] = t_gpa.th_grade
            mo_dict[so_text + "_th_mo_grade_point"] = t_gpa.th_point
            mo_dict[so_text + "_th_mo_grade_point_symbol"] = t_gpa.th_symbol

            p_gpa = GradeAndGpaNonGradePractical(pr_fm, pr_mo)
            mo_dict[so_text + "_pr_mo_grade"] = p_gpa.pr_grade
            mo_dict[so_text + "_pr_mo_grade_point"] = p_gpa.pr_point
            mo_dict[so_text + "_pr_mo_grade_point_symbol"] = p_gpa.pr_symbol
   

    context = {
        "term_list": term_list,
        "no_of_terms": no_of_terms,
        "no_of_terms_range": range(no_of_terms),
        "no_of_terms_marks_count": no_of_terms * 2,
        "gpa_colspan": 4 + (no_of_terms * 2),
        "school": school,
        "term": this_term,
        "year": this_term.year,
        "data": data,
        "grade": this_grade,
        "section": this_section,
        "subjects": grade_subjects,
        "std_list": data,
        "slogan": slogan,
        "logo": logo,
        "mo_dict": json.dumps(mo_dict),
        "no_of_subjects": subjects.count(),
        "th_pr_count": subjects.count()*2,
        "term_acronym": term_acronym,
    }

    return context


    
#def get_marks_grade_sheet_new_grading_system(**kwargs):
#    # Extracting inputs from kwargs
#    no_of_terms = kwargs['no_of_terms']
#    term_list = kwargs['term_list']
#    term_calculation = json.loads(kwargs['term_calculation'].term_calculation)
#    pass_fail_filter = kwargs['pass_fail_filter']
#    students = kwargs['students']
#    grade_subjects = kwargs['grade_subjects']
#    this_term = kwargs['this_term']
#    this_grade = kwargs['this_grade']
#    school = kwargs['school']
#    subjects = kwargs['subjects']
#    this_section = kwargs['this_section']
#    slogan = kwargs['slogan']
#    logo = kwargs['logo']
#    term_acronym = kwargs['term_acronym']
#    this_session = EduSession.objects.get(year=this_term.year)  # assuming this is how session is related
#
#    
#
#    sn = 0
#    data = {}
#    mo_dict = {}
#    total_gpa_calculation = {}
#    sub_total_fm_pm = {}
#
#    for student in students:
#        #if sn == 2:  # likely for debugging: limit to first 2 students
#        #    break
#        sn += 1
#        reg_no = student.student.reg_no
#
#        student_data = {
#            "session_detail": student,
#            "student_detail": student.student,
#            "reg_no": reg_no,
#            "name": student.student.name,
#            "grade": student.grade,
#            "section": student.section,
#            "total_calculation": {},
#        }
#
#        try:
#            att = Attendance.objects.get(reg_no=student.student, grade=student.grade, session=this_session, term=this_term)
#            student_data["no_of_school_days"] = att.no_of_school_days
#            student_data["no_of_present_days"] = att.no_of_present_days
#        except Attendance.DoesNotExist:
#            student_data["no_of_school_days"] = None
#            student_data["no_of_present_days"] = None
#
#        for term_id, weight in term_calculation.items():
#            if weight <= 0:
#                continue
#
#            marks_obtained = MarkObtained.objects.filter(student=student.student, term=term_id)
#
#            for mo in marks_obtained:
#                gfm = GradeFullMarks.objects.get(term=mo.term, subject=mo.subject)
#                key_base = f"{reg_no}_{mo.subject.id}_{mo.term.id}"
#
#                # Theory Marks Calculation
#                if gfm.th_fm > 0:
#                    th_mo = (weight / 100) * mo.th_mo
#                    th_fm = (weight / 100) * gfm.th_fm
#
#                    ga_gpa = GradeAndGpaNonGradeTheory(th_fm, th_mo)
#                    mo_dict.update({
#                        f"{key_base}_th_grade": ga_gpa.th_grade,
#                        f"{key_base}_th_symbol": ga_gpa.th_symbol,
#                        f"{key_base}_th_point": ga_gpa.th_point
#                    })
#
#                    subject_key = f"{reg_no}_{mo.subject.id}"
#                    total_gpa_calculation.setdefault(subject_key, {})
#                    total_gpa_calculation[subject_key]['th_fm'] = total_gpa_calculation[subject_key].get('th_fm', 0) + th_fm
#                    total_gpa_calculation[subject_key]['th_mo'] = total_gpa_calculation[subject_key].get('th_mo', 0) + th_mo
#
#                # Practical Marks Calculation
#                if gfm.pr_fm > 0:
#                    pr_mo = (weight / 100) * mo.pr_mo
#                    pr_fm = (weight / 100) * gfm.pr_fm
#
#                    ga_gpa = GradeAndGpaNonGradePractical(pr_fm, pr_mo)
#                    mo_dict.update({
#                        f"{key_base}_pr_grade": ga_gpa.pr_grade,
#                        f"{key_base}_pr_symbol": ga_gpa.pr_symbol,
#                        f"{key_base}_pr_point": ga_gpa.pr_point
#                    })
#
#                    total_gpa_calculation.setdefault(subject_key, {})
#                    total_gpa_calculation[subject_key]['pr_fm'] = total_gpa_calculation[subject_key].get('pr_fm', 0) + pr_fm
#                    total_gpa_calculation[subject_key]['pr_mo'] = total_gpa_calculation[subject_key].get('pr_mo', 0) + pr_mo
#
#        # Final GPA Calculation Per Subject
#        for subject in grade_subjects:
#            subject_key = f"{reg_no}_{subject.id}"
#            th_fm = pr_fm = th_mo = pr_mo = 0
#
#            if subject_key in total_gpa_calculation:
#                th_fm = total_gpa_calculation[subject_key].get('th_fm', 0)
#                pr_fm = total_gpa_calculation[subject_key].get('pr_fm', 0)
#                th_mo = total_gpa_calculation[subject_key].get('th_mo', 0)
#                pr_mo = total_gpa_calculation[subject_key].get('pr_mo', 0)
#            else:
#                # fallback to sub_total_fm_pm if available
#                th_fm = sub_total_fm_pm.get(f"{subject.id}th_fm", 0)
#                pr_fm = sub_total_fm_pm.get(f"{subject.id}pr_fm", 0)
#
#            t_gpa = GradeAndGpaNonGradeTheory(th_fm, th_mo)
#            p_gpa = GradeAndGpaNonGradePractical(pr_fm, pr_mo)
#
#            mo_dict.update({
#                f"{subject_key}_th_mo_grade": t_gpa.th_grade,
#                f"{subject_key}_th_mo_grade_point": t_gpa.th_point,
#                f"{subject_key}_th_mo_grade_point_symbol": t_gpa.th_symbol,
#                f"{subject_key}_pr_mo_grade": p_gpa.pr_grade,
#                f"{subject_key}_pr_mo_grade_point": p_gpa.pr_point,
#                f"{subject_key}_pr_mo_grade_point_symbol": p_gpa.pr_symbol,
#            })
#
#        data[sn] = student_data
#
#    # Preparing final context for template rendering
#    context = {
#        "term_list": term_list,
#        "no_of_terms": no_of_terms,
#        "no_of_terms_range": range(no_of_terms),
#        "no_of_terms_marks_count": no_of_terms * 2,
#        "gpa_colspan": 4 + (no_of_terms * 2),
#        "school": school,
#        "term": this_term,
#        "year": this_term.year,
#        "data": data,
#        "grade": this_grade,
#        "section": this_section,
#        "subjects": grade_subjects,
#        "std_list": data,
#        "slogan": slogan,
#        "logo": logo,
#        "mo_dict": json.dumps(mo_dict),
#        "no_of_subjects": subjects.count(),
#        "th_pr_count": subjects.count() * 2,
#        "term_acronym": term_acronym,
#    }
#
#    return context

def get_marks_grade_sheet_new_grading_system(**kwargs):
    try:
        term_calculation = json.loads(kwargs['term_calculation'].term_calculation)
        students = kwargs['students']
        grade_subjects = kwargs['grade_subjects']
        this_term = kwargs['this_term']
        school = kwargs['school']

        data = {}
        mo_dict = {}
        total_gpa_calculation = {}
        sub_total_fm_pm = {}

        term_ids = [term_id for term_id, weight in term_calculation.items() if weight > 0]
        marks_obtained = MarkObtained.objects.filter(
            term__in=term_ids,
            student__in=[s.student for s in students]
        ).select_related('term', 'subject')

        grade_full_marks = GradeFullMarks.objects.filter(
            term__in=term_ids,
            subject__in=grade_subjects
        ).select_related('term', 'subject')

        gfm_dict = {(gf.term_id, gf.subject_id): gf for gf in grade_full_marks}
        marks_dict = defaultdict(list)
        for mo in marks_obtained:
            marks_dict[(mo.student_id, mo.term_id)].append(mo)

        for sn, student in enumerate(students, 1):
            reg_no = student.student.reg_no
            student_data = {
                "session_detail": student,
                "student_detail": student.student,
                "reg_no": reg_no,
                "name": student.student.name,
                "grade": student.grade,
                "section": student.section,
                "total_calculation": {},
            }

            try:
                att = Attendance.objects.get(
                    reg_no=student.student,
                    grade=student.grade,
                    session=this_term.year,
                    term=this_term
                )
                student_data.update({
                    "no_of_school_days": att.no_of_school_days,
                    "no_of_present_days": att.no_of_present_days
                })
            except Attendance.DoesNotExist:
                student_data.update({
                    "no_of_school_days": None,
                    "no_of_present_days": None
                })

            for term_id, weight in term_calculation.items():
                if weight <= 0:
                    continue

                student_term_marks = marks_dict.get((student.id, int(term_id)), [])

                for mo in student_term_marks:
                    gfm = gfm_dict.get((mo.term_id, mo.subject_id))
                    if not gfm:
                        continue

                    key_base = f"{reg_no}_{mo.subject.id}_{mo.term.id}"
                    subject_key = f"{reg_no}_{mo.subject.id}"

                    if gfm.th_fm > 0:
                        _process_marks(
                            mo_dict, total_gpa_calculation,
                            weight, mo.th_mo, gfm.th_fm, gfm.th_pm,
                            key_base, subject_key, 'th',
                            GradeAndGpaNonGradeTheory
                        )

                    if gfm.pr_fm > 0:
                        _process_marks(
                            mo_dict, total_gpa_calculation,
                            weight, mo.pr_mo, gfm.pr_fm, gfm.pr_pm,
                            key_base, subject_key, 'pr',
                            GradeAndGpaNonGradePractical
                        )

            for subject in grade_subjects:
                subject_key = f"{reg_no}_{subject.id}"
                _calculate_final_grades_with_ng(
                    mo_dict, total_gpa_calculation, sub_total_fm_pm,
                    subject_key, subject.id, subject
                )

            data[sn] = student_data

        context = _prepare_context(
            kwargs, data, mo_dict,
            len(term_ids), grade_subjects.count()
        )
        return context

    except Exception as e:
        logger.error(f"Error in get_marks_grade_sheet_new_grading_system: {str(e)}")
        raise
        
def _process_marks(mo_dict, total_gpa_calculation, weight, mo_mark, fm_mark, pm_mark,
                   key_base, subject_key, prefix, calculator_class):
    calculated_mo = (weight / 100) * mo_mark
    calculated_fm = (weight / 100) * fm_mark
    calculated_pm = (weight / 100) * pm_mark

    failed = calculated_mo < calculated_pm if calculated_pm > 0 else False
    calculator = calculator_class(calculated_fm, calculated_mo)

    mo_dict.update({
        f"{key_base}_{prefix}_grade": "NG" if failed else getattr(calculator, f"{prefix}_grade"),
        f"{key_base}_{prefix}_symbol": "NG" if failed else getattr(calculator, f"{prefix}_symbol"),
        f"{key_base}_{prefix}_point": 0 if failed else getattr(calculator, f"{prefix}_point"),
        f"{key_base}_{prefix}_failed": failed
    })

    total_gpa_calculation.setdefault(subject_key, {})
    total_gpa_calculation[subject_key][f"{prefix}_fm"] = \
        total_gpa_calculation[subject_key].get(f"{prefix}_fm", 0) + calculated_fm
    total_gpa_calculation[subject_key][f"{prefix}_mo"] = \
        total_gpa_calculation[subject_key].get(f"{prefix}_mo", 0) + (0 if failed else calculated_mo)
    total_gpa_calculation[subject_key][f"{prefix}_pm"] = \
        total_gpa_calculation[subject_key].get(f"{prefix}_pm", 0) + calculated_pm
    total_gpa_calculation[subject_key][f"{prefix}_failed"] = \
        failed or total_gpa_calculation[subject_key].get(f"{prefix}_failed", False)


def _calculate_final_grades_with_ng(mo_dict, total_gpa_calculation, sub_total_fm_pm,
                                    subject_key, subject_id, subject):
    th_fm = total_gpa_calculation.get(subject_key, {}).get('th_fm',
           sub_total_fm_pm.get(f"{subject_id}th_fm", 0))
    pr_fm = total_gpa_calculation.get(subject_key, {}).get('pr_fm',
           sub_total_fm_pm.get(f"{subject_id}pr_fm", 0))
    th_mo = total_gpa_calculation.get(subject_key, {}).get('th_mo', 0)
    pr_mo = total_gpa_calculation.get(subject_key, {}).get('pr_mo', 0)
    th_failed = total_gpa_calculation.get(subject_key, {}).get('th_failed', False)
    pr_failed = total_gpa_calculation.get(subject_key, {}).get('pr_failed', False)

    t_gpa = GradeAndGpaNonGradeTheory(th_fm, th_mo)
    p_gpa = GradeAndGpaNonGradePractical(pr_fm, pr_mo)

    subject_failed = th_failed or pr_failed

    mo_dict.update({
        f"{subject_key}_th_mo_grade": "NG" if th_failed else t_gpa.th_grade,
        f"{subject_key}_th_mo_grade_point": 0 if th_failed else t_gpa.th_point,
        f"{subject_key}_th_mo_grade_point_symbol": "NG" if th_failed else t_gpa.th_symbol,
        f"{subject_key}_pr_mo_grade": "NG" if pr_failed else p_gpa.pr_grade,
        f"{subject_key}_pr_mo_grade_point": 0 if pr_failed else p_gpa.pr_point,
        f"{subject_key}_pr_mo_grade_point_symbol": "NG" if pr_failed else p_gpa.pr_symbol,
        f"{subject_key}_subject_failed": subject_failed
    })

    if subject_failed:
        mo_dict.update({
            f"{subject_key}_th_mo_grade": "NG",
            f"{subject_key}_th_mo_grade_point": 0,
            f"{subject_key}_th_mo_grade_point_symbol": "NG",
            f"{subject_key}_pr_mo_grade": "NG",
            f"{subject_key}_pr_mo_grade_point": 0,
            f"{subject_key}_pr_mo_grade_point_symbol": "NG",
        })


def _prepare_context(kwargs, data, mo_dict, no_of_terms, subject_count):
    # Implement this function to generate final report context
    # For example:
    return {
        "data": data,
        "mo_dict": mo_dict,
        "school": kwargs['school'],
        "this_term": kwargs['this_term'],
        "grade_subjects": kwargs['grade_subjects'],
        "no_of_terms": no_of_terms,
        "subject_count": subject_count,
    }


def get_marks_grade_sheet_new_grading_system_deepseek(**kwargs):
#def get_marks_grade_sheet_new_grading_system(**kwargs):
    try:
        term_calculation = json.loads(kwargs['term_calculation'].term_calculation)
        students = kwargs['students']
        grade_subjects = kwargs['grade_subjects']
        this_term = kwargs['this_term']
        school = kwargs['school']

        data = {}
        mo_dict = {}
        total_gpa_calculation = {}
        sub_total_fm_pm = {}

        term_ids = [term_id for term_id, weight in term_calculation.items() if weight > 0]
        has_two_terms = len(term_ids) == 2

        marks_obtained = MarkObtained.objects.filter(
            term__in=term_ids,
            student__in=[s.student for s in students]
        ).select_related('term', 'subject')

        grade_full_marks = GradeFullMarks.objects.filter(
            term__in=term_ids,
            subject__in=grade_subjects
        ).select_related('term', 'subject')

        # Get current term's passing marks
        current_term_gfm = GradeFullMarks.objects.filter(
            term=this_term,
            subject__in=grade_subjects
        ).select_related('subject')
        current_term_pm_dict = {
            gfm.subject_id: {
                'th_pm': gfm.th_pm if gfm.th_fm > 0 else None,
                'pr_pm': gfm.pr_pm if gfm.pr_fm > 0 else None
            }
            for gfm in current_term_gfm
        }

        gfm_dict = {(gf.term_id, gf.subject_id): gf for gf in grade_full_marks}
        marks_dict = defaultdict(list)
        for mo in marks_obtained:
            marks_dict[(mo.student_id, mo.term_id)].append(mo)

        for sn, student in enumerate(students, 1):
            reg_no = student.student.reg_no
            student_data = {
                "session_detail": student,
                "student_detail": student.student,
                "reg_no": reg_no,
                "name": student.student.name,
                "grade": student.grade,
                "section": student.section,
                "total_calculation": {},
            }

            try:
                att = Attendance.objects.get(
                    reg_no=student.student,
                    grade=student.grade,
                    session=this_term.year,
                    term=this_term
                )
                student_data.update({
                    "no_of_school_days": att.no_of_school_days,
                    "no_of_present_days": att.no_of_present_days
                })
            except Attendance.DoesNotExist:
                student_data.update({
                    "no_of_school_days": None,
                    "no_of_present_days": None
                })

            for term_id, weight in term_calculation.items():
                if weight <= 0:
                    continue

                student_term_marks = marks_dict.get((student.id, int(term_id)), [])

                for mo in student_term_marks:
                    gfm = gfm_dict.get((mo.term_id, mo.subject_id))
                    if not gfm:
                        continue

                    key_base = f"{reg_no}_{mo.subject.id}_{mo.term.id}"
                    subject_key = f"{reg_no}_{mo.subject.id}"

                    if gfm.th_fm > 0:
                        _process_marks(
                            mo_dict, total_gpa_calculation,
                            weight, mo.th_mo, gfm.th_fm, gfm.th_pm,
                            key_base, subject_key, 'th',
                            GradeAndGpaNonGradeTheory
                        )

                    if gfm.pr_fm > 0:
                        _process_marks(
                            mo_dict, total_gpa_calculation,
                            weight, mo.pr_mo, gfm.pr_fm, gfm.pr_pm,
                            key_base, subject_key, 'pr',
                            GradeAndGpaNonGradePractical
                        )

            # Check combined pass/fail for two-term cases
            if has_two_terms:
                combined_pass = True
                for subject in grade_subjects:
                    subject_key = f"{reg_no}_{subject.id}"
                    current_pm = current_term_pm_dict.get(subject.id, {})
                    
                    # Check theory
                    if current_pm.get('th_pm') is not None:
                        combined_th_mo = mo_dict.get(f"{subject_key}_th_total_mo", 0)
                        if combined_th_mo < current_pm['th_pm']:
                            combined_pass = False
                            break
                    
                    # Check practical
                    if current_pm.get('pr_pm') is not None:
                        combined_pr_mo = mo_dict.get(f"{subject_key}_pr_total_mo", 0)
                        if combined_pr_mo < current_pm['pr_pm']:
                            combined_pass = False
                            break
                
                if not combined_pass:
                    # If failed combined, set all subjects to fail
                    for subject in grade_subjects:
                        subject_key = f"{reg_no}_{subject.id}"
                        mo_dict[f"{subject_key}_subject_failed"] = True
                        mo_dict[f"{subject_key}_th_mo_grade"] = "NG"
                        mo_dict[f"{subject_key}_th_mo_grade_point"] = 0
                        mo_dict[f"{subject_key}_pr_mo_grade"] = "NG"
                        mo_dict[f"{subject_key}_pr_mo_grade_point"] = 0

            for subject in grade_subjects:
                subject_key = f"{reg_no}_{subject.id}"
                _calculate_final_grades_with_ng(
                    mo_dict, total_gpa_calculation, sub_total_fm_pm,
                    subject_key, subject.id, subject
                )

            data[sn] = student_data

        context = _prepare_context(
            kwargs, data, mo_dict,
            len(term_ids), grade_subjects.count()
        )
        return context

    except Exception as e:
        logger.error(f"Error in get_marks_grade_sheet_new_grading_system_deepseek: {str(e)}")
        raise



#created after santosh sir asked before my first second sem exam DAA

#def get_marks_grade_sheet_new_grading_system_exam_updated(**kwargs):
#    print("get_marks_grade_sheet_new_grading_system_exam_updated")
#    #    # Extracting inputs from kwargs
#    no_of_terms = kwargs['no_of_terms']
#    term_list = kwargs['term_list']
#    term_calculation = json.loads(kwargs['term_calculation'].term_calculation)
#    pass_fail_filter = kwargs['pass_fail_filter']
#    students = kwargs['students']
#    grade_subjects = kwargs['grade_subjects']
#    this_term = kwargs['this_term']
#    this_grade = kwargs['this_grade']
#    school = kwargs['school']
#    subjects = kwargs['subjects']
#    this_section = kwargs['this_section']
#    slogan = kwargs['slogan']
#    logo = kwargs['logo']
#    term_acronym = kwargs['term_acronym']
#    this_session = EduSession.objects.get(year=this_term.year)  # assuming this is how session is related
#
#    
#
#    sn = 0
#    data = {}
#    mo_dict = {}
#    total_gpa_calculation = {}
#    sub_total_fm_pm = {}
#
#    for student in students:
#        #if sn == 2:  # likely for debugging: limit to first 2 students
#        #    break
#        sn += 1
#        reg_no = student.student.reg_no
#
#        student_data = {
#            "session_detail": student,
#            "student_detail": student.student,
#            "reg_no": reg_no,
#            "name": student.student.name,
#            "grade": student.grade,
#            "section": student.section,
#            "total_calculation": {},
#        }
#
#        try:
#            att = Attendance.objects.get(reg_no=student.student, grade=student.grade, session=this_session, term=this_term)
#            student_data["no_of_school_days"] = att.no_of_school_days
#            student_data["no_of_present_days"] = att.no_of_present_days
#        except Attendance.DoesNotExist:
#            student_data["no_of_school_days"] = None
#            student_data["no_of_present_days"] = None
#
#        for term_id, weight in term_calculation.items():
#            if weight <= 0:
#                continue
#
#            marks_obtained = MarkObtained.objects.filter(student=student.student, term=term_id)
#
#            for mo in marks_obtained:
#                gfm = GradeFullMarks.objects.get(term=mo.term, subject=mo.subject)
#                key_base = f"{reg_no}_{mo.subject.id}_{mo.term.id}"
#
#                # Theory Marks Calculation
#                if gfm.th_fm > 0:
#                    th_mo = (weight / 100) * mo.th_mo
#                    th_fm = (weight / 100) * gfm.th_fm
#
#                    ga_gpa = GradeAndGpaNonGradeTheory(th_fm, th_mo)
#                    mo_dict.update({
#                        f"{key_base}_th_grade": ga_gpa.th_grade,
#                        f"{key_base}_th_symbol": ga_gpa.th_symbol,
#                        f"{key_base}_th_point": ga_gpa.th_point
#                    })
#
#                    subject_key = f"{reg_no}_{mo.subject.id}"
#                    total_gpa_calculation.setdefault(subject_key, {})
#                    total_gpa_calculation[subject_key]['th_fm'] = total_gpa_calculation[subject_key].get('th_fm', 0) + th_fm
#                    total_gpa_calculation[subject_key]['th_mo'] = total_gpa_calculation[subject_key].get('th_mo', 0) + th_mo
#
#                # Practical Marks Calculation
#                if gfm.pr_fm > 0:
#                    pr_mo = (weight / 100) * mo.pr_mo
#                    pr_fm = (weight / 100) * gfm.pr_fm
#
#                    ga_gpa = GradeAndGpaNonGradePractical(pr_fm, pr_mo)
#                    mo_dict.update({
#                        f"{key_base}_pr_grade": ga_gpa.pr_grade,
#                        f"{key_base}_pr_symbol": ga_gpa.pr_symbol,
#                        f"{key_base}_pr_point": ga_gpa.pr_point
#                    })
#
#                    total_gpa_calculation.setdefault(subject_key, {})
#                    total_gpa_calculation[subject_key]['pr_fm'] = total_gpa_calculation[subject_key].get('pr_fm', 0) + pr_fm
#                    total_gpa_calculation[subject_key]['pr_mo'] = total_gpa_calculation[subject_key].get('pr_mo', 0) + pr_mo
#
#        # Final GPA Calculation Per Subject
#        for subject in grade_subjects:
#            subject_key = f"{reg_no}_{subject.id}"
#            th_fm = pr_fm = th_mo = pr_mo = 0
#
#            if subject_key in total_gpa_calculation:
#                th_fm = total_gpa_calculation[subject_key].get('th_fm', 0)
#                pr_fm = total_gpa_calculation[subject_key].get('pr_fm', 0)
#                th_mo = total_gpa_calculation[subject_key].get('th_mo', 0)
#                pr_mo = total_gpa_calculation[subject_key].get('pr_mo', 0)
#            else:
#                # fallback to sub_total_fm_pm if available
#                th_fm = sub_total_fm_pm.get(f"{subject.id}th_fm", 0)
#                pr_fm = sub_total_fm_pm.get(f"{subject.id}pr_fm", 0)
#
#            t_gpa = GradeAndGpaNonGradeTheory(th_fm, th_mo)
#            p_gpa = GradeAndGpaNonGradePractical(pr_fm, pr_mo)
#
#            mo_dict.update({
#                f"{subject_key}_th_mo_grade": t_gpa.th_grade,
#                f"{subject_key}_th_mo_grade_point": t_gpa.th_point,
#                f"{subject_key}_th_mo_grade_point_symbol": t_gpa.th_symbol,
#                f"{subject_key}_pr_mo_grade": p_gpa.pr_grade,
#                f"{subject_key}_pr_mo_grade_point": p_gpa.pr_point,
#                f"{subject_key}_pr_mo_grade_point_symbol": p_gpa.pr_symbol,
#            })
#
#        data[sn] = student_data
#
#    # Preparing final context for template rendering
#    context = {
#        "term_list": term_list,
#        "no_of_terms": no_of_terms,
#        "no_of_terms_range": range(no_of_terms),
#        "no_of_terms_marks_count": no_of_terms * 2,
#        "gpa_colspan": 4 + (no_of_terms * 2),
#        "school": school,
#        "term": this_term,
#        "year": this_term.year,
#        "data": data,
#        "grade": this_grade,
#        "section": this_section,
#        "subjects": grade_subjects,
#        "std_list": data,
#        "slogan": slogan,
#        "logo": logo,
#        "mo_dict": json.dumps(mo_dict),
#        "no_of_subjects": subjects.count(),
#        "th_pr_count": subjects.count() * 2,
#        "term_acronym": term_acronym,
#    }
#
#    return context

#
#def get_marks_grade_sheet_new_grading_system_exam_updated(**kwargs):
#    print("get_marks_grade_sheet_new_grading_system_exam_updated")
#    try:
#        # Extract inputs from kwargs with error handling
#        no_of_terms = kwargs.get('no_of_terms', 0)
#        term_list = kwargs.get('term_list', [])
#        term_calculation = json.loads(kwargs.get('term_calculation', {}).term_calculation)
#        pass_fail_filter = kwargs.get('pass_fail_filter', 0)
#        students = kwargs.get('students', [])
#        grade_subjects = kwargs.get('grade_subjects', [])
#        this_term = kwargs.get('this_term')
#        this_grade = kwargs.get('this_grade')
#        school = kwargs.get('school')
#        subjects = kwargs.get('subjects', [])
#        this_section = kwargs.get('this_section')
#        slogan = kwargs.get('slogan', " ")
#        logo = kwargs.get('logo', "")
#        term_acronym = kwargs.get('term_acronym', {})
#
#        # Get session with error handling
#        try:
#            this_session = EduSession.objects.get(year=this_term.year)
#        except Exception as e:
#            print(f"Error getting session: {str(e)}")
#            this_session = None
#
#        sn = 0
#        data = {}
#        mo_dict = {}
#        total_gpa_calculation = {}
#        sub_total_fm_pm = {}
#
#        for student in students:
#            try:
#                sn += 1
#                reg_no = getattr(student.student, 'reg_no', '')
#                
#                student_data = {
#                    "session_detail": student,
#                    "student_detail": student.student,
#                    "reg_no": reg_no,
#                    "name": getattr(student.student, 'name', ''),
#                    "grade": getattr(student, 'grade', ''),
#                    "section": getattr(student, 'section', ''),
#                    "total_calculation": {},
#                }
#
#                # Attendance handling with error prevention
#                try:
#                    att = Attendance.objects.get(
#                        reg_no=student.student,
#                        grade=student.grade,
#                        session=this_session,
#                        term=this_term
#                    )
#                    student_data.update({
#                        "no_of_school_days": getattr(att, 'no_of_school_days', 0),
#                        "no_of_present_days": getattr(att, 'no_of_present_days', 0)
#                    })
#                except Exception as e:
#                    print(f"Attendance error for {reg_no}: {str(e)}")
#                    student_data.update({
#                        "no_of_school_days": None,
#                        "no_of_present_days": None
#                    })
#
#                # Process marks for each term
#                for term_id, weight in term_calculation.items():
#                    if weight <= 0:
#                        continue
#
#                    try:
#                        marks_obtained = MarkObtained.objects.filter(
#                            student=student.student,
#                            term=term_id
#                        )
#
#                        for mo in marks_obtained:
#                            try:
#                                gfm = GradeFullMarks.objects.get(term=mo.term, subject=mo.subject)
#                                key_base = f"{reg_no}_{mo.subject.id}_{mo.term.id}"
#                                subject_key = f"{reg_no}_{mo.subject.id}"
#
#                                # Initialize if not exists
#                                if subject_key not in total_gpa_calculation:
#                                    total_gpa_calculation[subject_key] = {
#                                        'th_fm': 0,
#                                        'th_mo': 0,
#                                        'th_pm': 0,
#                                        'pr_fm': 0,
#                                        'pr_mo': 0,
#                                        'pr_pm': 0
#                                    }
#
#                                # Theory Marks Calculation
#                                if getattr(gfm, 'th_fm', 0) > 0:
#                                    th_mo = (weight / 100) * getattr(mo, 'th_mo', 0)
#                                    th_fm = (weight / 100) * getattr(gfm, 'th_fm', 0)
#                                    th_pm = (weight / 100) * getattr(gfm, 'th_pm', 0)
#
#                                    ga_gpa = GradeAndGpaNonGradeTheory(th_fm, th_mo)
#                                    mo_dict.update({
#                                        f"{key_base}_th_grade": getattr(ga_gpa, 'th_grade', ' '),
#                                        f"{key_base}_th_symbol": getattr(ga_gpa, 'th_symbol', ' '),
#                                        f"{key_base}_th_point": getattr(ga_gpa, 'th_point', 0)
#                                    })
#
#                                    # Accumulate for final grade
#                                    total_gpa_calculation[subject_key]['th_fm'] += th_fm
#                                    total_gpa_calculation[subject_key]['th_mo'] += th_mo
#                                    total_gpa_calculation[subject_key]['th_pm'] += th_pm
#
#                                # Practical Marks Calculation
#                                if getattr(gfm, 'pr_fm', 0) > 0:
#                                    pr_mo = (weight / 100) * getattr(mo, 'pr_mo', 0)
#                                    pr_fm = (weight / 100) * getattr(gfm, 'pr_fm', 0)
#                                    pr_pm = (weight / 100) * getattr(gfm, 'pr_pm', 0)
#
#                                    ga_gpa = GradeAndGpaNonGradePractical(pr_fm, pr_mo)
#                                    mo_dict.update({
#                                        f"{key_base}_pr_grade": getattr(ga_gpa, 'pr_grade', ' '),
#                                        f"{key_base}_pr_symbol": getattr(ga_gpa, 'pr_symbol', ' '),
#                                        f"{key_base}_pr_point": getattr(ga_gpa, 'pr_point', 0)
#                                    })
#
#                                    total_gpa_calculation[subject_key]['pr_fm'] += pr_fm
#                                    total_gpa_calculation[subject_key]['pr_mo'] += pr_mo
#                                    total_gpa_calculation[subject_key]['pr_pm'] += pr_pm
#
#                            except Exception as e:
#                                print(f"Error processing marks for {reg_no}: {str(e)}")
#                                continue
#
#                    except Exception as e:
#                        print(f"Error processing term {term_id} for {reg_no}: {str(e)}")
#                        continue
#
#                # Final GPA Calculation Per Subject with pass/fail check
#                total_grade_points = 0
#                passed_subjects = 0
#                failed_subjects = 0
#
#                for subject in grade_subjects:
#                    try:
#                        subject_key = f"{reg_no}_{subject.id}"
#                        subject_data = total_gpa_calculation.get(subject_key, {})
#                        
#                        th_fm = subject_data.get('th_fm', 0)
#                        th_mo = subject_data.get('th_mo', 0)
#                        th_pm = subject_data.get('th_pm', 0)
#                        pr_fm = subject_data.get('pr_fm', 0)
#                        pr_mo = subject_data.get('pr_mo', 0)
#                        pr_pm = subject_data.get('pr_pm', 0)
#
#                        # Check if student passed both components
#                        passed_theory = th_fm == 0 or (th_mo >= th_pm)
#                        passed_practical = pr_fm == 0 or (pr_mo >= pr_pm)
#                        passed_subject = passed_theory and passed_practical
#
#                        # Calculate grades
#                        t_gpa = GradeAndGpaNonGradeTheory(th_fm, th_mo)
#                        p_gpa = GradeAndGpaNonGradePractical(pr_fm, pr_mo)
#
#                        # Store results
#                        mo_dict.update({
#                            f"{subject_key}_th_mo_grade": t_gpa.th_grade if passed_theory else "NG",
#                            f"{subject_key}_th_mo_grade_point": t_gpa.th_point if passed_theory else 0,
#                            f"{subject_key}_th_mo_grade_point_symbol": t_gpa.th_symbol if passed_theory else "",
#                            f"{subject_key}_pr_mo_grade": p_gpa.pr_grade if passed_practical else "NG",
#                            f"{subject_key}_pr_mo_grade_point": p_gpa.pr_point if passed_practical else 0,
#                            f"{subject_key}_pr_mo_grade_point_symbol": p_gpa.pr_symbol if passed_practical else "",
#                            f"{subject_key}_passed": passed_subject
#                        })
#
#                        # Calculate subject grade point
#                        if passed_subject:
#                            if th_fm > 0 and pr_fm > 0:
#                                subject_point = (t_gpa.th_point + p_gpa.pr_point) / 2
#                            elif th_fm > 0:
#                                subject_point = t_gpa.th_point
#                            else:
#                                subject_point = p_gpa.pr_point
#                            
#                            total_grade_points += subject_point
#                            passed_subjects += 1
#                        else:
#                            failed_subjects += 1
#
#                    except Exception as e:
#                        print(f"Error processing subject {getattr(subject, 'id', '?')} for {reg_no}: {str(e)}")
#                        continue
#
#                # Calculate final GPA (0 if any subject failed)
#                if failed_subjects == 0 and passed_subjects > 0:
#                    gpa = round(total_grade_points / passed_subjects, 2)
#                    remarks = "Congratulations, You have been promoted"
#                else:
#                    gpa = 0
#                    remarks = "Re-examination required" if failed_subjects > 0 else "No marks available"
#                
#                mo_dict.update({
#                    f"{reg_no}_gpa": gpa,
#                    f"{reg_no}_passed_all": failed_subjects == 0,
#                    f"{reg_no}_remarks": remarks
#                })
#
#                data[sn] = student_data
#
#            except Exception as e:
#                print(f"Error processing student {getattr(student, 'reg_no', 'UNKNOWN')}: {str(e)}")
#                continue
#
#        # Preparing final context for template rendering
#        context = {
#            "term_list": term_list,
#            "no_of_terms": no_of_terms,
#            "no_of_terms_range": range(no_of_terms),
#            "no_of_terms_marks_count": no_of_terms * 2,
#            "gpa_colspan": 4 + (no_of_terms * 2),
#            "school": school,
#            "term": this_term,
#            "year": this_term.year,
#            "data": data,
#            "grade": this_grade,
#            "section": this_section,
#            "subjects": grade_subjects,
#            "std_list": data,
#            "slogan": slogan,
#            "logo": logo,
#            "mo_dict": json.dumps(mo_dict),
#            "no_of_subjects": len(subjects),
#            "th_pr_count": len(subjects) * 2,
#            "term_acronym": term_acronym,
#        }
#
#        return context
#
#    except Exception as e:
#        print(f"Critical error in grade sheet generation: {str(e)}")
#        # Return minimal context to prevent template errors
#        return {
#            "term_list": [],
#            "no_of_terms": 0,
#            "data": {},
#            "mo_dict": "{}",
#            # Include other required fields with safe defaults
#        }

def get_marks_grade_sheet_new_grading_system_exam_updated(**kwargs):
    print("get_marks_grade_sheet_new_grading_system_exam_updated")
    # print(f"kwargs: {kwargs}")
    try:
        # Extract inputs from kwargs with error handling
        no_of_terms = kwargs.get('no_of_terms', 0)
        term_list = kwargs.get('term_list', [])
        term_calculation_input = kwargs.get('term_calculation', '{}')
        if not isinstance(term_calculation_input, str):
            term_calculation_input = getattr(term_calculation_input, 'term_calculation', '{}')
        try:
            term_calculation = json.loads(term_calculation_input)
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Error parsing term_calculation: {str(e)}")
            term_calculation = {}
        pass_fail_filter = kwargs.get('pass_fail_filter', 0)
        students = kwargs.get('students', [])
        grade_subjects = kwargs.get('grade_subjects', [])
        this_term = kwargs.get('this_term')
        this_grade = kwargs.get('this_grade')
        school = kwargs.get('school')
        subjects = kwargs.get('subjects', [])
        this_section = kwargs.get('this_section')
        slogan = kwargs.get('slogan', " ")
        logo = kwargs.get('logo', "")
        term_acronym = kwargs.get('term_acronym', {})
        this_session = kwargs.get('this_session')

        # If this_session not passed, try to get it from term year (but prefer latest)
        if not this_session:
            try:
                year = this_term.year if hasattr(this_term, 'year') else this_term.term.year
                this_session = EduSession.objects.filter(year=year).last()
            except Exception as e:
                print(f"Error getting session: {str(e)}")
                this_session = None

        sn = 0
        data = {}
        mo_dict = {}
        total_gpa_calculation = {}
        sub_total_fm_pm = {}

        for student in students:
            try:
                sn += 1
                reg_no = getattr(student.student, 'reg_no', '')
                
                student_data = {
                    "session_detail": student,
                    "student_detail": student.student,
                    "reg_no": reg_no,
                    "name": getattr(student.student, 'name', ''),
                    "grade": getattr(student, 'grade', ''),
                    "section": getattr(student, 'section', ''),
                    "total_calculation": {},
                    "no_of_school_days": None,
                    "no_of_present_days": None
                }

                # Attendance handling
                try:
                    att = Attendance.objects.get(
                        reg_no=student.student,
                        grade=student.grade,
                        session=this_session,
                        term=this_term
                    )
                    student_data.update({
                        "no_of_school_days": getattr(att, 'no_of_school_days', 0),
                        "no_of_present_days": getattr(att, 'no_of_present_days', 0)
                    })
                except Exception as e:
                    print(f"Attendance error for {reg_no}: {str(e)}")

                # Initialize subject data for aggregation
                for subject in grade_subjects:
                    subject_key = f"{reg_no}_{subject.id}"
                    total_gpa_calculation[subject_key] = {
                        'th_fm': 0, 'th_mo': 0, 'th_pm': 0,
                        'pr_fm': 0, 'pr_mo': 0, 'pr_pm': 0
                    }

                # Process marks for each term
                for term_id, weight in term_calculation.items():
                    if weight <= 0:
                        continue

                    try:
                        marks_obtained = MarkObtained.objects.filter(
                            student=student.student,
                            term=term_id
                        )

                        for mo in marks_obtained:
                            try:
                                gfm = GradeFullMarks.objects.get(term=mo.term, subject=mo.subject)
                                key_base = f"{reg_no}_{mo.subject.id}_{mo.term.id}"
                                subject_key = f"{reg_no}_{mo.subject.id}"

                                # Theory Marks Calculation
                                if getattr(gfm, 'th_fm', 0) > 0:
                                    th_mo = (weight / 100) * getattr(mo, 'th_mo', 0)
                                    th_fm = (weight / 100) * getattr(gfm, 'th_fm', 0)
                                    th_pm = (weight / 100) * getattr(gfm, 'th_pm', 0)

                                    # print("WEight:" , weight, "TH FM", th_fm, "TH PM", th_pm)

                                    ga_gpa = GradeAndGpaNonGradeTheoryExam(th_fm, th_mo)
                                    mo_dict.update({
                                        f"{key_base}_th_grade": getattr(ga_gpa, 'th_grade', ' '),
                                        f"{key_base}_th_point": getattr(ga_gpa, 'th_point', 0),
                                        f"{key_base}_th_symbol": getattr(ga_gpa, 'th_symbol', ' '),
                                        f"{key_base}_th_mo": round(th_mo, 2)
                                    })

                                    # Accumulate for final grade
                                    total_gpa_calculation[subject_key]['th_fm'] += th_fm
                                    total_gpa_calculation[subject_key]['th_mo'] += th_mo
                                    total_gpa_calculation[subject_key]['th_pm'] += th_pm

                                    if reg_no == 11110510:
                                        print('TH total_gpa_calculation', total_gpa_calculation[subject_key]['th_fm'])

                                # Practical Marks Calculation
                                if getattr(gfm, 'pr_fm', 0) > 0:
                                    pr_mo = (weight / 100) * getattr(mo, 'pr_mo', 0)
                                    pr_fm = (weight / 100) * getattr(gfm, 'pr_fm', 0)
                                    pr_pm = (weight / 100) * getattr(gfm, 'pr_pm', 0)

                                    # print("PR FM", pr_fm, "PR PM", pr_pm)

                                    ga_gpa = GradeAndGpaNonGradePracticalExam(pr_fm, pr_mo)
                                    mo_dict.update({
                                        f"{key_base}_pr_grade": getattr(ga_gpa, 'pr_grade', ' '),
                                        f"{key_base}_pr_point": getattr(ga_gpa, 'pr_point', 0),
                                        f"{key_base}_pr_symbol": getattr(ga_gpa, 'pr_symbol', ' '),
                                        f"{key_base}_pr_mo": round(pr_mo, 2)
                                    })

                                    total_gpa_calculation[subject_key]['pr_fm'] += pr_fm
                                    total_gpa_calculation[subject_key]['pr_mo'] += pr_mo
                                    total_gpa_calculation[subject_key]['pr_pm'] += pr_pm

                                    if reg_no == 11110510:
                                        print('TGC', subject_key, total_gpa_calculation[subject_key]['pr_fm'])

                            except Exception as e:
                                print(f"Error processing marks for {reg_no}, subject {mo.subject.id}: {str(e)}")
                                continue

                    except Exception as e:
                        print(f"Error processing term {term_id} for {reg_no}: {str(e)}")
                        continue

                # Final GPA Calculation Per Subject with pass/fail check
                total_grade_points = 0
                passed_subjects = 0
                failed_subjects = 0

                for subject in grade_subjects:
                    if reg_no == 11110510:
                        print("Total GPA Calculation", total_gpa_calculation)
                    try:
                        subject_key = f"{reg_no}_{subject.id}"
                        subject_data = total_gpa_calculation.get(subject_key, {})
                        
                        # Extract aggregated marks
                        th_fm = subject_data.get('th_fm', 0)
                        th_mo = subject_data.get('th_mo', 0)
                        th_pm = subject_data.get('th_pm', 0)
                        pr_fm = subject_data.get('pr_fm', 0)
                        pr_mo = subject_data.get('pr_mo', 0)
                        pr_pm = subject_data.get('pr_pm', 0)

                        if reg_no == 11110510:
                            print("Subject Key", subject_key, th_fm, th_mo, th_pm, pr_fm, pr_mo, pr_pm)

                        if th_fm > 0:
                            th_per = th_mo*100/th_fm
                        if pr_fm > 0:
                            pr_per = pr_mo*100/pr_fm


                        # Check pass/fail for aggregated marks
                        # passed_theory = th_fm == 0 or (th_mo >= th_pm)
                        # passed_practical = pr_fm == 0 or (pr_mo >= pr_pm)
                        # passed_subject = passed_theory and passed_practical

                        passed_theory = th_fm == 0 or (th_per >= 40)
                        passed_practical = pr_fm == 0 or (pr_per >= 40)
                        passed_subject = passed_theory and passed_practical


                        # Initialize default values for failed subjects
                        total_grade = "NG"
                        total_symbol = ""
                        total_grade_point = 0  # Explicitly set to 0 for failed subjects

                        # Only calculate grades if subject is passed
                        if passed_subject:
                            # if reg_no == 11110510:
                            # print('subjects passed', reg_no, (th_fm, th_mo))
                            # t_gpa = GradeAndGpaNonGradeTheoryExam(th_fm, th_mo) if th_fm > 0 else None
                            # p_gpa = GradeAndGpaNonGradePracticalExam(pr_fm, pr_mo) if pr_fm > 0 else None
                            # print(reg_no, 'Theory',t_gpa.th_point, 'practical',p_gpa.pr_point)

                            # if th_fm > 0 and pr_fm > 0 and t_gpa and p_gpa:
                            #     total_grade_point = (t_gpa.th_point + p_gpa.pr_point) / 2
                            #     total_grade, total_symbol, total_gp = get_grade_point_exam(total_grade_point)
                            #     # total_grade = "ABC"
                            # elif th_fm > 0 and t_gpa:
                            #     total_grade_point = t_gpa.th_point
                            #     total_grade = t_gpa.th_grade
                            #     total_symbol = t_gpa.th_symbol
                            # elif pr_fm > 0 and p_gpa:
                            #     total_grade_point = p_gpa.pr_point
                            #     total_grade = p_gpa.pr_grade
                            #     total_symbol = p_gpa.pr_symbol

                            total_grade, total_symbol, total_grade_point = get_grade_point_exam((th_mo+pr_mo)*100/(th_fm+pr_fm))

                        # Store results - will show 0 for failed subjects
                        mo_dict.update({
                            f"{subject_key}_total_grade": total_grade,
                            f"{subject_key}_total_symbol": total_symbol,
                            f"{subject_key}_total_grade_point": round(total_grade_point, 2),
                            f"{subject_key}_passed": passed_subject
                        })

                        if total_grade_point < 1.6:
                            failed_subjects += 1

                        # Calculate subject grade point for GPA
                        if passed_subject:
                            total_grade_points += total_grade_point
                            passed_subjects += 1
                        else:
                            failed_subjects += 1

                    except Exception as e:
                        print(f"Error processing subject {getattr(subject, 'id', '?')} for {reg_no}: {str(e)}")
                        failed_subjects += 1
                        continue

                # # Calculate final GPA and remarks
                if failed_subjects > 0:  # Set GPA to 0 if any subject is failed
                    gpa = 0
                    remark = this_term.final_term and "Re-examination required for further consideration" or "Labour Hard"
                else:
                    gpa = round(total_grade_points / passed_subjects, 2) if passed_subjects > 0 else 0
                    remark = this_term.final_term and "Congratulations, You have been promoted" or remarks(gpa)

                mo_dict.update({
                    f"{reg_no}_gpa": gpa,
                    f"{reg_no}_passed_all": failed_subjects == 0,
                    f"{reg_no}_remarks": remark
                })

                data[sn] = student_data

            except Exception as e:
                print(f"Error processing student {getattr(student, 'reg_no', 'UNKNOWN')}: {str(e)}")
                continue

        # Prepare spacing for template
        sub_count = len(grade_subjects)
        the_space = "a" * (12 - sub_count)

        # Prepare final context for template rendering
        context = {
            "term_list": term_list,
            "no_of_terms": no_of_terms,
            "no_of_terms_range": range(no_of_terms),
            "no_of_terms_marks_count": no_of_terms * 2,
            "gpa_colspan": 4 + (no_of_terms * 2),
            "school": school,
            "term": this_term,
            "year": this_term.year if hasattr(this_term, 'year') else this_term.term.year,
            "data": data,
            "grade": this_grade,
            "section": this_section,
            "subjects": grade_subjects,
            "std_list": data,
            "slogan": slogan,
            "logo": logo,
            "mo_dict": json.dumps(mo_dict),
            "no_of_subjects": len(subjects),
            "th_pr_count": len(subjects) * 2,
            "term_acronym": term_acronym,
            "the_space": the_space
        }

        return context

    except Exception as e:
        print(f"Critical error in grade sheet generation: {str(e)}")
        return {
            "term_list": [],
            "no_of_terms": 0,
            "data": {},
            "mo_dict": "{}",
        }


@login_required
def print_grade_ledger_exam(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    slogan = " &nbsp; "
    logo = ""
    no_of_terms = 0
    exam_board = [14, 15]  # Define exam_board for board logic

    if school.id <= 13:
        # Samata School
        slogan = "Education for all."
        logo = "https://cdn.hamro.com/simsnepal/logos/samata_logo_black.png"
    elif school.id == 14:
        # CSA Montessori
        slogan = "Soaring to Excellence"
        logo = "https://cdn.hamro.com/simsnepal/logos/csa.jpg"
    elif school.id == 15:
        # Paramount Children Academy
        slogan = " &nbsp; "
        logo = "https://cdn.hamro.com/simsnepal/logos/paramount.png"
    elif school.id >= 16 and school.id <= 26:
        # Samata School
        slogan = "Education for all."
        logo = "https://cdn.hamro.com/simsnepal/logos/samata_logo_black.png"

    if request.method == "POST":
        edusession = request.POST.get("edusession")
        term = request.POST.get("term")
        printtype = int(request.POST.get("printtype"))
        grade = request.POST.get("grade2", 0)
        section = request.POST.get("section2", 0)
        data_filter = int(request.POST.get("filter", 0))
        data_order = int(request.POST.get("data_order", 1))
        grading_type = int(request.POST.get("grading_type"))
        rank_by = request.POST.get("rank_by", "total")

        if grade == 0 or grade is None or grade == "":
            return HttpResponse(
                "Sorry! something went wrong. Please take care while submitting data."
            )
        else:
            this_grade = SchoolGrade.objects.get(id=grade)
        this_session = EduSession.objects.get(id=edusession)
        this_term = SchoolTerm.objects.get(id=term)

        if int(section) > 0:
            this_section = Section.objects.get(id=section)
        else:
            this_section = False

        subjects = Subject.objects.filter(
            session=this_session, branch=school, grade=this_grade, status=True
        ).order_by("id")
        grade_subjects = Subject.objects.filter(
            session=this_session, branch=school, grade=this_grade, status=True
        ).order_by("id")

        if this_section == False:
            if data_order == 1:
                students = StudentSession.objects.filter(session=this_session, grade=this_grade, status=True).order_by(
                    'student__reg_no')
            elif data_order == 2:
                students = StudentSession.objects.filter(session=this_session, grade=this_grade, status=True).order_by(
                    'roll_no')
            elif data_order == 3:
                # Rank
                ranks = calculate_rank(school.id, this_session, this_grade, this_term, this_section, rank_by=rank_by)
                students = list(StudentSession.objects.filter(session=this_session, grade=this_grade, status=True))
                students.sort(key=lambda s: ranks.get(s.student.reg_no, 9999))
            else:
                students = StudentSession.objects.filter(session=this_session, grade=this_grade, status=True).order_by(
                    'roll_no')
        else:
            if data_order == 1:
                students = StudentSession.objects.filter(grade=this_grade, section=this_section, session=this_session,
                                                         status=True).order_by('student__reg_no')
            elif data_order == 2:
                students = StudentSession.objects.filter(grade=this_grade, section=this_section, session=this_session,
                                                         status=True).order_by('roll_no')
            elif data_order == 3:
                # Rank
                ranks = calculate_rank(school.id, this_session, this_grade, this_term, this_section, rank_by=rank_by)
                students = list(StudentSession.objects.filter(grade=this_grade, section=this_section, session=this_session,
                                                         status=True))
                students.sort(key=lambda s: ranks.get(s.student.reg_no, 9999))
            else:
                students = StudentSession.objects.filter(grade=this_grade, section=this_section, session=this_session,
                                                         status=True).order_by('roll_no')

        term_calculation = ResultManagement.objects.get(school_term=this_term)
        term_list = []
        term_acronym = {}
        for key, value in json.loads(term_calculation.term_calculation).items():
            if value > 0:
                no_of_terms += 1
                this_term_obj = SchoolTerm.objects.get(id=key)
                term_acronym[this_term_obj.name_in_short] = this_term_obj.term_name
                term_list.append(key)

        if grading_type == 2:
            context = get_marks_grade_sheet_new_grading_system_exam_updated1(
                no_of_terms=no_of_terms,
                term_list=term_list,
                term_calculation=term_calculation,
                pass_fail_filter=data_filter,
                students=students,
                grade_subjects=grade_subjects,
                this_term=this_term,
                this_grade=this_grade,
                school=school,
                subjects=subjects,
                this_section=this_section,
                slogan=slogan,
                logo=logo,
                term_acronym=term_acronym
            )
        else:
            sub_total_fm_pm = {}
            mo_dict = {}
            total_gpa_calculation = {}
            sn = 0
            data = {}
            final_term_count = 0
            std_list = {}

            for student in students:
                sn += 1
                fail = 0
                total_mo = 0
                data[sn] = {
                    "session_detail": student,
                    "student_detail": student.student,
                    "reg_no": student.student.reg_no,
                    "name": student.student.name,
                    "grade": student.grade,
                    "section": student.section,
                    "roll_no": student.roll_no
                }

                for key, value in json.loads(term_calculation.term_calculation).items():
                    if value > 0:
                        marks_obtained = MarkObtained.objects.filter(
                            student=student.student, term=key)

                        for mo in marks_obtained:
                            gfm = GradeFullMarks.objects.get(term=mo.term, subject=mo.subject)
                            sub_heavy_weight = Subject.objects.get(id=mo.subject.id)

                            cal_th_mo = cal_th_fm = cal_th_pm = cal_pr_mo = cal_pr_fm = cal_pr_pm = 0

                            if gfm.th_fm > 0:
                                cal_th_mo = (value / 100) * mo.th_mo
                                cal_th_fm = (value / 100) * gfm.th_fm
                                cal_th_pm = (value / 100) * gfm.th_pm

                                if str(mo.subject.id) + "th_fm" not in sub_total_fm_pm:
                                    sub_total_fm_pm[str(mo.subject.id) + "th_fm"] = cal_th_fm
                                    sub_total_fm_pm[str(mo.subject.id) + "pr_fm"] = 0

                            if gfm.pr_fm > 0:
                                cal_pr_mo = (value / 100) * mo.pr_mo
                                cal_pr_fm = (value / 100) * gfm.pr_fm
                                cal_pr_pm = (value / 100) * gfm.pr_pm

                                if str(mo.subject.id) + "pr_fm" not in sub_total_fm_pm:
                                    sub_total_fm_pm[str(mo.subject.id) + "pr_fm"] = cal_pr_fm

                            if str(student.student.reg_no) + "_" + str(mo.subject.id) not in total_gpa_calculation:
                                total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)] = {}

                            pre_text = str(student.student.reg_no) + "_" + str(mo.subject.id) + "_" + str(mo.term.id)
                            pre_total = str(student.student.reg_no) + "_" + str(mo.subject.id)

                            if "th_mo" in total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]:
                                total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)][
                                    "th_mo"] += cal_th_mo
                                total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)][
                                    "th_fm"] += cal_th_fm
                                total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)][
                                    "th_pm"] += cal_th_pm
                            else:
                                total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)][
                                    "th_mo"] = cal_th_mo
                                total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)][
                                    "th_fm"] = cal_th_fm
                                total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)][
                                    "th_pm"] = cal_th_pm

                            if "pr_mo" in total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)]:
                                total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)][
                                    "pr_mo"] += cal_pr_mo
                                total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)][
                                    "pr_fm"] += cal_pr_fm
                                total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)][
                                    "pr_pm"] += cal_pr_pm
                            else:
                                total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)][
                                    "pr_mo"] = cal_pr_mo
                                total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)][
                                    "pr_fm"] = cal_pr_fm
                                total_gpa_calculation[str(student.student.reg_no) + "_" + str(mo.subject.id)][
                                    "pr_pm"] = cal_pr_pm

                            mo_dict[pre_text + "_th_mo"] = cal_th_mo
                            mo_dict[pre_text + "_pr_mo"] = cal_pr_mo

                            if grading_type == 2:
                                ga_gpa = GradeAndGpaNew(cal_th_fm, cal_pr_fm, cal_th_mo, cal_pr_mo,
                                                        mo.subject.heavy_weight, result_type=grading_type)
                                mo_dict[pre_text + "_th_grade"] = ga_gpa.th_grade
                                mo_dict[pre_text + "_pr_grade"] = ga_gpa.pr_grade
                                mo_dict[pre_text + "_th_symbol"] = ga_gpa.th_symbol
                                mo_dict[pre_text + "_pr_symbol"] = ga_gpa.pr_symbol
                            else:
                                ga_gpa = GradeAndGpa(cal_th_fm, cal_pr_fm, cal_th_mo, cal_pr_mo,
                                                     mo.subject.heavy_weight)
                                mo_dict[pre_text + "_th_grade"] = ga_gpa.th_grade
                                mo_dict[pre_text + "_th_symbol"] = ga_gpa.th_symbol
                                mo_dict[pre_text + "_pr_grade"] = ga_gpa.pr_grade
                                mo_dict[pre_text + "_pr_symbol"] = ga_gpa.pr_symbol
                                mo_dict[pre_text + "_total_symbol"] = ga_gpa.total_symbol

                            if mo.term.final_term:
                                final_term_count += 1

                total_gp = 0
                for subject in grade_subjects:
                    if str(student.student.reg_no) + "_" + str(subject.id) in total_gpa_calculation:
                        th_fm = total_gpa_calculation[str(student.student.reg_no) + "_" + str(subject.id)]["th_fm"]
                        pr_fm = total_gpa_calculation[str(student.student.reg_no) + "_" + str(subject.id)]["pr_fm"]
                        th_mo = total_gpa_calculation[str(student.student.reg_no) + "_" + str(subject.id)]["th_mo"]
                        pr_mo = total_gpa_calculation[str(student.student.reg_no) + "_" + str(subject.id)]["pr_mo"]
                    else:
                        th_fm = 0
                        pr_fm = 0
                        th_mo = 0
                        pr_mo = 0

                    g_gpa = GradeAndGpa(th_fm, pr_fm, th_mo, pr_mo, subject.heavy_weight)
                    mo_dict[str(student.student.reg_no) + "_" + str(subject.id) + "_total_grade"] = g_gpa.total_grade
                    mo_dict[
                        str(student.student.reg_no) + "_" + str(subject.id) + "_total_grade_point"] = g_gpa.total_point
                    mo_dict[str(student.student.reg_no) + "_" + str(subject.id) + "_total_symbol"] = g_gpa.total_symbol
                    total_gp += g_gpa.total_point

                    if this_term.final_term and subject.heavy_weight:
                        if float(g_gpa.total_point) < 1.6:
                            fail += 1
                    elif not this_term.final_term and subject.heavy_weight:
                        if float(g_gpa.total_point) < 1.6:
                            fail += 1

                    total_mo += g_gpa.total_mo

                mo_gpa = round(total_gp / grade_subjects.count(), 2)
                if int(grading_type) == 2 and fail > 0:
                    mo_dict[str(student.student.reg_no) + "_gpa"] = 0
                else:
                    mo_dict[str(student.student.reg_no) + "_gpa"] = mo_gpa

                data[sn]["hide"] = False
                if this_term.final_term:
                    if fail > 0:
                        data[sn]["fail"] = True
                        if fail >= 2:
                            mo_dict[
                                str(student.student.reg_no) + "_remarks"] = "Re-examination required for further consideration"
                        else:
                            mo_dict[
                                str(student.student.reg_no) + "_remarks"] = "Can be promoted upon meeting conditions"
                        if data_filter == 1:
                            data[sn]["hide"] = True
                        elif data_filter == 2:
                            data[sn]["hide"] = False
                    else:
                        data[sn]["fail"] = False
                        if data_filter == 2:
                            data[sn]["hide"] = True
                        elif data_filter == 1:
                            data[sn]["hide"] = False
                        mo_dict[str(student.student.reg_no) + "_remarks"] = "Congratulations, You have been promoted"
                        std_list[student.student.reg_no] = total_mo
                else:
                    if fail > 0:
                        data[sn]["fail"] = True
                        if data_filter == 1:
                            data[sn]["hide"] = True
                        elif data_filter == 2:
                            data[sn]["hide"] = False
                        mo_dict[str(student.student.reg_no) + "_remarks"] = "Labour Hard"
                    else:
                        data[sn]["fail"] = False
                        if data_filter == 2:
                            data[sn]["hide"] = True
                        elif data_filter == 1:
                            data[sn]["hide"] = False
                        mo_dict[str(student.student.reg_no) + "_remarks"] = remarks(mo_gpa)
                        std_list[student.student.reg_no] = total_mo

            sorted_d = sorted(std_list.items(), key=lambda x: x[1], reverse=True)
            high_mark = 0
            stat_rank = 0
            std_dict = {}

            for calc in sorted_d:
                if calc[1] == high_mark:
                    high_mark = calc[1]
                    reg_no = calc[0]
                    std_dict[reg_no] = stat_rank
                else:
                    stat_rank += 1
                    high_mark = calc[1]
                    reg_no = calc[0]
                    std_dict[reg_no] = stat_rank

            for rank_reg_no in std_dict:
                mo_dict[str(rank_reg_no) + "_rank"] = std_dict[rank_reg_no]

            board = True if school.id in exam_board else False
            spacing = 8 - subjects.count() if board else 10 - subjects.count()
            subjectcount = range(spacing)

            context = {
                "term_list": term_list,
                "no_of_terms": no_of_terms,
                "no_of_terms_range": range(no_of_terms),
                "no_of_terms_marks_count": no_of_terms * 2,
                "gpa_colspan": 3 + (no_of_terms * 2),
                "school": school,
                "term": this_term,
                "year": this_term.year,
                "data": data,
                "grade": this_grade,
                "section": this_section,
                "subjects": grade_subjects,
                "subjectcount": subjectcount,
                "std_list": data,
                "slogan": slogan,
                "logo": logo,
                "the_space": range(spacing),
                "mo_dict": json.dumps(mo_dict),
                "no_of_subjects": subjects.count(),
                "th_pr_count": subjects.count() * 2,
                "board": board,
                "term_acronym": term_acronym,
            }

        if this_term.final_term:
            return render(request, "panel/grade_ledger_all_final.html", context)
        else:
            return render(request, "panel/grade_ledger_all.html", context)
    else:
        return HttpResponseRedirect("/panel/")


def get_marks_grade_sheet_new_grading_system_exam_updated1(**kwargs):
    print("get_marks_grade_sheet_new_grading_system_exam_updated")
    try:
        no_of_terms = kwargs.get('no_of_terms', 0)
        term_list = kwargs.get('term_list', [])
        term_calculation_input = kwargs.get('term_calculation', '{}')
        if not isinstance(term_calculation_input, str):
            term_calculation_input = getattr(term_calculation_input, 'term_calculation', '{}')
        try:
            term_calculation = json.loads(term_calculation_input)
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Error parsing term_calculation: {str(e)}")
            term_calculation = {}
        pass_fail_filter = kwargs.get('pass_fail_filter', 0)
        students = kwargs.get('students', [])
        grade_subjects = kwargs.get('grade_subjects', [])
        this_term = kwargs.get('this_term')
        this_grade = kwargs.get('this_grade')
        school = kwargs.get('school')
        subjects = kwargs.get('subjects', [])
        this_section = kwargs.get('this_section')
        slogan = kwargs.get('slogan', " ")
        logo = kwargs.get('logo', "")
        term_acronym = kwargs.get('term_acronym', {})

        try:
            year = this_term.year if hasattr(this_term, 'year') else this_term.term.year
            this_session = EduSession.objects.get(year=year)
        except Exception as e:
            print(f"Error getting session: {str(e)}")
            this_session = None

        sn = 0
        data = {}
        mo_dict = {}
        total_gpa_calculation = {}
        sub_total_fm_pm = {}

        for student in students:
            try:
                sn += 1
                reg_no = getattr(student.student, 'reg_no', '')
                
                student_data = {
                    "session_detail": student,
                    "student_detail": student.student,
                    "reg_no": reg_no,
                    "name": getattr(student.student, 'name', ''),
                    "grade": getattr(student, 'grade', ''),
                    "section": getattr(student, 'section', ''),
                    "total_calculation": {},
                    "no_of_school_days": None,
                    "no_of_present_days": None
                }

                try:
                    att = Attendance.objects.get(
                        reg_no=student.student,
                        grade=student.grade,
                        session=this_session,
                        term=this_term
                    )
                    student_data.update({
                        "no_of_school_days": getattr(att, 'no_of_school_days', 0),
                        "no_of_present_days": getattr(att, 'no_of_present_days', 0)
                    })
                except Exception as e:
                    print(f"Attendance error for {reg_no}: {str(e)}")

                for subject in grade_subjects:
                    subject_key = f"{reg_no}_{subject.id}"
                    total_gpa_calculation[subject_key] = {
                        'th_fm': 0, 'th_mo': 0, 'th_pm': 0,
                        'pr_fm': 0, 'pr_mo': 0, 'pr_pm': 0
                    }

                for term_id, weight in term_calculation.items():
                    if weight <= 0:
                        continue

                    try:
                        marks_obtained = MarkObtained.objects.filter(
                            student=student.student,
                            term=term_id
                        )

                        for mo in marks_obtained:
                            try:
                                gfm = GradeFullMarks.objects.get(term=mo.term, subject=mo.subject)
                                key_base = f"{reg_no}_{mo.subject.id}_{mo.term.id}"
                                subject_key = f"{reg_no}_{mo.subject.id}"

                                if getattr(gfm, 'th_fm', 0) > 0:
                                    th_mo = (weight / 100) * getattr(mo, 'th_mo', 0)
                                    th_fm = (weight / 100) * getattr(gfm, 'th_fm', 0)
                                    th_pm = (weight / 100) * getattr(gfm, 'th_pm', 0)

                                    ga_gpa = GradeAndGpaNonGradeTheoryExam(th_fm, th_mo)
                                    mo_dict.update({
                                        f"{key_base}_th_grade": getattr(ga_gpa, 'th_grade', ' '),
                                        f"{key_base}_th_point": getattr(ga_gpa, 'th_point', 0),
                                        f"{key_base}_th_symbol": getattr(ga_gpa, 'th_symbol', ' '),
                                        f"{key_base}_th_mo": round(th_mo, 2)
                                    })

                                    total_gpa_calculation[subject_key]['th_fm'] += th_fm
                                    total_gpa_calculation[subject_key]['th_mo'] += th_mo
                                    total_gpa_calculation[subject_key]['th_pm'] += th_pm

                                if getattr(gfm, 'pr_fm', 0) > 0:
                                    pr_mo = (weight / 100) * getattr(mo, 'pr_mo', 0)
                                    pr_fm = (weight / 100) * getattr(gfm, 'pr_fm', 0)
                                    pr_pm = (weight / 100) * getattr(gfm, 'pr_pm', 0)

                                    ga_gpa = GradeAndGpaNonGradePracticalExam(pr_fm, pr_mo)
                                    mo_dict.update({
                                        f"{key_base}_pr_grade": getattr(ga_gpa, 'pr_grade', ' '),
                                        f"{key_base}_pr_point": getattr(ga_gpa, 'pr_point', 0),
                                        f"{key_base}_pr_symbol": getattr(ga_gpa, 'pr_symbol', ' '),
                                        f"{key_base}_pr_mo": round(pr_mo, 2)
                                    })

                                    total_gpa_calculation[subject_key]['pr_fm'] += pr_fm
                                    total_gpa_calculation[subject_key]['pr_mo'] += pr_mo
                                    total_gpa_calculation[subject_key]['pr_pm'] += pr_pm

                            except Exception as e:
                                print(f"Error processing marks for {reg_no}, subject {mo.subject.id}: {str(e)}")
                                continue

                    except Exception as e:
                        print(f"Error processing term {term_id} for {reg_no}: {str(e)}")
                        continue

                total_grade_points = 0
                passed_subjects = 0
                failed_subjects = 0

                for subject in grade_subjects:
                    try:
                        subject_key = f"{reg_no}_{subject.id}"
                        subject_data = total_gpa_calculation.get(subject_key, {})
                        
                        th_fm = subject_data.get('th_fm', 0)
                        th_mo = subject_data.get('th_mo', 0)
                        th_pm = subject_data.get('th_pm', 0)
                        pr_fm = subject_data.get('pr_fm', 0)
                        pr_mo = subject_data.get('pr_mo', 0)
                        pr_pm = subject_data.get('pr_pm', 0)

                        if th_fm > 0:
                            th_per = th_mo * 100 / th_fm
                        else:
                            th_per = 0
                        if pr_fm > 0:
                            pr_per = pr_mo * 100 / pr_fm
                        else:
                            pr_per = 0

                        passed_theory = th_fm == 0 or (th_per >= 40)
                        passed_practical = pr_fm == 0 or (pr_per >= 40)
                        passed_subject = passed_theory and passed_practical

                        total_grade = "NG"
                        total_symbol = ""
                        total_grade_point = 0

                        if passed_subject:
                            total_grade, total_symbol, total_grade_point = get_grade_point_exam((th_mo + pr_mo) * 100 / (th_fm + pr_fm))

                        mo_dict.update({
                            f"{subject_key}_total_grade": total_grade,
                            f"{subject_key}_total_symbol": total_symbol,
                            f"{subject_key}_total_grade_point": round(total_grade_point, 2),
                            f"{subject_key}_passed": passed_subject
                        })

                        if total_grade_point < 1.6:
                            failed_subjects += 1

                        if passed_subject:
                            total_grade_points += total_grade_point
                            passed_subjects += 1
                        else:
                            failed_subjects += 1

                    except Exception as e:
                        print(f"Error processing subject {getattr(subject, 'id', '?')} for {reg_no}: {str(e)}")
                        failed_subjects += 1
                        continue

                if failed_subjects > 0:
                    gpa = 0
                    remark = this_term.final_term and "Re-examination required for further consideration" or "Labour Hard"
                else:
                    gpa = round(total_grade_points / passed_subjects, 2) if passed_subjects > 0 else 0
                    remark = this_term.final_term and "Congratulations, You have been promoted" or remarks(gpa)

                mo_dict.update({
                    f"{reg_no}_gpa": gpa,
                    f"{reg_no}_passed_all": failed_subjects == 0,
                    f"{reg_no}_remarks": remark
                })

                student_data["hide"] = False
                if this_term.final_term:
                    if failed_subjects > 0:
                        student_data["fail"] = True
                        if pass_fail_filter == 1:
                            student_data["hide"] = True
                        elif pass_fail_filter == 2:
                            student_data["hide"] = False
                    else:
                        student_data["fail"] = False
                        if pass_fail_filter == 2:
                            student_data["hide"] = True
                        elif pass_fail_filter == 1:
                            student_data["hide"] = False
                else:
                    if failed_subjects > 0:
                        student_data["fail"] = True
                        if pass_fail_filter == 1:
                            student_data["hide"] = True
                        elif pass_fail_filter == 2:
                            student_data["hide"] = False
                    else:
                        student_data["fail"] = False
                        if pass_fail_filter == 2:
                            student_data["hide"] = True
                        elif pass_fail_filter == 1:
                            student_data["hide"] = False

                data[sn] = student_data

            except:
                print("SOME ERROR")

        sub_count = len(grade_subjects)
        board = True if school.id in [14, 15] else False
        spacing = 8 - sub_count if board else 10 - sub_count
        subjectcount = range(spacing)

        context = {
            "term_list": term_list,
            "no_of_terms": no_of_terms,
            "no_of_terms_range": range(no_of_terms),
            "no_of_terms_marks_count": no_of_terms * 2,
            "gpa_colspan": 4 + (no_of_terms * 2),
            "school": school,
            "term": this_term,
            "year": this_term.year if hasattr(this_term, 'year') else this_term.term.year,
            "data": data,
            "grade": this_grade,
            "section": this_section,
            "subjects": grade_subjects,
            "subjectcount": subjectcount,
            "std_list": data,
            "slogan": slogan,
            "logo": logo,
            "mo_dict": json.dumps(mo_dict),
            "no_of_subjects": len(subjects),
            "th_pr_count": len(subjects) * 2,
            "board": board,
            "term_acronym": term_acronym,
            "the_space": range(spacing)
        }

        return context

    except Exception as e:
        print(f"Critical error in grade sheet generation: {str(e)}")
        return {
            "term_list": [],
            "no_of_terms": 0,
            "data": {},
            "mo_dict": "{}",
        }


@login_required
def student_progress(request, regno):
    user = request.user
    branchuser, error = get_branch_info(user)
    if error:
        return HttpResponse(f'{error} Click <a href="/">Here</a> to go the homepage.')
    
    school = branchuser.school
    
    try:
        student = Student.objects.get(reg_no=regno, school=school)
    except Student.DoesNotExist:
        return HttpResponse("Student not found or access denied.")
        
    # Get all sessions the student has been enrolled in
    student_sessions = StudentSession.objects.filter(student=student).select_related('session', 'grade', 'section').order_by('session__year')
    
    progress_data = []
    
    # For each session, calculate term-wise averages
    for ss in student_sessions:
        session = ss.session
        grade = ss.grade
        section = ss.section
        
        # Get terms configured for this school in this session
        terms = SchoolTerm.objects.filter(school=school, year=session)
        
        term_data = []
        for term in terms:
            # Query student marks for this session, grade, term
            marks = MarkObtained.objects.filter(
                student=student,
                session=session,
                school=school,
                grade=grade,
                term=term
            )
            
            if not marks.exists():
                continue
                
            # Get full marks configuration for this grade and term
            full_marks_qs = GradeFullMarks.objects.filter(
                school=school,
                session=session,
                grade=grade,
                term=term
            )
            full_marks_map = {fm.subject_id: fm for fm in full_marks_qs}
            
            total_obtained = 0
            total_full = 0
            absent_count = 0
            
            subject_details = []
            for mark in marks:
                fm = full_marks_map.get(mark.subject_id)
                th_fm = fm.th_fm if fm else 100
                pr_fm = fm.pr_fm if fm else 0
                max_sub_mark = th_fm + pr_fm
                
                obtained_sub_mark = mark.th_mo + mark.pr_mo
                if mark.is_absent:
                    absent_count += 1
                    
                total_obtained += obtained_sub_mark
                total_full += max_sub_mark
                
                subject_details.append({
                    'subject_name': mark.subject.subject,
                    'th_mo': mark.th_mo,
                    'pr_mo': mark.pr_mo,
                    'total_mo': obtained_sub_mark,
                    'max_mark': max_sub_mark,
                    'is_absent': mark.is_absent,
                })
                
            percentage = (total_obtained / total_full * 100) if total_full > 0 else 0
            
            term_data.append({
                'term_id': term.id,
                'term_name': term.term_name,
                'total_obtained': total_obtained,
                'total_full': total_full,
                'percentage': round(percentage, 2),
                'absent_count': absent_count,
                'subjects': subject_details,
            })
            
        progress_data.append({
            'session_year': session.year,
            'grade_name': grade.grade_name,
            'section_name': section.section,
            'terms': term_data,
        })
        
    # Calculate difference/progress compared to previous session
    for idx, sess_data in enumerate(progress_data):
        if idx == 0:
            for term in sess_data['terms']:
                term['progress_diff'] = None
            continue
            
        prev_sess = progress_data[idx - 1]
        for term in sess_data['terms']:
            # Find the same term name in previous session
            matching_prev_term = next((t for t in prev_sess['terms'] if t['term_name'] == term['term_name']), None)
            if matching_prev_term:
                diff = term['percentage'] - matching_prev_term['percentage']
                term['progress_diff'] = round(diff, 2)
            else:
                term['progress_diff'] = None

    context = {
        'student': student,
        'branchuser': branchuser,
        'school': school,
        'progress_data': progress_data,
    }
    return render(request, "panel/student_progress.html", context)


@login_required
def manage_grades(request):
    user = request.user
    try:
        branchuser = BranchUser.objects.get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse("Unauthorized", status=403)
        
    school = branchuser.school
    current_session = get_current_session()
    
    FIXED_LEVELS_GRADES = {
        "Pre-Primary": [("PLAYGROUP", 1), ("NURSERY", 2), ("KG 1", 3), ("KG 2", 4)],
        "Primary": [("GRADE 1", 5), ("GRADE 2", 6), ("GRADE 3", 7), ("GRADE 4", 8), ("GRADE 5", 9)],
        "Lower Secondary": [("GRADE 6", 10), ("GRADE 7", 11), ("GRADE 8", 12)],
        "Secondary": [("GRADE 9", 13), ("GRADE 10", 14)],
        "Higher Secondary": [("GRADE 11", 15), ("GRADE 12", 16)],
    }
    
    if request.method == "POST":
        enabled_grades = request.POST.getlist('enabled_grades')
        
        # Deactivate all grades that were NOT selected
        SchoolGrade.objects.filter(school=school).update(active=False)
        
        for level_name, grades_list in FIXED_LEVELS_GRADES.items():
            level_obj, _ = GradeLevel.objects.get_or_create(name=level_name)
            for default_name, weight in grades_list:
                if default_name in enabled_grades:
                    # Get the custom display name provided by user
                    custom_name = request.POST.get(f'custom_name_{default_name}', default_name).strip()
                    if not custom_name:
                        custom_name = default_name
                        
                    # Lookup by unique grade slot identifier (grade_weight) for this school
                    grade_obj = SchoolGrade.objects.filter(school=school, grade_weight=weight).first()
                    if grade_obj:
                        grade_obj.grade_name = custom_name
                        grade_obj.level = level_obj
                        grade_obj.active = True
                        grade_obj.save()
                    else:
                        SchoolGrade.objects.create(
                            school=school,
                            level=level_obj,
                            session=current_session,
                            grade_name=custom_name,
                            active=True,
                            grade_weight=weight
                        )
                        
        messages.success(request, "School levels and custom class terms updated successfully!")
        return redirect('panel:manage_grades')
        
    active_grades_by_weight = {g.grade_weight: g for g in SchoolGrade.objects.filter(school=school, active=True)}
    all_grades_by_weight = {g.grade_weight: g for g in SchoolGrade.objects.filter(school=school)}
    
    # Structure data for template
    levels_data = []
    for level_name, grades_list in FIXED_LEVELS_GRADES.items():
        grades_status = []
        for default_name, weight in grades_list:
            is_active = weight in active_grades_by_weight
            display_name = default_name
            existing_grade = all_grades_by_weight.get(weight)
            if existing_grade:
                display_name = existing_grade.grade_name
                
            grades_status.append({
                'default_name': default_name,
                'display_name': display_name,
                'is_active': is_active
            })
        levels_data.append({
            'name': level_name,
            'grades': grades_status
        })
        
    context = {
        'levels_data': levels_data,
        'branchuser': branchuser,
        'school': school,
    }
    return render(request, "panel/manage_grades.html", context)


@login_required
def manage_standard_subjects(request):
    try:
        branchuser = BranchUser.objects.get(user=request.user)
    except BranchUser.DoesNotExist:
        return HttpResponse("Unauthorized", status=403)
        
    school = branchuser.school
    editing_subject = None

    if request.method == "POST":
        action = request.POST.get('action')
        code = request.POST.get('code', '').strip().upper()
        canonical_name = request.POST.get('canonical_name', '').strip()
        description = request.POST.get('description', '').strip()

        if action == "delete":
            subject_id = request.POST.get('subject_id')
            try:
                sm = SubjectMaster.objects.filter(id=subject_id, school=school).first()
                if not sm:
                    messages.error(request, "Subject not found or does not belong to your school.")
                elif Subject.objects.filter(subject_master=sm).exists():
                    messages.error(request, f"Cannot delete standard subject '{sm.canonical_name}' because it is assigned to one or more grades/sections.")
                else:
                    sm.delete()
                    messages.success(request, f"Standard subject '{sm.canonical_name}' deleted successfully.")
            except SubjectMaster.DoesNotExist:
                messages.error(request, "Subject not found.")
            return redirect('panel:manage_standard_subjects')

        elif action == "edit":
            subject_id = request.POST.get('subject_id')
            try:
                    # Ensure subject belongs to current school
                    sm = SubjectMaster.objects.filter(id=subject_id, school=school).first()
                    if not sm:
                        messages.error(request, "Subject not found or does not belong to your school.")
                    elif not code or not canonical_name:
                        messages.error(request, "Code and Canonical Name are required.")
                    else:
                        # Check unique code (excluding itself)
                        if SubjectMaster.objects.filter(code=code).exclude(id=sm.id).exists():
                            messages.error(request, f"Standard subject with code '{code}' already exists.")
                        # Check unique canonical name (excluding itself)
                        elif SubjectMaster.objects.filter(canonical_name__iexact=canonical_name).exclude(id=sm.id).exists():
                            messages.error(request, f"Standard subject with name '{canonical_name}' already exists.")
                        else:
                            sm.code = code
                            sm.canonical_name = canonical_name
                            sm.description = description
                            sm.save()
                            messages.success(request, f"Standard subject '{canonical_name}' updated successfully.")
                            return redirect('panel:manage_standard_subjects')
            except SubjectMaster.DoesNotExist:
                messages.error(request, "Subject not found.")

        else:  # Create
            if not code or not canonical_name:
                messages.error(request, "Code and Canonical Name are required.")
            else:
                if SubjectMaster.objects.filter(code=code).exists():
                    messages.error(request, f"Standard subject with code '{code}' already exists.")
                elif SubjectMaster.objects.filter(canonical_name__iexact=canonical_name).exists():
                    messages.error(request, f"Standard subject with name '{canonical_name}' already exists.")
                else:
                    SubjectMaster.objects.create(
                        code=code,
                        canonical_name=canonical_name,
                        description=description,
                        school=school
                    )
                    messages.success(request, f"Standard subject '{canonical_name}' created successfully.")
                    return redirect('panel:manage_standard_subjects')

    # GET requests & fallbacks
    edit_id = request.GET.get('edit')
    if edit_id:
        editing_subject = SubjectMaster.objects.filter(id=edit_id, school=school).first()
        # If not found or belongs to another school, ignore silently

    delete_id = request.GET.get('delete')
    if delete_id:
        sm = SubjectMaster.objects.filter(id=delete_id, school=school).first()
        if not sm:
            messages.error(request, "Subject not found or does not belong to your school.")
        elif Subject.objects.filter(subject_master=sm).exists():
            messages.error(request, f"Cannot delete '{sm.canonical_name}' because it is assigned to one or more grades/sections.")
        else:
            sm.delete()
            messages.success(request, f"Standard subject '{sm.canonical_name}' deleted successfully.")
        return redirect('panel:manage_standard_subjects')

    standard_subjects = SubjectMaster.objects.filter(school=school).order_by('canonical_name')
    context = {
        'branchuser': branchuser,
        'school': school,
        'standard_subjects': standard_subjects,
        'editing_subject': editing_subject,
    }
    return render(request, "panel/manage_standard_subjects.html", context)


@login_required
def switch_session(request):
    session_id = request.POST.get('session_id') or request.GET.get('session_id')
    if session_id:
        try:
            edu_session = EduSession.objects.get(id=session_id)
            request.session['active_session_id'] = edu_session.id
            messages.success(request, f"Switched to academic session {edu_session.year}.")
        except EduSession.DoesNotExist:
            messages.error(request, "Invalid academic session.")
            
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('index')


