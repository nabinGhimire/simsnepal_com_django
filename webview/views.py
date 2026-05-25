from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import json
import traceback
import nepali_datetime
from django.urls import reverse
import logging
from sms.models import (
    EduSession, SchoolBranch, SchoolGrade, Section, Subject,
    Student, StudentSession, Homework, MarkObtained, SchoolTerm,
    TeacherSubjectAccess, BranchUser
)

User = get_user_model()
signer = TimestampSigner()

def get_current_session():
    return EduSession.objects.filter(status=True).first()

@csrf_exempt
def generate_auth_token(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST requests allowed"}, status=405)
        
    api_key = request.headers.get("X-API-Key")
    expected_key = getattr(settings, "WEBVIEW_API_KEY", "")
    if not api_key or api_key != expected_key:
        return JsonResponse({"error": "Unauthorized API Access"}, status=403)
        
    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    phone = data.get("phone")
    hamro_uuid = data.get("hamro_uuid")
    
    response_data = {"exists": False, "roles": []}
    
    if phone:
        try:
            phone_int = int(phone)
            parent_exists = Student.objects.filter(
                Q(fathers_phone=phone_int) |
                Q(mothers_phone=phone_int) |
                Q(guardian_phone=phone_int),
                status=True
            ).exists()
            if parent_exists:
                response_data["exists"] = True
                response_data["roles"].append("parent")
                response_data["parent_token"] = signer.sign_object({"role": "parent", "phone": str(phone)})
        except ValueError:
            pass

    if hamro_uuid:
        from sso.models import HamroUserProfile
        profile = HamroUserProfile.objects.filter(hamro_uuid=hamro_uuid).first()
        user = profile.user if profile else None
        if user and BranchUser.objects.filter(user=user, status=True).exists():
            response_data["exists"] = True
            response_data["roles"].append("teacher")
            response_data["teacher_token"] = signer.sign_object({"role": "teacher", "user_id": user.id})

    return JsonResponse(response_data)


def validate_webview_token(request, expected_role):
    token = request.GET.get("token") or request.POST.get("token")
    if not token:
        return None
        
    try:
        data = signer.unsign_object(token, max_age=86400)
    except (BadSignature, SignatureExpired):
        return None
        
    if data.get("role") != expected_role:
        return None
        
    if expected_role == "parent":
        return data.get("phone")
    elif expected_role == "teacher":
        user_id = data.get("user_id")
        return User.objects.filter(id=user_id).first()
        
    return None


def parent_homework(request):
    phone = validate_webview_token(request, "parent")
    if not phone:
        return render(request, "webview/error.html", {
            "error_title": "Unauthorized Access",
            "error_message": "Invalid or expired token. Please reopen the page from the app."
        })
        
    current_session = get_current_session()
    if not current_session:
        return render(request, "webview/error.html", {
            "error_title": "Configuration Error",
            "error_message": "No active academic session configured."
        })
        
    try:
        phone_int = int(phone)
    except ValueError:
        return render(request, "webview/error.html", {
            "error_title": "Invalid Phone",
            "error_message": "Verified phone format is invalid."
        })
        
    students = Student.objects.filter(
        Q(fathers_phone=phone_int) |
        Q(mothers_phone=phone_int) |
        Q(guardian_phone=phone_int),
        status=True
    ).select_related('school')
    
    if not students.exists():
        return render(request, "webview/error.html", {
            "error_title": "No Enrolled Students",
            "error_message": f"No student profiles are linked to phone number '{phone}'."
        })
        
    selected_date_str = request.GET.get('date')
    if selected_date_str:
        try:
            parts = selected_date_str.split('-')
            selected_date = nepali_datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
        except Exception:
            selected_date = nepali_datetime.date.today()
    else:
        selected_date = nepali_datetime.date.today()
        
    student_homeworks = []
    for student in students:
        ss_qs = StudentSession.objects.filter(
            student=student,
            session=current_session,
            status=True
        ).select_related('grade', 'section')
        
        if not ss_qs.exists():
            continue
            
        ss = ss_qs.first()
        grade = ss.grade
        section = ss.section
        
        try:
            homework_obj = Homework.objects.get(
                session=current_session,
                grade=grade,
                section=section,
                nepali_date=selected_date
            )
            hw_dict = json.loads(homework_obj.homework or "{}")
        except Homework.DoesNotExist:
            hw_dict = {}
            
        subjects = Subject.objects.filter(
            session=current_session,
            grade=grade,
            section=section,
            status=True
        )
        
        hw_list = []
        for sub in subjects:
            content = hw_dict.get(str(sub.id))
            if content:
                hw_list.append({
                    'subject': sub.subject,
                    'content': content
                })
                
        student_homeworks.append({
            'student': student,
            'grade': grade,
            'section': section,
            'homeworks': hw_list
        })
        
    context = {
        'student_homeworks': student_homeworks,
        'selected_date': str(selected_date),
        'parent_phone': phone,
        'token': request.GET.get("token", ""),
    }
    return render(request, "webview/parent_homework.html", context)


def parent_result(request):
    phone = validate_webview_token(request, "parent")
    if not phone:
        return render(request, "webview/error.html", {
            "error_title": "Unauthorized Access",
            "error_message": "Invalid or expired token. Please reopen the page from the app."
        })
        
    current_session = get_current_session()
    if not current_session:
        return render(request, "webview/error.html", {
            "error_title": "Configuration Error",
            "error_message": "No active academic session configured."
        })
        
    try:
        phone_int = int(phone)
    except ValueError:
        return render(request, "webview/error.html", {
            "error_title": "Invalid Phone",
            "error_message": "Verified phone format is invalid."
        })
        
    students = Student.objects.filter(
        Q(fathers_phone=phone_int) |
        Q(mothers_phone=phone_int) |
        Q(guardian_phone=phone_int),
        status=True
    ).select_related('school')
    
    if not students.exists():
        return render(request, "webview/error.html", {
            "error_title": "No Enrolled Students",
            "error_message": f"No student profiles are linked to phone number '{phone}'."
        })
        
    student_results = []
    for student in students:
        ss_qs = StudentSession.objects.filter(
            student=student,
            session=current_session,
            status=True
        ).select_related('grade', 'section')
        
        if not ss_qs.exists():
            continue
            
        ss = ss_qs.first()
        
        marks = MarkObtained.objects.filter(
            student=student,
            session=current_session,
            school=student.school,
            grade=ss.grade
        ).select_related('term', 'subject')
        
        terms_data = {}
        for mark in marks:
            term_name = mark.term.term_name
            if term_name not in terms_data:
                terms_data[term_name] = {
                    'term': mark.term,
                    'marks': []
                }
            terms_data[term_name]['marks'].append(mark)
            
        student_results.append({
            'student': student,
            'grade': ss.grade,
            'section': ss.section,
            'terms': terms_data.values()
        })
        
    context = {
        'student_results': student_results,
        'parent_phone': phone,
    }
    return render(request, "webview/parent_result.html", context)


@csrf_exempt
def teacher_homework(request):
    """Render teacher homework webview with robust error handling.

    Any unexpected exception is logged with a full traceback and a generic
    error page is displayed to the user.
    """
    try:
        user = validate_webview_token(request, "teacher")
        token = request.GET.get('token') or request.POST.get('token')
        if not user:
            return render(request, "webview/error.html", {
                "error_title": "Unauthorized Access",
                "error_message": "Invalid or expired token. Please reopen the page from the app."
            })

        current_session = get_current_session()
        if not current_session:
            return render(request, "webview/error.html", {"error_title": "Configuration Error", "error_message": "No active academic session configured."})

        branch_users = BranchUser.objects.filter(user=user, status=True)
        if not branch_users.exists():
            return render(request, "webview/error.html", {"error_title": "Access Denied", "error_message": "Your user profile is not associated with any school branch."})

        is_admin = branch_users.filter(admin_status=True).exists() or user.is_superuser

        # Identify available schools
        if is_admin:
            if user.is_superuser:
                available_schools = list(SchoolBranch.objects.filter(status=True))
            else:
                available_schools = [bu.school for bu in branch_users if bu.admin_status]
        else:
            ts_access = TeacherSubjectAccess.objects.filter(teacher=user, session=current_session, status=True).select_related('grade__school')
            available_schools = list(set([t.grade.school for t in ts_access]))

        if not available_schools:
            return render(request, "webview/error.html", {"error_title": "No Classes", "error_message": "You have no assigned subjects."})

        school_id = request.GET.get('school_id') or request.POST.get('school_id')

        # Force school selection if > 1 school and none selected
        if len(available_schools) > 1 and not school_id:
            return render(request, "webview/teacher_select_school.html", {
                "schools": available_schools,
                "token": token,
                "next_url": request.path,
            })

        if school_id:
            try:
                selected_school = SchoolBranch.objects.get(id=school_id)
            except SchoolBranch.DoesNotExist:
                selected_school = available_schools[0]
        else:
            selected_school = available_schools[0]

        selected_date_str = request.GET.get('date') or request.POST.get('date')
        if selected_date_str:
            try:
                parts = selected_date_str.split('-')
                selected_date = nepali_datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
            except Exception:
                selected_date = nepali_datetime.date.today()
        else:
            selected_date = nepali_datetime.date.today()

        message = ""

        # Filter subjects by selected school
        if is_admin:
            access_subjects = Subject.objects.filter(
                session=current_session,
                branch=selected_school,
                status=True
            ).select_related('grade', 'section', 'branch')
        else:
            ts_access = TeacherSubjectAccess.objects.filter(
                teacher=user,
                session=current_session,
                grade__school=selected_school,
                status=True
            ).select_related('grade', 'section', 'subject', 'grade__school')
            access_subjects = [t.subject for t in ts_access]

        # Process Bulk POST
        if request.method == "POST":
            updates_by_class = {}
            for subject in access_subjects:
                input_name = f"hw_{subject.grade_id}_{subject.section_id}_{subject.id}"
                hw_text = request.POST.get(input_name)
                if hw_text is not None:
                    class_key = (subject.grade_id, subject.section_id)
                    if class_key not in updates_by_class:
                        updates_by_class[class_key] = {}
                    updates_by_class[class_key][str(subject.id)] = hw_text.strip()

            for (g_id, s_id), subjects_data in updates_by_class.items():
                homework_obj, created = Homework.objects.get_or_create(
                    session=current_session, grade_id=g_id, section_id=s_id, nepali_date=selected_date,
                    defaults={"homework": "{}"}
                )
                try:
                    hw_dict = json.loads(homework_obj.homework or "{}")
                except Exception:
                    hw_dict = {}
                for sub_id_str, text in subjects_data.items():
                    if text:
                        hw_dict[sub_id_str] = text
                    else:
                        hw_dict.pop(sub_id_str, None)
                homework_obj.homework = json.dumps(hw_dict)
                homework_obj.save()
            message = "All homework entries saved successfully!"

        grade_section_pairs = set((sub.grade, sub.section) for sub in access_subjects)
        existing_homework = {}
        for grade, section in grade_section_pairs:
            try:
                hw_obj = Homework.objects.get(session=current_session, grade=grade, section=section, nepali_date=selected_date)
                existing_homework[(grade.id, section.id)] = json.loads(hw_obj.homework or "{}")
            except Homework.DoesNotExist:
                existing_homework[(grade.id, section.id)] = {}

        grouped_ui = {}
        for subject in access_subjects:
            school_name = subject.grade.school.name
            class_name = f"Grade {subject.grade.grade_name} - Section {subject.section.section}"
            if school_name not in grouped_ui:
                grouped_ui[school_name] = {}
            if class_name not in grouped_ui[school_name]:
                grouped_ui[school_name][class_name] = []
            hw_dict = existing_homework.get((subject.grade_id, subject.section_id), {})
            grouped_ui[school_name][class_name].append({
                'subject': subject,
                'input_name': f"hw_{subject.grade_id}_{subject.section_id}_{subject.id}",
                'value': hw_dict.get(str(subject.id), "")
            })

        context = {
            'is_admin': is_admin,
            'selected_school': selected_school,
            'grouped_ui': grouped_ui,
            'selected_date': str(selected_date),
            'message': message,
            'token': token,
        }
        return render(request, "webview/teacher_homework.html", context)
    except Exception as exc:
        logger = logging.getLogger(__name__)
        logger.error("Unexpected error in teacher_homework view: %s\nTraceback:\n%s", exc, traceback.format_exc())
        return render(request, "webview/error.html", {
            "error_title": "Server Error",
            "error_message": "An unexpected error occurred while loading the page. Please contact support."
        })


def teacher_marks(request):
    user = validate_webview_token(request, "teacher")
    token = request.GET.get('token')
    if not user:
        return render(request, "webview/error.html", {"error_title": "Unauthorized Access", "error_message": "Invalid token."})
        
    current_session = get_current_session()
    if not current_session:
        return render(request, "webview/error.html", {"error_title": "Configuration Error", "error_message": "No active academic session."})
        
    branch_users = BranchUser.objects.filter(user=user, status=True)
    is_admin = branch_users.filter(admin_status=True).exists() or user.is_superuser
    
    if is_admin:
        if user.is_superuser:
            available_schools = list(SchoolBranch.objects.filter(status=True))
        else:
            available_schools = [bu.school for bu in branch_users if bu.admin_status]
    else:
        ts_access = TeacherSubjectAccess.objects.filter(teacher=user, session=current_session, status=True).select_related('grade__school')
        available_schools = list(set([t.grade.school for t in ts_access]))
        
    if not available_schools:
        return render(request, "webview/error.html", {"error_title": "No Classes", "error_message": "You have no assigned subjects."})
        
    school_id = request.GET.get('school_id')
    term_id = request.GET.get('term_id')
    grade_id = request.GET.get('grade_id')
    section_id = request.GET.get('section_id')
    subject_id = request.GET.get('subject_id')
    
    # 1. School Selection
    if len(available_schools) > 1 and not school_id:
        return render(request, "webview/teacher_select_school.html", {
            "schools": available_schools, "token": token, "next_url": request.path
        })
        
    if school_id:
        selected_school = SchoolBranch.objects.filter(id=school_id).first()
    else:
        selected_school = available_schools[0]
        
    # 2. Term Selection
    terms = SchoolTerm.objects.filter(school=selected_school, year=current_session, active=True)
    if not term_id:
        return render(request, "webview/teacher_select_step.html", {
            "step": "term", "items": terms, "school": selected_school, "token": token
        })
        
    # 3. Grade & Section Selection
    if is_admin:
        access_subjects = Subject.objects.filter(session=current_session, branch=selected_school, status=True).select_related('grade', 'section')
    else:
        ts_access = TeacherSubjectAccess.objects.filter(teacher=user, session=current_session, grade__school=selected_school, status=True).select_related('grade', 'section', 'subject')
        access_subjects = [t.subject for t in ts_access]
        
    unique_classes = set((sub.grade, sub.section) for sub in access_subjects)
    
    if not grade_id or not section_id:
        classes_data = [{'grade': g, 'section': s} for g, s in unique_classes]
        return render(request, "webview/teacher_select_step.html", {
            "step": "class", "items": classes_data, "term_id": term_id, "school": selected_school, "token": token
        })
        
    # 4. Subject Routing
    subjects_in_class = [sub for sub in access_subjects if str(sub.grade_id) == str(grade_id) and str(sub.section_id) == str(section_id)]
    
    if len(subjects_in_class) == 1 or subject_id:
        final_subject_id = subject_id if subject_id else subjects_in_class[0].id
        # Route directly to the admin marks entry
        redirect_url = f"{reverse('subject_wise_marks_entry')}?term={term_id}&grade={grade_id}&section={section_id}&subject={final_subject_id}"
        return redirect(redirect_url)
    else:
        return render(request, "webview/teacher_select_step.html", {
            "step": "subject", "items": subjects_in_class, "term_id": term_id, 
            "grade_id": grade_id, "section_id": section_id, "school": selected_school, "token": token
        })
