from django.shortcuts import render
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.views.generic import View
from .forms import SignUpForm
from django.contrib.auth.models import User
from django.contrib.auth import authenticate

from django.shortcuts import redirect
from django.contrib.auth.hashers import make_password
from sms.models import *
import json

from django.db.models import Max
from random import randint
from datetime import datetime
from django.views.generic import View
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required


# Create your views here.
from .func import *

# from .student_reg import my_students
from django.db.models import Q

this_year = 2079
this_session = EduSession.objects.get(year=this_year)


@login_required
def index(request):
    user = request.user
    if CreatedUsers.objects.filter(guardian=user).count() == 1:
        return redirect("/guardian/")
    if SuperBranchUser.objects.filter(user=user).count() == 1:
        return redirect("/superuser/")

    try:
        branchuser = BranchUser.objects.get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )

    # gradelevel= GradeLevel.objects.get(id=level)
    schoolbranch = SchoolBranch.objects.get(id=branchuser.school_id)

    grade_level = GradeLevel.objects.all()
    grades = SchoolGrade.objects.filter(school=schoolbranch).order_by("grade_weight")

    # context = {'grade_level': grade_level, 'branchuser':branchuser,}
    context = {"grade_level": grade_level, "grades": grades, "branchuser": branchuser}
    return render(request, "panel/index.html", context)


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


def profile(request):
    user = request.user
    try:
        obj = BranchUser.objects.get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )
    print(user.id)
    grade_level = GradeLevel.objects.all()
    context = {
        "grade_level": grade_level,
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
    try:
        branchuser = BranchUser.objects.get(user=user)
    except BranchUser.DoesNotExist:
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
            schoolgrade.session = this_session
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

    try:
        branchuser = BranchUser.objects.get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )

    schoolbranch = SchoolBranch.objects.get(id=branchuser.school_id)

    grade_level = GradeLevel.objects.all()
    grades = SchoolGrade.objects.filter(school=schoolbranch).order_by("id")

    avaiablesections = Section.objects.filter(grade=gradelevel)
    gradelevel = SchoolGrade.objects.get(id=int(gradelevel))

    subjects = Subject.objects.filter(branch=branchuser.school, grade=gradelevel.id)
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
            section = True
        elif add == "subject":
            subject = True
        elif add == "student":
            student = True
        elif add == "teacher":
            teacher = True
            # mainuser = BranchUser.objects.get(user=request.user)
            # print(mainuser.id)

            # schoolgrade = SchoolGrade.objects.get(school=mainuser.school, id=gradelevel.id)
            # # allsection = Section.objects.filter(grade=gradelevel)
            # # print(allsection)
            # print(schoolgrade)
            # section = Section.objects.filter(grade=schoolgrade)
            # print(section)
        else:
            return HttpResponse(
                'Sorry! Something went wrong. Click <a href="/">Here</a> to go the homepage.'
            )

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
        "avaiablesections": avaiablesections,
        "subjects": subjects,
        "list_student": list_student,
    }
    return render(request, "panel/listgradeitems.html", context)


@login_required
def addsection(request):
    if request.method == "POST":
        gradelevel = request.POST.get("gradelevel")
        redurl = request.POST.get("redurl")
        sectionname = request.POST.get("sectionname")
        print(gradelevel)

        grade = SchoolGrade.objects.get(id=gradelevel)

        Section.objects.get_or_create(grade=grade, section=sectionname.upper())

        return HttpResponseRedirect(redurl)

    else:
        return HttpResponse(
            'Sorry! Something went wrong. Click <a href="/">Here</a> to go the homepage.'
        )


@login_required
def addsubject(request):
    user = request.user
    if request.method == "POST":
        gradelevel = request.POST.get("gradelevel")
        redurl = request.POST.get("redurl")
        subject = request.POST.get("subjectname")
        print(gradelevel)

        grade = SchoolGrade.objects.get(id=gradelevel)

        userbranch = BranchUser.objects.get(user=user)

        print(userbranch.school)

        Subject.objects.get_or_create(
            branch=userbranch.school, grade=grade, subject=subject.upper()
        )

        # Section.objects.get_or_create(grade=grade,section=sectionname.upper())

        return HttpResponseRedirect(redurl)

    else:
        return HttpResponse(
            'Sorry! Something went wrong. Click <a href="/">Here</a> to go the homepage.'
        )


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
        userbranch = BranchUser.objects.get(user=user)

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


# @login_required
# def addstudent(request):
#     user = request.user
#     if request.method == "POST":
#         gradelevel = request.POST.get("gradelevel")
#         redurl = request.POST.get("redurl")
#
#         # gradelevel = SchoolGrade.objects.get(id=gradelevel)
#
#         studentname = request.POST.get("studentname")
#         rollno = request.POST.get("rollno", 1)
#         gender = request.POST.get("gender")
#         section = request.POST.get("section")
#         dateofbirth = request.POST.get("dateofbirth", "")
#
#         tempaddr = request.POST.get("tempaddr", "")
#         peraddr = request.POST.get("peraddr", "")
#         fathersname = request.POST.get("fathersname", "")
#         fathersphone = request.POST.get("fathersphone", 9800000000)
#         mothersname = request.POST.get("mothersname", "")
#         mothersphone = request.POST.get("mothersphone", 9800000000)
#         parentsemail = request.POST.get("parentsemail", "demoemail@hamro.com")
#
#         # print(gradelevel, grade, section)
#
#         grade = SchoolGrade.objects.get(id=gradelevel)
#         userbranch = BranchUser.objects.get(user=user)
#         section = Section.objects.get(id=section)
#         school = userbranch.school
#
#         new_reg_no = findNewRegNo(userbranch.school.id)
#         pincode = randint(1000, 9999)
#
#         student = Student()
#         student.reg_no = new_reg_no
#         student.pin_code = pincode
#         student.roll_no = rollno
#         student.name = studentname
#         student.gender = gender
#         # student.dob = dateofbirth #datetime.strptime(dateofbirth, '%y/%m/%d')
#         # student.temporary_address = tempaddr
#         # student.permanent_address = peraddr
#         student.grade = grade
#         student.section = section
#         # student.fathers_name = fathersname
#         # student.fathers_phone = fathersphone
#         # student.mothers_name = mothersname
#         # student.mothers_phone = mothersphone
#         # student.parents_email = parentsemail
#         student.school = userbranch.school
#         print("going to save student")
#
#         student.save()
#
#         # print(new_reg_no)
#         # print('ADD STUDENT')
#         # print(gradelevel, studentname, gender)#, username, gradelevel, userbranch.school.id, section)
#         # print(userbranch.school)
#
#         # BranchUser.objects.filter()
#
#         # Subject.objects.get_or_create(branch=userbranch.school, grade=grade,subject=subject.upper())
#
#         # Section.objects.get_or_create(grade=grade,section=sectionname.upper())
#
#         for key, value in request.POST.items():
#             print("Key: %s" % (key))
#             # print(f'Key: {key}') in Python >= 3.7
#             print("Value %s" % (value))
#             # print(f'Value: {value}') in Python >= 3.7
#
#         return HttpResponseRedirect(redurl)
#
#     else:
#         return HttpResponse(
#             'Sorry! Something went wrong. Click <a href="/">Here</a> to go the homepage.'
#         )


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
    branchuser = BranchUser.objects.get(user=user)
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


def printentrancecard(request):
    user = request.user
    if user.id != 16:
        width = 50
        logo = "https://grihakarya.hamro.com/samataeast/images/logo1.jpg"
    else:
        width = 50
        logo = "http://school3.nep.onl/wp-content/uploads/sites/8/2019/12/51150449_1650894705012798_8214025074135531520_n.png"
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)

    if request.method == "POST":
        term = request.POST.get("term")
        whattype = request.POST.get("whattype")
        if whattype == "True":
            whattype = True
        else:
            whattype = False
        print(term)
        students = Student.objects.filter(school=school, status=True).exclude(grade=110)
        count = students.count()
        print(students)
        term_exam = SchoolTerm.objects.get(id=term)

        if whattype:
            context = {
                "school": school,
                "students": students,
                "count": count,
                "term_exam": term_exam,
                "year": this_year,
                "logo": logo,
                "width": width,
                "blankcount": "12345678",
            }

            return render(request, "panel/entrancecard.html", context)
        else:
            context = {
                "school": school,
                "term_exam": term_exam,
                "year": this_year,
                "logo": logo,
                "width": width,
                "blankcount": "12345678",
            }

            return render(request, "panel/entrancecardblank.html", context)

    exam_types = SchoolTerm.objects.filter(school=branchuser.school)

    grades = SchoolGrade.objects.filter(school=branchuser.school)

    context = {"grades": grades, "school": school, "exam_types": exam_types}
    return render(request, "panel/entrancecardbase.html", context)

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
#         }
#         return render(request, "panel/entrancecard.html", context)


@login_required
def studentdetail(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    students = Student.objects.filter(school=school, status=True).order_by(
        "grade", "section"
    )

    context = {"school": school, "students": students}
    return render(request, "panel/student_detail_print.html", context)


@login_required
def printmarksform(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)

    if request.method == "POST":
        term = request.POST.get("term")
        grade = request.POST.get("grade")
        section = request.POST.get("section")
        print(term, grade, section)
        students = Student.objects.filter(
            school=school, grade=grade, section=section, status=True
        )
        count = students.count()
        # print(students)
        term_exam = SchoolTerm.objects.get(id=term)
        grade = SchoolGrade.objects.get(id=grade)
        section = Section.objects.get(id=section)

        context = {
            "school": school,
            "students": students,
            "count": count,
            "term_exam": term_exam,
            "grade": grade,
            "section": section,
        }
        return render(request, "panel/printmarksform.html", context)

    exam_types = SchoolTerm.objects.filter(school=branchuser.school)

    grades = SchoolGrade.objects.filter(school=branchuser.school).order_by("id")
    section_list = {}
    for grade in grades:
        sections = Section.objects.filter(grade=grade)
        new_dict = {}
        for section in sections:
            new_dict[str(section.id)] = section.section

        section_list[str(grade.id)] = new_dict

    section_list = json.dumps(section_list)

    # print(section_list)

    context = {
        "grades": grades,
        "school": school,
        "exam_types": exam_types,
        "section_list": section_list,
    }
    return render(request, "panel/printmarksformbase.html", context)


@login_required
def letterpincode(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    students = Student.objects.filter(school=school, status=True).exclude(grade=110)
    # for student in all_students:
    #    if student.grade

    context = {"school": school, "students": students}
    return render(request, "panel/letter_pincode.html", context)


@login_required
def fullmarks(request):
    user = request.user
    try:
        branchuser = BranchUser.objects.get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )

    # school = SchoolBranch.objects.get(id=branchuser.school)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    exam_types = SchoolTerm.objects.filter(school=branchuser.school)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    exam_types = SchoolTerm.objects.filter(school=branchuser.school)
    grades = SchoolGrade.objects.filter(school=branchuser.school).order_by("id")
    edusession = EduSession.objects.get(year=this_year)

    context = {
        "grades": grades,
        "school": school,
        "exam_types": exam_types,
        "edusession": edusession,
    }

    return render(request, "panel/marks.html", context)


@login_required
def inputfullmarksredirector(request):
    if request.method == "POST":
        user = request.user
        try:
            branchuser = BranchUser.objects.get(user=user)
        except BranchUser.DoesNotExist:
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
    try:
        branchuser = BranchUser.objects.get(user=user)

    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )

    school = SchoolBranch.objects.get(id=branchuser.school.id)
    exam_term = SchoolTerm.objects.get(id=term)
    grade = SchoolGrade.objects.get(id=grade)
    edusession = EduSession.objects.get(year=this_year)

    subjects = Subject.objects.filter(branch=school, grade=grade, status=True).order_by(
        "id"
    )

    if (
            GradeFullMarks.objects.filter(
                session=edusession, school=school, grade=grade, term=exam_term
            ).count()
            == 0
    ):
        gs = False
    else:
        gs = True

        subjects = GradeFullMarks.objects.filter(
            session=edusession, school=school, grade=grade, term=exam_term
        )

    if request.method == "POST":
        for subject in subjects:
            this_subject = str(subject.id)
            th_full = request.POST.get(this_subject + "_th_full")
            pr_full = request.POST.get(this_subject + "_pr_full")

            th_pass = request.POST.get(this_subject + "_th_pass")
            pr_pass = request.POST.get(this_subject + "_pr_pass")

            if (
                    GradeFullMarks.objects.filter(
                        session=edusession,
                        school=school,
                        grade=grade,
                        term=exam_term,
                        subject=subject,
                    ).count()
                    == 0
            ):
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

    context = {
        "grade": grade,
        "school": school,
        "exam_term": exam_term,
        "edusession": edusession,
        "subjects": subjects,
        "gs": gs,
    }

    return render(request, "panel/addfullmarks.html", context)


def addfullmarksedit(request, grade, term):
    the_grade = grade
    the_term = term
    user = request.user
    try:
        branchuser = BranchUser.objects.get(user=user)

    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )

    school = SchoolBranch.objects.get(id=branchuser.school.id)
    exam_term = SchoolTerm.objects.get(id=term)
    grade = SchoolGrade.objects.get(id=grade)
    edusession = EduSession.objects.get(year=this_year)

    subjects = Subject.objects.filter(branch=school, grade=grade, status=True).order_by(
        "id"
    )

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
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)

    grade_level = GradeLevel.objects.all()
    grades = SchoolGrade.objects.filter(school=school).order_by("id")

    if request.method == "POST":
        term = request.POST.get("term")
        grade = request.POST.get("grade")
        section = request.POST.get("section")
        praMarks = request.POST.get("praMarks")
        this_grade = SchoolGrade.objects.get(id=grade)
        subjects = Subject.objects.filter(
            branch=school, grade=this_grade, status=True
        ).order_by("id")
        print(term, grade, section)
        print(subjects)
        print(praMarks)
        # students = Student.objects.filter(school=school, grade=grade, section=section)
        # count = students.count()
        # print(students)
        term_exam = SchoolTerm.objects.get(id=term)
        grade = SchoolGrade.objects.get(id=grade)
        section = Section.objects.get(id=section)

        context = {
            "school": school,
            "term_exam": term_exam,
            "grade": grade,
            "section": section,
            "subjects": subjects,
            "praMarks": praMarks,
            "grade_level": grade_level,
            "grades": grades,
            "branchuser": branchuser
        }
        return render(request, "panel/subjectwiseselectsubject.html", context)

    exam_types = SchoolTerm.objects.filter(school=branchuser.school)

    grades = SchoolGrade.objects.filter(school=branchuser.school).order_by("id")
    section_list = {}
    for grade in grades:
        sections = Section.objects.filter(grade=grade)
        new_dict = {}
        for section in sections:
            new_dict[str(section.id)] = section.section

        section_list[str(grade.id)] = new_dict

    section_list = json.dumps(section_list)

    # print(section_list)

    context = {
        "grades": grades,
        "school": school,
        "exam_types": exam_types,
        "section_list": section_list,
        "grade_level": grade_level,
        "grades": grades,
        "branchuser": branchuser
    }
    return render(request, "panel/subjectwisemarksformbase.html", context)


@login_required
def subjectwisemarksentry(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)

    if request.method == "POST":
        term = request.POST.get("term")
        grade = request.POST.get("grade")
        section = request.POST.get("section")
        praMarks = request.POST.get("praMarks")
        subject = request.POST.get("subject")
        this_grade = SchoolGrade.objects.get(id=grade)
        subjects = Subject.objects.filter(branch=school, grade=this_grade, status=True)
        grade = SchoolGrade.objects.get(id=grade)
        section = Section.objects.get(id=section)
        subject = Subject.objects.get(id=subject)
        term_exam = SchoolTerm.objects.get(id=term)
        students = Student.objects.filter(
            school=school, grade=grade, section=section, status=True
        )
        # count = students.count()
        fullmark = GradeFullMarks.objects.get(
            school=school,
            grade=grade,
            session=this_session,
            term=term_exam,
            subject=subject,
        )
        new_desc = {}
        for student in students:
            new_desc[student.reg_no] = {}
            new_desc[student.reg_no]["name"] = student.name
            print(student.reg_no)
            if request.POST.get("submittedhere") == "1":
                # print('submittedhere')
                th_mo = request.POST.get(str(student.reg_no) + "_th")
                if th_mo == "":
                    th_mo = 0
                else:
                    th_mo = int(th_mo)

                pr_mo = request.POST.get(str(student.reg_no) + "_pr", 0)

                # if praMarks == '1':

                if pr_mo == "":
                    pr_mo = 0
                else:
                    pr_mo = int(pr_mo)
                # else:
                #     pr_mo = 0

                find_mo = MarkObtained.objects.filter(
                    student=int(student.reg_no),
                    school=school.id,
                    grade=grade.id,
                    term=term_exam.id,
                    subject=subject.id,
                    session=this_session,
                ).count()
                # print('111111111111111111111111111111',find_mo)
                if find_mo == 1:
                    the_mo = MarkObtained.objects.get(
                        student=int(student.reg_no),
                        school=school.id,
                        grade=grade.id,
                        term=term_exam.id,
                        subject=subject.id,
                        session=this_session,
                    )
                    the_mo.th_mo = th_mo
                    the_mo.pr_mo = pr_mo
                    the_mo.save()

                    new_desc[student.reg_no]["th_mo"] = th_mo
                    new_desc[student.reg_no]["pr_mo"] = pr_mo
                else:
                    the_mo = MarkObtained()
                    the_mo.student = int(student.reg_no)
                    the_mo.session = this_session
                    the_mo.school = school.id
                    the_mo.grade = grade.id
                    the_mo.term = term_exam.id
                    the_mo.subject = subject.id
                    the_mo.th_mo = th_mo
                    the_mo.pr_mo = pr_mo

                    the_mo.save()

                    new_desc[student.reg_no]["th_mo"] = th_mo
                    new_desc[student.reg_no]["pr_mo"] = pr_mo

            else:
                mo_by_students = MarkObtained.objects.filter(
                    student=int(student.reg_no),
                    school=school.id,
                    grade=grade.id,
                    term=term_exam.id,
                    subject=subject.id,
                    session=this_session,
                )

                if mo_by_students.count() == 0:
                    the_mo = MarkObtained()
                    the_mo.student = int(student.reg_no)
                    the_mo.session = this_session
                    the_mo.school = school.id
                    the_mo.grade = grade.id
                    the_mo.term = term_exam.id
                    the_mo.subject = subject.id
                    the_mo.th_mo = 0
                    the_mo.pr_mo = 0

                    the_mo.save()

                    new_desc[student.reg_no]["th_mo"] = 0
                    new_desc[student.reg_no]["pr_mo"] = 0
                else:
                    mo_by_students = MarkObtained.objects.get(
                        student=int(student.reg_no),
                        school=school.id,
                        grade=grade.id,
                        term=term_exam.id,
                        subject=subject.id,
                        session=this_session,
                    )
                    new_desc[student.reg_no]["th_mo"] = mo_by_students.th_mo
                    new_desc[student.reg_no]["pr_mo"] = mo_by_students.pr_mo
        else:
            # print(mo_by_students)

            mo_by_students = MarkObtained.objects.filter(
                school=school.id,
                grade=grade.id,
                term=term_exam.id,
                subject=subject.id,
                session=this_session,
            )
        ###
        # mo_by_students = MarkObtained.objects.filter(
        #     school= school.id,
        #     grade=grade.id,
        #     term=term_exam.id,
        #     subject=subject.id,
        #     session = this_session,
        # ).select_related('student').filter(section=section)

        ###
        # print(praMarks)
        if fullmark.pr_fm > 0:
            praMarks = True
        else:
            praMarks = False
        # print(praMarks)

        # grade = SchoolGrade.objects.get(id=grade)
        # section = Section.objects.get(id=section)

        context = {
            "school": school,
            "students": students,
            "term_exam": term_exam,
            "grade": grade,
            "section": section,
            "subject": subject,
            "praMarks": praMarks,
            "fullmark": fullmark,
            "mo_by_students": mo_by_students,
            "new_desc": new_desc,
        }
        return render(request, "panel/subjectwisemarksform.html", context)
    else:
        return HttpResponse(
            'Sorry! Something went wrong. Click <a href="/">Here</a> to go the homepage.'
        )


@login_required
def submitsubjectwise(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)

    if request.method == "POST":
        term = request.POST.get("term")
        grade = request.POST.get("grade")
        section = request.POST.get("section")
        praMarks = request.POST.get("praMarks")
        subject = request.POST.get("subject")

        this_grade = SchoolGrade.objects.get(id=grade)
        subjects = Subject.objects.filter(branch=school, grade=this_grade)
        grade = SchoolGrade.objects.get(id=grade)
        section = Section.objects.get(id=section)
        subject = Subject.objects.get(id=subject)
        term_exam = SchoolTerm.objects.get(id=term)
        students = Student.objects.filter(school=school, grade=grade, section=section)
        fullmark = GradeFullMarks.objects.get(
            school=school,
            grade=grade,
            session=this_session,
            term=term_exam,
            subject=subject,
        )

        if praMarks == "1":
            praMarks = True
        else:
            praMarks = False

        for student in students:
            find_mo = MarkObtained.objects.filter(
                student=int(student.reg_no),
                school=school,
                grade=grade,
                term=term_exam,
                subject=subject,
            ).count()
            if find_mo == 0:
                marksobtained = MarkObtained()

                th_mo = request.POST.get(str(student.reg_no) + "_th")
                if th_mo == "":
                    th_mo = 0
                else:
                    th_mo = int(th_mo)

                if praMarks:
                    pr_mo = request.POST.get(str(student.reg_no) + "_pr")
                    if pr_mo == "":
                        pr_mo = 0
                    else:
                        pr_mo = int(pr_mo)
                else:
                    pr_mo = 0

                marksobtained.student = int(student.reg_no)
                marksobtained.session = this_session
                marksobtained.school = school
                marksobtained.grade = grade
                marksobtained.term = term_exam
                marksobtained.subject = subject
                marksobtained.th_mo = th_mo
                marksobtained.pr_mo = pr_mo
                marksobtained.save()
                print(marksobtained)
        # grade = SchoolGrade.objects.get(id=grade)
        # section = Section.objects.get(id=section)

        context = {
            "school": school,
            "students": students,
            "term_exam": term_exam,
            "grade": grade,
            "section": section,
            "subject": subject,
            "praMarks": praMarks,
            "fullmark": fullmark,
        }
        return render(request, "panel/subjectwisemarksform.html", context)
    else:
        return HttpResponse(
            'Sorry! Something went wrong. Click <a href="/">Here</a> to go the homepage.'
        )


@login_required
def edgradeitems(request, gradelevel):
    # request.session['this_session'] = this_session
    user = request.user
    message = " "
    success = ""
    subjects = ""
    allsection = ""
    student = ""

    try:
        branchuser = BranchUser.objects.get(user=user)
    except BranchUser.DoesNotExist:
        return HttpResponse(
            'Sorry! You are not allowed to access this page. Click <a href="/">Here</a> to go the homepage.'
        )

    schoolbranch = SchoolBranch.objects.get(id=branchuser.school_id)

    grade_level = GradeLevel.objects.all()
    grades = SchoolGrade.objects.filter(school=schoolbranch).order_by("id")

    avaiablesections = Section.objects.filter(grade=gradelevel)
    gradelevel = SchoolGrade.objects.get(id=int(gradelevel))
    # this_grade =

    subjects = Subject.objects.filter(branch=branchuser.school, grade=gradelevel.id).order_by('id')
    students = StudentSession.objects.filter(grade=gradelevel.id, status=True).select_related('student', 'section').order_by("section", "roll_no")

    # Teacher access logic
    teacher_subject_access = TeacherSubjectAccess.objects.filter(
        session=this_session, grade=gradelevel
    ).select_related('teacher', 'subject', 'section')
    
    teacher_access = {}
    for tsa in teacher_subject_access:
        sub_id = tsa.subject_id
        t_id = tsa.teacher_id
        sec_id = tsa.section_id
        
        if sub_id not in teacher_access:
            teacher_access[sub_id] = {}
        if t_id not in teacher_access[sub_id]:
            teacher_access[sub_id][t_id] = {}
            
        teacher_access[sub_id][t_id][sec_id] = {
            'name': f"{tsa.teacher.first_name} {tsa.teacher.last_name}",
            'section': tsa.section.section,
            'status': tsa.status,
            'photo': tsa.teacher.profile.photo.url if hasattr(tsa.teacher, 'profile') and tsa.teacher.profile.photo else None
        }

    section = list_attendance = list_subject = False
    teacher = teachers = subject = student = False
    list_student = ed_subject = hw_subject = attendance = student_by_reg = change_name = assign_section = assign_house = False
    edsubject = hwsubject = cn_subject = houses = this_term = ""
    this_section = None

    if request.method == "GET" and "list" in request.GET:
        list_item = request.GET["list"]

        if list_item == "student":
            list_student = True
        if list_item == "attendance":
            list_attendance = True
            if "term" in request.GET:
                try:
                    this_term = SchoolTerm.objects.get(id=request.GET["term"])
                except:
                    pass
        if list_item == "subject":
            list_subject = True

    if request.method == "GET" and "assign" in request.GET:
        assign = request.GET["assign"]
        if assign == "house":
            assign_house = True
            houses = House.objects.filter(school=schoolbranch)
        elif assign == "section":
            assign_section = True
        elif assign == "teacher":
            teacher = True
            teachers = Teacher.objects.filter(added_by=user)

    if request.method == "GET" and "cn" in request.GET:
        cn = request.GET["cn"]
        cn_subject = Subject.objects.filter(id=cn, branch=schoolbranch).first()
        if cn_subject:
            change_name = True

    if request.method == "GET" and "uta" in request.GET:
        uta = request.GET["uta"]
        tsa_toggle = TeacherSubjectAccess.objects.filter(
            session=this_session, teacher_id=uta, 
            subject_id=request.GET.get("sub"), 
            section_id=request.GET.get("sec")
        ).first()
        if tsa_toggle:
            tsa_toggle.status = not tsa_toggle.status
            tsa_toggle.save()
            return redirect(request.path)

    if request.method == "GET" and "ed" in request.GET:
        ed = request.GET["ed"]

        find_subject = Subject.objects.filter(
            branch=schoolbranch, grade=gradelevel, id=ed
        ).count()

        if find_subject == 1:
            ed_subject = True

            edsubject = Subject.objects.get(
                branch=schoolbranch, grade=gradelevel, id=ed
            )

    if request.method == "GET" and "hw" in request.GET:
        hw = request.GET["hw"]

        find_subject = Subject.objects.filter(
            branch=schoolbranch, grade=gradelevel, id=hw
        ).count()

        if find_subject == 1:
            hw_subject = True

            hwsubject = Subject.objects.get(
                branch=schoolbranch, grade=gradelevel, id=hw
            )

    if list_attendance and this_term:
        students = Attendance.objects.filter(grade=gradelevel, session=this_session, term=this_term)
        if this_section:
            # Filter attendance by students in this section
            section_students = StudentSession.objects.filter(grade=gradelevel, session=this_session, section=this_section).values_list('student__reg_no', flat=True)
            students = students.filter(reg_no__in=section_students)

    if request.method == "GET" and "add" in request.GET:
        add = request.GET["add"]

        if add == "section":
            section = True
        elif add == "subject":
            subject = True
        elif add == "student":
            student = True
        elif add == "teacher":
            teacher = True
        elif add == "attendance":
            students = students.filter(status=True)
            attendance = True
            if "term" in request.GET:
                try:
                    this_term = SchoolTerm.objects.get(id=request.GET["term"])
                except SchoolTerm.DoesNotExist:
                    this_term = None
            if "section" in request.GET:
                this_section = avaiablesections.filter(id=request.GET["section"]).first()
                if this_section:
                    students = students.filter(section=this_section)
        elif add == "student_by_reg":
            student_by_reg = True
            # mainuser = BranchUser.objects.get(user=request.user)
            # print(mainuser.id)

            # schoolgrade = SchoolGrade.objects.get(school=mainuser.school, id=gradelevel.id)
            # # allsection = Section.objects.filter(grade=gradelevel)
            # # print(allsection)
            # print(schoolgrade)
            # section = Section.objects.filter(grade=schoolgrade)
            # print(section)
        else:
            return HttpResponse(
                'Sorry! Something went wrong. Click <a href="/panel/">Here</a> to go the homepage.'
            )

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
        "schoolbranch": schoolbranch,
        "student_by_reg": student_by_reg,
        "teacher_access": teacher_access,
        "teachers": teachers,
        "cn_subject": cn_subject,
        "change_name": change_name,
        "assign_house": assign_house,
        "assign_section": assign_section,
        "houses": houses,
        "exam_types": exam_types,
        "this_term": this_term,
    }
    return render(request, "panel/listgradeitems.html", context)


def addAttendance(request, grade=None):
    # print(request.POST)
    if request.method == "POST":
        grade = request.POST.get("grade")
        grade = SchoolGrade.objects.get(id=grade)
        session = this_session
        no_of_school_days = int(request.POST.get("no_of_school_days"))
        data_type = request.POST.get("data_type")
        students = Student.objects.filter(grade=grade)
        thou = 1000
        for student in students:
            std_att = request.POST.get(str(student.reg_no)).strip()
            if std_att == "" or std_att == "":
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

            # print('Student: ', student, 'Session: ', session, 'Grade: ', grade, 'School Days: ', no_of_school_days, 'Present Days: ', present_days, 'Absent Days: ', absent_days)
            try:
                created = Attendance.objects.get(
                    reg_no=student, grade=grade, session=session,
                )
                if std_att != 0:
                    created.no_of_school_days = no_of_school_days
                    created.no_of_present_days = present_days
                    created.no_of_absent_days = absent_days
                    created.save()

            except:
                attend = Attendance()
                attend.reg_no = student
                attend.grade = grade
                attend.session = session
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
    edusession = EduSession.objects.all()
    exam_types = SchoolTerm.objects.filter(
        year=this_session, school=school, active=True
    )
    grades = SchoolGrade.objects.filter(school=school, active=True).order_by("id")

    section_list = {}
    for grade in grades:
        sections = Section.objects.filter(grade=grade)
        new_dict = {}
        for section in sections:
            new_dict[str(section.id)] = section.section

        section_list[str(grade.id)] = new_dict

    section_list = json.dumps(section_list)

    context = {
        "edusession": edusession,
        "school": school,
        "exam_types": exam_types,
        "grades": grades,
        "section_list": section_list,
    }
    return render(request, "panel/printledger.html", context)


@login_required
def printledgerpreview(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
    if request.method == "POST":
        edusession = request.POST.get("edusession")
        term = request.POST.get("term")
        grade = request.POST.get("grade")
        section = request.POST.get("section")

        this_grade = SchoolGrade.objects.get(id=grade)
        this_session = EduSession.objects.get(id=edusession)
        this_term = SchoolTerm.objects.get(id=term)
        this_section = Section.objects.get(id=section)
        subjects = Subject.objects.filter(branch=school, grade=this_grade, status=True)

        print(subjects)

        print(this_grade)
        grade_subjects = Subject.objects.filter(branch=school, grade=grade, status=True)
        # for grade in grade_subjects:
        #     print(grade)
        counter = 1
        students = Student.objects.filter(
            school=school, grade=this_grade, section=this_section, status=True
        )
        mo_object = {}
        for student in students:
            marks_obtained = MarkObtained.objects.filter(
                student=student.reg_no, term=term, session=this_session
            )  # grade=grade, term=term, session=this_session)
            print(student.reg_no)
            mo_object[counter] = {}
            mo_object[counter]["reg_no"] = student.reg_no
            mo_object[counter]["name"] = student.name

            mo_object[counter]["mo_object"] = {}
            for mo in marks_obtained:
                print(mo.subject, mo)
                # print(grade_subjects[mo.subject])

                mo_object[counter]["mo_object"][mo.subject] = {}
                mo_object[counter]["mo_object"][mo.subject]["th_mo"] = mo.th_mo
                mo_object[counter]["mo_object"][mo.subject]["pr_mo"] = mo.pr_mo

            counter += 1

        # marks_obtained_by_students = MarkObtained.objects.filter(school=school.id, grade=grade, session_id=this_session.id, term=term)
        # for mobs in marks_obtained_by_students:
        #     print(mobs.reg_no)
        # print(mo_object)
        context = {"grade_subjects": grade_subjects, "mo_object": mo_object}
        return render(request, "panel/printledgerpreview.html", context)
    else:
        return HttpResponseRedirect("/panel/")


@login_required
def printledgernow(request):
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

        subjects = Subject.objects.filter(
            branch=school, grade=this_grade, status=True
        ).order_by("id")
        subjectcount = ""
        for subject in subjects:
            subjectcount += "1"
        if this_section == False:
            students = Student.objects.filter(
                school=school, grade=this_grade, status=True
            )
            calculated_rank = calculaterank(school.id, this_session, grade, term)
        else:
            students = Student.objects.filter(
                school=school, grade=this_grade, section=this_section, status=True
            )
            calculated_rank = calculaterank(
                school.id, this_session, grade, term, this_section
            )
            print(school.id, this_session, grade, term, this_section)
            print("calculated rank ", calculated_rank)
        sn = 0
        data = {}
        for student in students:
            sn += 1
            data[sn] = {}
            data[sn]["reg_no"] = student.reg_no
            data[sn]["name"] = student.name
            data[sn]["section"] = student.section
            if student.reg_no in calculated_rank:
                data[sn]["rank"] = calculated_rank[student.reg_no]
            else:
                data[sn]["rank"] = "-"

            if printtype == 2:
                # sd = summarizedResult(school, term, grade, student.reg_no)
                sd = detailResult(school, term, grade, student.reg_no, printtype)
                data[sn]["mo_th"] = sd["mo_th"]
                data[sn]["mo_pr"] = sd["mo_pr"]
                data[sn]["total"] = sd["total"]
                data[sn]["gp"] = sd["gp"]
                # print(summarizedResult)
                print("Summarized Result")
            else:
                sd = detailResult(school, term, grade, student.reg_no, printtype)
                data[sn]["mo_th"] = sd["mo_th"]
                data[sn]["mo_pr"] = sd["mo_pr"]
                data[sn]["total"] = sd["total"]
                data[sn]["gp"] = sd["gp"]
                data[sn]["subjects"] = sd["subjects"]

                # print(detailResult, subjectcount)
                print("Detail Result")

        context = {
            "school": school,
            "term": this_term,
            "year": this_term.year,
            "data": data,
            "grade": this_grade,
            "section": this_section,
            "subjects": subjects,
            "subjectcount": subjectcount,
        }
        if printtype == 2:
            return render(request, "panel/printledgernow_summarized.html", context)
        else:
            return render(request, "panel/printledgernow_detailed.html", context)
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
def printgradesheetnow2078(request):
    user = request.user
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)
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
        logo = "https://cdn.hamro.com/simsnepal/logos/paramount.png"
    elif school.id >= 16 and school.id <= 22:
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
            students = Student.objects.filter(
                school=school, grade=this_grade, status=True
            )
            calculated_rank = calculaterank(school.id, this_session, grade, term)
        else:
            students = Student.objects.filter(
                school=school, grade=this_grade, section=this_section, status=True
            )
            calculated_rank = calculaterank(
                school.id, this_session, grade, term, this_section
            )
            # print(school.id, this_session, grade, term, this_section)
            # print('calculated rank ', calculated_rank)
        sn = 0
        data = {}
        for student in students:
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

    grade_level = GradeLevel.objects.all()
    grades = SchoolGrade.objects.filter(school=schoolbranch).order_by("id")

    school_terms = SchoolTerm.objects.filter(
        school=school, year=this_session, active=True
    )

    if request.method == "POST":
        termname = request.POST.get("termname")
        url = request.POST.get("redurl")

        termname = termname.title()

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
            term.save()
        else:
            term = SchoolTerm()
            term.school = school
            term.year = this_session
            term.term_name = termname

            term.save()

        return HttpResponseRedirect(url)

    addterm = False
    listterm = False

    if request.method == "GET" and "action" in request.GET:
        action = request.GET["action"]

        if action == "addterm":
            addterm = True
        elif action == "listterm":
            listterm = True
    else:
        return HttpResponseRedirect("/panel/terms/?action=listterm")

    context = {
        "grade_level": grade_level,
        "grades": grades,
        "branchuser": branchuser,
        "school": school,
        "terms": school_terms,
        "addterm": addterm,
        "listterm": listterm,
    }
    return render(request, "panel/termmanagement.html", context)


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
                    schoolresulttype.resulttype = result
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
                checks = request.POST.getlist("checks[]")
                # checks = int(checks)

                checks = [int(i) for i in checks]

                checks = json.dumps(checks)

                if LiveResult.objects.filter(school=school).count() == 0:
                    liveresult = LiveResult()
                    liveresult.school = school
                    liveresult.term = examtype
                    liveresult.gradelist = checks
                    liveresult.status = livestatus
                    liveresult.save()

                    live_result_status = liveresult.status
                else:
                    liveresult = LiveResult.objects.get(school=school)
                    liveresult.school = school
                    liveresult.term = examtype
                    liveresult.gradelist = checks
                    liveresult.status = livestatus
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
    else:
        liveresult = True
        lr = LiveResult.objects.get(school=school)

        lr_term = SchoolTerm.objects.get(id=lr.term)

        print(lr_term)

        gradelist = json.loads(lr.gradelist)

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
    }
    return render(request, "panel/resultmanagement.html", context)


def resultapi(request):
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


@login_required
def schoolprivate(request, regno):
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
    totalstudent = Student.objects.filter(
        grade=student.grade, section=student.section
    ).count()
    # for calculating rank

    req_rank = calculaterank(
        school=student.school.id,
        session=this_session,
        grade=int(student.grade.id),
        term=term,
        section=student.section,
        regno=student.reg_no,
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
    the_edusession = EduSession.objects.all()
    exam_types = SchoolTerm.objects.filter(
        year=this_session, school=school, active=True
    )
    grades = SchoolGrade.objects.filter(school=school, active=True).order_by("id")

    section_list = {}
    for grade in grades:
        sections = Section.objects.filter(grade=grade)
        new_dict = {}
        for section in sections:
            new_dict[str(section.id)] = section.section

        section_list[str(grade.id)] = new_dict

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

    exam_types = SchoolTerm.objects.filter(school=branchuser.school)

    live_result_status_count = LiveResult.objects.filter(school=school).count()
    if live_result_status_count == 1:
        live_result_status = LiveResult.objects.get(school=school)
        live_result_status = live_result_status.status
    else:
        live_result_status = False

    if request.method == "POST":
        # if request.POST.get('submittype'):

        #     data = request.POST.get('submittype')

        #     if data == 'resulttype':
        #         percent_or_grade = request.POST.get('percentorgrade')

        #         if percent_or_grade == 'percent':
        #             print('percent')
        #             result = 1
        #         elif percent_or_grade == 'grade':
        #             print('grade')
        #             result = 2

        #         if SchoolResultType.objects.filter(school=school, session=this_session).count() > 0:
        #             print('result found')
        #         else:
        #             print('result not found')

        #             schoolresulttype = SchoolResultType()
        #             schoolresulttype.school = school
        #             schoolresulttype.session = this_session
        #             schoolresulttype.resulttype = result
        #             schoolresulttype.save()

        #     elif data == 'termandgrades':
        #         examtype = request.POST.get('examtype')
        #         print(examtype)
        #         # for grade in grades:
        #         #     isit = request.POST.get(grade.id)
        #         #     print(grade.grade_name, isit)

        #         # checks =
        #         publishresultswitch = request.POST.get('publishresultswitch')
        #         if publishresultswitch == 'on':
        #             livestatus = True
        #         else:
        #             livestatus = False
        #         print('publishresultswitch: ', publishresultswitch)
        #         checks = request.POST.getlist('checks[]')
        #         # checks = int(checks)

        #         checks = [int(i) for i in checks]

        #         checks = json.dumps(checks)

        #         if LiveResult.objects.filter(school=school).count() == 0:
        #             liveresult = LiveResult()
        #             liveresult.school = school
        #             liveresult.term = examtype
        #             liveresult.gradelist = checks
        #             liveresult.status = livestatus
        #             liveresult.save()

        #             live_result_status = liveresult.status
        #         else:
        #             liveresult = LiveResult.objects.get(school=school)
        #             liveresult.school = school
        #             liveresult.term = examtype
        #             liveresult.gradelist = checks
        #             liveresult.status = livestatus
        #             liveresult.save()

        #             live_result_status = liveresult.status
        #     # print(request.POST.get('resulttype'))

        # # if request.POST.get('termtype'):
        # #     for key, value in request.POST.items():
        # #         print('Key: %s' % (key) )
        # #         # print(f'Key: {key}') in Python >= 3.7
        # #         print('Value %s' % (value) )
        # #         # print(f'Value: {value}') in Python >= 3.7
        # nab = dict()
        # nab[1] = 'nabin'
        # context = {'nab': nab}

        term = request.POST.get("term")
        submitted_session = request.POST.get("edusession")
        grade = request.POST.get("grade2")
        print("SCHOOL", school, " GRADE: ", grade)
        this_grade = SchoolGrade.objects.get(id=grade)
        this_term = SchoolTerm.objects.get(id=term)

        # print(session.type())

        print("TERM", this_term, " GRADE: ", this_grade)
        # this_session = EduSession.objects.get(id=submitted_session)
        students = Student.objects.filter(school=school, grade=this_grade, status=True)
        subjects = Subject.objects.filter(
            branch=schoolbranch, grade=this_grade, status=True
        )
        additional_td = 13 - subjects.count()
        print("OOOOOOOOOOOOOOOOOOOOOOOOo", "SUBJECT COUNT", subjects.count())

        std_list = {}
        for student in students:
            print(student)
            std_list[student.reg_no] = {}
            std_list[student.reg_no]["name"] = student.name
            std_list[student.reg_no]["grade"] = student.grade
            std_list[student.reg_no]["section"] = student.section

            mo_dict = {}
            count = 1
            for subject in subjects:
                mo_dict[count] = {}
                mo_dict[count]["subject_name"] = subject.subject

                print(subject)
                print(student, this_session, this_grade, this_term, subject)
                try:
                    # this_marks = MarkObtained.objects.get(
                    #     student=int(student.reg_no),
                    #     school=school.id,
                    #     grade=grade.id,
                    #     term=term_exam.id,
                    #     subject=subject.id,
                    #     session=this_session,
                    # )
                    moc = MarkObtained.objects.filter(
                        student=student.reg_no,
                        # school=school.id,
                        # grade=this_grade.id,
                        term=this_term.id,
                        subject=subject.id,
                        session=this_session,
                    ).count()
                    print("MOC: ", moc)

                    this_marks = MarkObtained.objects.get(
                        student=int(student.reg_no),
                        session=this_session,
                        grade=this_grade.id,  # school = school.id,
                        term=this_term.id,
                        subject=subject.id,
                    )

                    gfm = GradeFullMarks.objects.get(
                        grade=this_grade.id, term=this_term.id, subject=subject.id,
                    )
                    the_fm = gfm.th_fm + gfm.pr_fm

                    if gfm.th_fm > 0:
                        if gfm.pr_fm > 0:
                            # Both Theory and Practical Marks are available
                            if this_marks.th_mo > 0:
                                # If Marks obtained is grater than 0
                                percent_th = this_marks.th_mo * 100 / gfm.th_fm
                            else:
                                # If Theory Marks obtained is equal to 0
                                percent_th = 0
                            if this_marks.pr_mo > 0:
                                percent_pr = this_marks.pr_mo * 100 / gfm.th_fm
                            else:
                                percent_pr = 0

                            percent_total = (
                                    (this_marks.th_mo + this_marks.pr_mo) * 100 / the_fm
                            )

                        else:
                            # Only theory Marks are available
                            if this_marks.th_mo > 0:
                                # If Marks obtained is grater than 0
                                percent_th = this_marks.th_mo * 100 / gfm.th_fm
                                percent_total = percent_th
                            else:
                                # If Theory Marks obtained is equal to 0
                                percent_th = 0

                            grade_th = grading(percent_th)
                            grade_pr = grading(percent_pr)
                            # grade_total = grading(percent_total)

                    th_mo = this_marks.th_mo
                    pr_mo = this_marks.pr_mo

                    if count == 1:
                        print("GFM ", gfm)
                        print("THIS MARKS", this_marks)
                except:
                    th_mo = 0
                    pr_mo = 0
                # print('MARKS', this_marks)
                mo_dict[count]["theory_mo"] = grade_th[0]  # this_marks.th_mo
                mo_dict[count]["prac_mo"] = grade_pr[0]  # pr_mo #this_marks.pr_mo

                mo_dict[count]["gradepoint"] = 3.2  # grade_total[1]

                count += 1

            std_list[student.reg_no]["mo_dict"] = mo_dict

        context = {
            "std_list": std_list,
            "school": schoolbranch,
            "slogan": True,
            "term": this_term,
            "additional_td": additional_td,
        }
        # context = {}

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

        print(lr_term)

        gradelist = json.loads(lr.gradelist)

        # gradelist = tuple(gradelist)

        for grade in grades:
            if grade.id in gradelist:
                print(grade)
            # schoolgrade = SchoolGrade.objects.get(id=i)
            # print(i)

    context = {
        "edusession": the_edusession,
        "exam_types": exam_types,
        "section_list": section_list,
        "school": school,
        "grade_level": grade_level,
        "grades": grades,
        "gradelist": gradelist,
        "branchuser": branchuser,
        "exam_types": exam_types,
        "schoolresulttype": schoolresulttype,
        "sr": sr,
        "live_result_status": live_result_status,
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
               'school_branch': school_branch}
    return render(request, "panel/guardians.html", context)


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
               'school_branch': school_branch}
    return render(request, "panel/edit_guardian.html", context)


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


@login_required()
def add_teacher(request):
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

                bu = BranchUser()
                bu.added_by = user
                bu.guardian = obj
                bu.save()
                message = "Teacher Login Account Created Successfully. "
            else:
                message = "Teacher Login Account Already Exists. "
        except Exception as e:
            message = "Sorry something went wrong. Please Contact Hamro Support. REF: " + str(e)
    else:
        print("GET")
    context = {'message': message}
    return render(request, "panel/add_teacher.html", context)


@login_required
def addsection(request):
    if request.method == 'POST':
        gradelevel = request.POST.get('gradelevel')
        redurl = request.POST.get('redurl')
        sectionname = request.POST.get('sectionname')
        print(gradelevel)

        grade = SchoolGrade.objects.get(id=gradelevel)

        Section.objects.get_or_create(grade=grade, section=sectionname.upper(), session=this_session)

        return HttpResponseRedirect(redurl)

    else:
        return HttpResponse('Sorry! Something went wrong. Click <a href="/">Here</a> to go the homepage.')



@login_required
def addsubject(request):
    user = request.user
    if request.method == 'POST':
        gradelevel = request.POST.get('gradelevel')
        redurl = request.POST.get('redurl')
        subject = request.POST.get('subjectname')
        print(gradelevel)

        grade = SchoolGrade.objects.get(id=gradelevel)

        userbranch = BranchUser.objects.get(user=user)

        print(userbranch.school)

        Subject.objects.get_or_create(
            branch=userbranch.school, grade=grade, subject=subject.upper(), session=this_session)

        # Section.objects.get_or_create(grade=grade,section=sectionname.upper())

        return HttpResponseRedirect(redurl)

    else:
        return HttpResponse('Sorry! Something went wrong. Click <a href="/">Here</a> to go the homepage.')


def edsubject(request):
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
def addstudent(request):
    user = request.user
    if request.method == 'POST':
        gradelevel = request.POST.get('gradelevel')
        redurl = request.POST.get('redurl')

        # gradelevel = SchoolGrade.objects.get(id=gradelevel)
        #regno = request.POST.get('regno')
        studentname = request.POST.get('studentname')
        rollno = request.POST.get('rollno', 1)
        gender = request.POST.get('gender')
        section = request.POST.get('section')
        dateofbirth = request.POST.get('dateofbirth', '')

        tempaddr = request.POST.get('tempaddr', '')
        peraddr = request.POST.get('peraddr', '')

        fathersname = request.POST.get('fathersname', '')
        fathersphone = request.POST.get('fathersphone', 0)
        fathersemail = request.POST.get('fathersemail', None)

        mothersname = request.POST.get('mothersname', '')
        mothersphone = request.POST.get('mothersphone', None)
        mothersemail = request.POST.get('mothersemail', None)

        gurdainsname = request.POST.get('guardiansname', '')
        gurdainsphone = request.POST.get('guardiansphone', None)
        gurdainsemail = request.POST.get('guardiansemail', None)

        # print(gradelevel, grade, section)

        grade = SchoolGrade.objects.get(id=gradelevel)
        userbranch = BranchUser.objects.get(user=user)
        section = Section.objects.get(id=section)
        school = userbranch.school

        new_reg_no = findNewRegNo(userbranch.school.id)
        pincode = randint(1000, 9999)

        student = Student()
        student.reg_no = new_reg_no #if regno == '' else regno

        student.pin_code = pincode
        student.roll_no = rollno
        student.name = studentname
        student.gender = gender
        student.dob = dateofbirth #datetime.strptime(dateofbirth, '%y/%m/%d')
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

        student.school = userbranch.school
        print("going to save student")

        student.save()
        if StudentSession.objects.filter(session=this_session, student=student).count() == 0:
            student_session = StudentSession()
            student_session.session = this_session
            student_session.student = student
            student_session.grade = grade
            student_session.section = section
            student_session.roll_no = rollno

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

        # print(new_reg_no)
        # print('ADD STUDENT')
        # print(gradelevel, studentname, gender)#, username, gradelevel, userbranch.school.id, section)
        # print(userbranch.school)

        # BranchUser.objects.filter()

        # Subject.objects.get_or_create(branch=userbranch.school, grade=grade,subject=subject.upper())

        # Section.objects.get_or_create(grade=grade,section=sectionname.upper())

        for key, value in request.POST.items():
            print('Key: %s' % (key))
            # print(f'Key: {key}') in Python >= 3.7
            print('Value %s' % (value))
            # print(f'Value: {value}') in Python >= 3.7

        return HttpResponseRedirect(redurl)

    else:
        return HttpResponse('Sorry! Something went wrong. Click <a href="/">Here</a> to go the homepage.')


@login_required
def add_student_by_reg(request):
    user = request.user
    if request.method == 'POST':
        gradelevel = request.POST.get('gradelevel')
        redurl = request.POST.get('redurl')

        # gradelevel = SchoolGrade.objects.get(id=gradelevel)
        regno = request.POST.get('regno')
        rollno = request.POST.get('rollno', 1)
        section = request.POST.get('section')
        dateofbirth = request.POST.get('dateofbirth', '')

        tempaddr = request.POST.get('tempaddr', '')
        peraddr = request.POST.get('peraddr', '')

        fathersname = request.POST.get('fathersname', '')
        fathersphone = request.POST.get('fathersphone', 0)
        fathersemail = request.POST.get('fathersemail', None)

        mothersname = request.POST.get('mothersname', '')
        mothersphone = request.POST.get('mothersphone', None)
        mothersemail = request.POST.get('mothersemail', None)

        gurdainsname = request.POST.get('guardiansname', '')
        gurdainsphone = request.POST.get('guardiansphone', None)
        gurdainsemail = request.POST.get('guardiansemail', None)

        # print(gradelevel, grade, section)

        grade = SchoolGrade.objects.get(id=gradelevel)
        userbranch = BranchUser.objects.get(user=user)
        section = Section.objects.get(id=section)
        school = userbranch.school

        new_reg_no = findNewRegNo(userbranch.school.id)

        student = Student.objects.get(reg_no= regno)
        # student.reg_no = new_reg_no if regno == '' else regno

        student.roll_no = rollno
        student.dob = dateofbirth #datetime.strptime(dateofbirth, '%y/%m/%d')
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

        student.school = userbranch.school
        print("going to save student")

        student.save()
        #
        # student_session = StudentSession()
        # student_session.session = this_session
        # student_session.student = student
        # student_session.grade = grade
        # student_session.section = section
        # student_session.roll_no = rollno
        #
        # student_session.save()
        if StudentSession.objects.filter(session=this_session, student=student).count() == 0:
            student_session = StudentSession()
            student_session.session = this_session
            student_session.student = student
            student_session.grade = grade
            student_session.section = section
            student_session.roll_no = rollno

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

        # print(new_reg_no)
        # print('ADD STUDENT')
        # print(gradelevel, studentname, gender)#, username, gradelevel, userbranch.school.id, section)
        # print(userbranch.school)

        # BranchUser.objects.filter()

        # Subject.objects.get_or_create(branch=userbranch.school, grade=grade,subject=subject.upper())

        # Section.objects.get_or_create(grade=grade,section=sectionname.upper())

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
        width = 50
        logo = "https://grihakarya.hamro.com/samataeast/images/logo1.jpg"
    else:
        width = 50
        logo = "http://school3.nep.onl/wp-content/uploads/sites/8/2019/12/51150449_1650894705012798_8214025074135531520_n.png"
    branchuser = BranchUser.objects.get(user=user)
    school = SchoolBranch.objects.get(id=branchuser.school.id)

    std_reg = ''

    if request.method == 'POST':
        term = request.POST.get('term')
        whattype = request.POST.get('whattype')
        if whattype == 'True':
            whattype = True
        else:
            whattype = False
            print(term)
        students = Student.objects.filter(
            school=school, status=True)
        std_reg = {}
        for student in students:
            if StudentSession.objects.filter(session=this_session, student=student, status=True).count() == 1:
                std_sesstion = StudentSession.objects.get(session=this_session, student=student, status=True)
                std_reg[student.reg_no] = {}
                std_reg[student.reg_no]['reg_no'] = student.reg_no
                std_reg[student.reg_no]['name'] = student.name
                std_reg[student.reg_no]['grade'] = std_sesstion.grade.grade_name
                std_reg[student.reg_no]['section'] = std_sesstion.section

        count = students.count()
        print(students)
        term_exam = SchoolTerm.objects.get(id=term)

        if whattype:
            context = {
                'school': school,
                'students': students,
                'count': count,
                'term_exam': term_exam,
                'year': this_year,
                'logo': logo,
                'width': width,
                'blankcount': '12345678',
                'std_reg': std_reg,
                'branchuser': branchuser
            }

            return render(request, 'panel/entrancecard_dict.html', context)
        else:
            context = {
                'school': school,
                'term_exam': term_exam,
                'year': this_year,
                'logo': logo,
                'width': width,
                'blankcount': '12345678',
                'std_reg': std_reg,
                'branchuser': branchuser
            }

            return render(request, 'panel/entrancecardblank.html', context)

    exam_types = SchoolTerm.objects.filter(school=branchuser.school)

    grades = SchoolGrade.objects.filter(school=branchuser.school)

    context = {'grades': grades, 'school': school, 'exam_types': exam_types, 'branchuser': branchuser}
    return render(request, 'panel/entrancecardbase.html', context)


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
