from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
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
from types import SimpleNamespace
from sms.models import EduSession, SchoolBranch, SchoolGrade, Section, Subject, Student, StudentSession, Homework, MarkObtained, SchoolTerm, TeacherSubjectAccess, BranchUser, LiveResult
from grihakarya.models import HomeworkEntry, HomeworkEntryAuditLog


User = get_user_model()
signer = TimestampSigner(key=settings.SIMS_WEBVIEW_SIGNER_KEY, salt='')


def get_current_session():
    return EduSession.objects.filter(status=True).first()

def normalize_nepali_phone(phone_str):
    if not phone_str:
        return ""
    phone = str(phone_str).strip()
    if phone.startswith('+'):
        phone = phone[1:]
    if phone.startswith('00'):
        phone = phone[2:]
    if phone.startswith('977') and len(phone) > 10:
        phone = phone[3:]
    return phone


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
    username = data.get("username")
    
    # response_data = {"exists": False, "roles": []}
    response_data = {"exists": False, "roles": [], "phone": phone, "hamro_uuid": hamro_uuid, "username": username}
    
    if phone:
        try:
            normalized_phone = normalize_nepali_phone(phone)
            phone_int = int(normalized_phone)
            parent_exists = Student.objects.filter(
                Q(fathers_phone=phone_int) |
                Q(mothers_phone=phone_int) |
                Q(guardian_phone=phone_int),
                status=True
            ).exists()
            if parent_exists:
                response_data["exists"] = True
                response_data["roles"].append("parent")
                response_data["parent_token"] = signer.sign_object({"role": "parent", "phone": str(normalized_phone)})
        except ValueError:
            pass

    # Try to find user via hamro_uuid first
    if hamro_uuid:
        from sso.models import HamroUserProfile
        profile = HamroUserProfile.objects.filter(hamro_uuid=hamro_uuid).first()
        user = profile.user if profile else None

    # If no hamro_uuid, try lookup by phone
    if not user and phone:
        from sso.models import HamroUserProfile
        normalized_phone = normalize_nepali_phone(phone)
        try:
            phone_int = int(normalized_phone)
            profile = HamroUserProfile.objects.filter(mobile_number=phone_int).first()
            user = profile.user if profile else None
        except ValueError:
            user = None

    # If no user yet, try lookup by username
    if not user and username:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None

    # If user found and has BranchUser record, generate teacher token
    if user:
        response_data["exists"] = True
        response_data["roles"].append("teacher")
        # Generate a token for teacher access (required by webview apps)
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


def teacher_attendance(request):
    """Render teacher attendance webview with robust error handling."""
    try:
        token = request.GET.get('token') or request.POST.get('token')
        user = validate_webview_token(request, "teacher")
        if not user:
            return render(request, "webview/error.html", {
                "error_title": "Unauthorized Access",
                "error_message": "Invalid or expired token. Please reopen the page from the app."
            })

        # Get current academic session
        current_session = get_current_session()
        if not current_session:
            return render(request, "webview/error.html", {
                "error_title": "Configuration Error",
                "error_message": "No active academic session configured."
            })

        # Determine admin status based on branch admin flag or superuser
        from sms.models import BranchUser
        branch_users = BranchUser.objects.filter(user=user, status=True)
        is_admin = branch_users.filter(admin_status=True).exists() or user.is_superuser

        # Identify available schools
        if is_admin:
            if user.is_superuser:
                available_schools = list(SchoolBranch.objects.filter(status=True))
            else:
                available_schools = [bu.school for bu in branch_users if bu.admin_status]
        else:
            # Teacher-specific schools from TeacherSubjectAccess
            ts_access = TeacherSubjectAccess.objects.filter(
                teacher=user, session=current_session, status=True
            ).select_related('grade__school', 'grade__level', 'section', 'subject')
            if not ts_access.exists():
                return render(request, "webview/error.html", {
                    "error_title": "No Subjects Assigned",
                    "error_message": "You have no subjects or classes assigned. Please contact the administrator."
                })
            schools_from_access = list(set(
                t.grade.school for t in ts_access if t.grade and t.grade.school
            ))
            if branch_users:
                available_schools = list(set(schools_from_access + [bu.school for bu in branch_users]))
            else:
                available_schools = schools_from_access

        if not available_schools:
            return render(request, "webview/error.html", {"error_title": "No Classes", "error_message": "You have no assigned subjects."})

        # School selection
        school_id = request.GET.get('school_id') or request.POST.get('school_id')
        if len(available_schools) > 1 and not school_id:
            return render(request, "webview/teacher_select_school.html", {
                "schools": available_schools,
                "token": token,
                "next_url": request.path,
            })

        if school_id:
            try:
                selected_school = SchoolBranch.objects.get(id=school_id)
            except SchoolBridge.DoesNotExist:
                selected_school = available_schools[0]
        else:
            selected_school = available_schools[0]

        # Date selection
        selected_date_str = request.GET.get('date')
        if selected_date_str:
            try:
                parts = selected_date_str.split('-')
                selected_date = nepali_datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
            except Exception:
                selected_date = nepali_datetime.date.today()
        else:
            selected_date = nepali_datetime.date.today()

        # Get teacher's students by class
        ts_access = TeacherSubjectAccess.objects.filter(
            teacher=user, session=current_session, status=True
        ).select_related('grade__school', 'grade__level', 'section', 'subject')

        students_by_class = {}
        for entry in ts_access:
            key = (entry.grade_id, entry.section_id)
            if key not in students_by_class:
                students_by_class[key] = StudentSession.objects.filter(
                    grade_id=entry.grade_id,
                    section_id=entry.section_id,
                    session=current_session,
                    status=True
                ).select_related('student', 'grade', 'section').order_by('roll_no', 'student__name')

        # Build class->subjects->students mapping
        grouped_ui = {}
        for entry in ts_access:
            key = (entry.grade_id, entry.section_id)
            school_name = entry.grade.school.name
            class_name = f"Grade {entry.grade.grade_name} - Section {entry.section.section}"

            if key not in grouped_ui:
                grouped_ui[school_name] = {}

            if class_name not in grouped_ui[school_name]:
                grouped_ui[school_name][class_name] = []

            students = students_by_class.get(key, [])

            grouped_ui[school_name][class_name].append({
                'subject': entry.subject,
                'grade_id': entry.grade_id,
                'section_id': entry.section_id,
                'students': students,
                'entry': entry,
            })

        # POST: Save attendance
        if request.method == "POST":
            action = request.POST.get("action")
            date = request.POST.get("date")

            if action == "save_attendance":
                saved = 0
                for (g_id, s_id), ss_list in students_by_class.items():
                    for ss in ss_list:
                        reg_no = ss.student.reg_no
                        status_val = request.POST.get(f"attendance_{reg_no}")
                        is_present = status_val == "present"
                        informed = request.POST.get(f"informed_{reg_no}") == "yes"
                        remarks = request.POST.get(f"remarks_{reg_no}", "")

                        from attendance.models import DailyAttendance, AttendanceAuditLog
                        from django.utils import timezone

                        existing = DailyAttendance.objects.filter(
                            reg_no=ss.student,
                            date=selected_date,
                            session=current_session,
                            grade_id=g_id,
                            section_id=s_id,
                        ).first()

                        rec, created = DailyAttendance.objects.update_or_create(
                            reg_no=ss.student,
                            date=selected_date,
                            session=current_session,
                            grade_id=g_id,
                            section_id=s_id,
                            defaults={
                                'is_present': is_present,
                                'absent_informed': informed,
                                'remarks': remarks,
                                'taken_by': user,
                                'school': selected_school,
                            }
                        )

                        if not created and existing:
                            if existing.is_present != is_present or existing.remarks != remarks or existing.absent_informed != informed:
                                AttendanceAuditLog.objects.create(
                                    attendance=rec,
                                    updated_by=user,
                                    previous_status=existing.is_present,
                                    new_status=is_present,
                                    previous_remarks=existing.remarks,
                                    new_remarks=remarks
                                )
                        saved += 1

                if saved > 0:
                    message = f"Attendance for {saved} students saved successfully ({saved} changes logged in Audit Trail)."
                else:
                    message = "Attendance saved successfully."

                return render(request, "webview/teacher_attendance.html", {
                    'is_admin': is_admin,
                    'selected_school': selected_school,
                    'selected_date': selected_date,
                    'message': message,
                    'token': token,
                })
            elif action == "cancel":
                return redirect(request.path)

        # GET: render form with grouped UI data
        context = {
            'is_admin': is_admin,
            'selected_school': selected_school,
            'selected_date': selected_date,
            'token': token,
            'grouped_ui': grouped_ui,
            'message': "",
        }
        return render(request, "webview/teacher_attendance.html", context)

    except Exception as exc:
        logger = logging.getLogger(__name__)
        logger.error("Unexpected error in teacher_attendance: %s\n%s", exc, traceback.format_exc())
        return render(request, "webview/error.html", {
            "error_title": "Server Error",
            "error_message": "An unexpected error occurred while loading the page. Please contact support."
        })
    return render(request, "webview/error.html", {"error_title": "No Content", "error_message": "Unable to load teacher attendance. Please ensure you are assigned to a school and subjects."})


def teacher_concerns(request):
    """Teacher adds remarks per student - admin marks concerns from panel."""
    try:
        token = request.GET.get('token') or request.POST.get('token')
        user = validate_webview_token(request, "teacher")
        if not user:
            return render(request, "webview/error.html", {
                "error_title": "Unauthorized Access",
                "error_message": "Invalid or expired token. Please reopen the page from the app."
            })

        # Get current academic session
        current_session = get_current_session()
        if not current_session:
            return render(request, "webview/error.html", {
                "error_title": "Configuration Error",
                "error_message": "No active academic session configured."
            })

        # Determine admin status
        from sms.models import BranchUser
        branch_users = BranchUser.objects.filter(user=user, status=True)
        is_admin = branch_users.filter(admin_status=True).exists() or user.is_superuser

        # Identify available schools
        if is_admin:
            if user.is_superuser:
                available_schools = list(SchoolBranch.objects.filter(status=True))
            else:
                available_schools = [bu.school for bu in branch_users if bu.admin_status]
        else:
            # Teacher-specific schools
            ts_access = TeacherSubjectAccess.objects.filter(
                teacher=user, session=current_session, status=True
            ).select_related('grade__school', 'grade__level', 'section', 'subject', 'teacher')
            if not ts_access.exists():
                return render(request, "webview/error.html", {
                    "error_title": "No Subjects Assigned",
                    "error_message": "You have no subjects or classes assigned. Please contact the administrator."
                })
            schools_from_access = list(set(
                t.grade.school for t in ts_access if t.grade and t.grade.school
            ))
            if branch_users:
                available_schools = list(set(schools_from_access + [bu.school for bu in branch_users]))
            else:
                available_schools = schools_from_access

        if not available_schools:
            return render(request, "webview/error.html", {"error_title": "No Classes", "error_message": "You have no assigned subjects."})

        # School selection
        school_id = request.GET.get('school_id') or request.POST.get('school_id')
        if len(available_schools) > 1 and not school_id:
            return render(request, "webview/teacher_select_school.html", {
                "schools": available_schools,
                "token": token,
                "next_url": request.path,
            })

        if school_id:
            try:
                selected_school = SchoolBranch.objects.get(id=school_id)
            except SchoolBridge.DoesNotExist:
                selected_school = available_schools[0]
        else:
            selected_school = available_schools[0]

        # Date selection
        selected_date_str = request.GET.get('date')
        if selected_date_str:
            try:
                parts = selected_date_str.split('-')
                selected_date = nepali_datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
            except Exception:
                selected_date = nepali_datetime.date.today()
        else:
            selected_date = nepali_datetime.date.today()

        # Get teacher's students by class
        ts_access = TeacherSubjectAccess.objects.filter(
            teacher=user, session=current_session, status=True
        ).select_related('grade__school', 'grade__level', 'section', 'subject', 'teacher')

        students_by_class = {}
        for entry in ts_access:
            key = (entry.grade_id, entry.section_id)
            if key not in students_by_class:
                students_by_class[key] = StudentSession.objects.filter(
                    grade_id=entry.grade_id,
                    section_id=entry.section_id,
                    session=current_session,
                    status=True
                ).select_related('student', 'grade', 'section').order_by('roll_no', 'student__name')

        # Build class data
        class_data = {}
        for entry in ts_access:
            key = (entry.grade_id, entry.section_id)
            school_name = entry.grade.school.name
            class_name = f"Grade {entry.grade.grade_name} - Section {entry.section.section}"

            if key not in class_data:
                class_data[school_name] = {}

            if class_name not in class_data[school_name]:
                class_data[school_name][class_name] = {
                    'subject': entry.subject,
                    'grade_id': entry.grade_id,
                    'section_id': entry.section_id,
                    'students': students_by_class.get(key, []),
                }

        # Handle POST
        if request.method == "POST":
            action = request.POST.get("action")
            date = request.POST.get("date")

            if action == "save_remarks":
                saved = 0
                for school_name, classes in class_data.items():
                    for class_name, data in classes.items():
                        for ss in data['students']:
                            reg_no = ss.student.reg_no
                            remarks = request.POST.get(f"remarks_{reg_no}", "")

                            from attendance.models import DailyAttendance
                            from django.utils import timezone

                            existing = DailyAttendance.objects.filter(
                                reg_no=ss.student,
                                date=selected_date,
                                session=current_session,
                            ).first()

                            if existing:
                                existing.remarks = remarks
                                existing.save(update_fields=['remarks'])
                            else:
                                DailyAttendance.objects.create(
                                    reg_no=ss.student,
                                    date=selected_date,
                                    session=current_session,
                                    remarks=remarks,
                                    taken_by=user,
                                    school=selected_school,
                                )
                            saved += 1

                if saved > 0:
                    message = f"Remarks for {saved} students saved successfully."
                else:
                    message = "Remarks saved successfully."

                return render(request, "webview/teacher_concerns.html", {
                    'is_admin': is_admin,
                    'selected_school': selected_school,
                    'selected_date': selected_date,
                    'message': message,
                    'token': token,
                    'class_data': class_data,
                })

            elif action == "cancel":
                return redirect(request.path)

        # GET: render form
        context = {
            'is_admin': is_admin,
            'selected_school': selected_school,
            'selected_date': selected_date,
            'token': token,
            'class_data': class_data,
            'message': "",
        }
        return render(request, "webview/teacher_concerns.html", context)

    except Exception as exc:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error("Unexpected error in teacher_concerns: %s\n%s", exc, traceback.format_exc())
        return render(request, "webview/error.html", {
            "error_title": "Server Error",
            "error_message": "An unexpected error occurred while loading the page. Please contact support."
        })
    return render(request, "webview/error.html", {"error_title": "No Content", "error_message": "Unable to load teacher concerns. Please ensure you are assigned to a school and students."})