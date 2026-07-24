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
from sms.models import EduSession, SchoolBranch, SchoolGrade, Section, Subject, Student, StudentSession, Homework, MarkObtained, SchoolTerm, TeacherSubjectAccess, BranchUser


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

    if hamro_uuid:
        from sso.models import HamroUserProfile
        profile = HamroUserProfile.objects.filter(hamro_uuid=hamro_uuid).first()
        user = profile.user if profile else None
        if user and BranchUser.objects.filter(user=user, status=True).exists():
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


def parent_homework(request):
    phone = validate_webview_token(request, "parent")
    if not phone:
        return render(request, "webview/error.html", {
            "error_title": "Unauthorized Access",
            "error_message": "Invalid or expired token. Please reopen the page from the app."
        })
        
    current_session = get_current_session()
    logger = logging.getLogger(__name__)
    logger.info("parent_homework called: phone=%s, current_session=%s (id=%s)", phone, current_session, current_session.id if current_session else None)
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
        logger.warning("No enrolled students found for phone: %s", phone)
        return render(request, "webview/error.html", {
            "error_title": "No Enrolled Students",
            "error_message": f"No student profiles are linked to phone number '{phone}'."
        })
        
    selected_date_str = request.GET.get('date')
    if selected_date_str:
        try:
            parts = selected_date_str.split('-')
            selected_date = nepali_datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
            logger.info("parent_homework: token=%s, validated phone=%s, selected_date=%s", request.GET.get('token'), phone, selected_date)
        except Exception:
            selected_date = nepali_datetime.date.today()
            logger.warning("Failed to parse date '%s', using today: %s", selected_date_str, selected_date)
    else:
        selected_date = nepali_datetime.date.today()
        logger.info("No date provided, using today: %s", selected_date)
        
    student_homeworks = []
    for student in students:
        ss_qs = StudentSession.objects.filter(
            student=student,
            session=current_session,
            status=True
        ).select_related('grade', 'section')
        
        if not ss_qs.exists():
            logger.warning("No active StudentSession for student %s (id=%s) in session %s", student.name, student.id, current_session.id if current_session else None)
            continue
            
        ss = ss_qs.first()
        grade = ss.grade
        section = ss.section
        logger.debug("Student %s session found: grade=%s (id=%s), section=%s (id=%s)", student.name, grade, grade.id if grade else None, section, section.id if section else None)
        
        try:
            homework_qs = Homework.objects.filter(
                session=current_session,
                grade=grade,
                section=section,
                nepali_date=selected_date,
            )
            logger.debug(
                "Primary Query: session=%s, grade=%s, section=%s, nepali_date=%s, count=%d",
                current_session.id, grade.id if grade else None, section.id if section else None, selected_date, homework_qs.count(),
            )
            greg_date_val = None
            if not homework_qs.exists():
                if hasattr(selected_date, "to_datetime_date"):
                    greg_date = selected_date.to_datetime_date()
                elif hasattr(selected_date, "to_date"):
                    greg_date = selected_date.to_date()
                else:
                    greg_date = selected_date

                # Format as ISO date string to be completely safe with Django's DateField
                if hasattr(greg_date, "strftime"):
                    greg_date_val = greg_date.strftime("%Y-%m-%d")
                else:
                    greg_date_val = greg_date

                homework_qs = Homework.objects.filter(
                    session=current_session,
                    grade=grade,
                    section=section,
                    date=greg_date_val,
                )
                logger.debug(
                    "Fallback Query: session=%s, grade=%s, section=%s, date=%s, count=%d",
                    current_session.id, grade.id if grade else None, section.id if section else None, greg_date_val, homework_qs.count(),
                )
            if homework_qs.exists():
                homework_obj = homework_qs.first()
                hw_dict = json.loads(homework_obj.homework or "{}")
                logger.debug("Homework object found ID=%s, raw homework=%s, parsed hw_dict=%s", homework_obj.id, homework_obj.homework, hw_dict)
            else:
                hw_dict = {}
                logger.debug("No homework record found for student %s on date %s (greg_date_val=%s)", student.name, selected_date, greg_date_val)
        except Exception as e:
            hw_dict = {}
            logger.error("Exception querying/loading homework for student %s: %s\n%s", student.name, str(e), traceback.format_exc())
            
        subjects = Subject.objects.filter(
            Q(section=section) | Q(section__isnull=True),
            session=current_session,
            grade=grade,
            status=True
        )
        logger.debug("Subjects found count=%d: %s", subjects.count(), [(s.id, s.subject) for s in subjects])
        
        hw_list = []
        for sub in subjects:
            content_data = hw_dict.get(str(sub.id))
            if not content_data:
                continue

            if isinstance(content_data, str):
                # Legacy string format (no teacher info)
                hw_list.append({
                    'subject': sub.subject,
                    'entries': [{'teacher_name': None, 'text': content_data}]
                })
            elif isinstance(content_data, dict):
                # New nested dictionary format
                entries = []
                for t_id, t_data in content_data.items():
                    if isinstance(t_data, dict) and t_data.get("text"):
                        entries.append({
                            'teacher_name': t_data.get("teacher_name"),
                            'text': t_data.get("text")
                        })
                if entries:
                    hw_list.append({
                        'subject': sub.subject,
                        'entries': entries
                    })
                
        student_homeworks.append({
            'student': student,
            'grade': grade,
            'section': section,
            'homeworks': hw_list
        })
        
        logger.debug("Total student_homeworks entries built: %d", len(student_homeworks))
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
        
    token = request.GET.get("token") or request.POST.get("token")
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
        
        # Get distinct terms for this student (from marks entered)
        term_ids = MarkObtained.objects.filter(
            student=student,
            session=current_session,
            school=student.school,
            grade=ss.grade
        ).values_list('term_id', flat=True).distinct()
        
        terms = SchoolTerm.objects.filter(id__in=term_ids).select_related('status')
        
        terms_list = []
        for term in terms:
            terms_list.append({
                'term': term,
                'is_published': term.status_id == 3,
                'detail_url': f"/webview/parent/result/detail/?token={token}&student={student.reg_no}&term={term.id}"
            })
        
        student_results.append({
            'student': student,
            'grade': ss.grade,
            'section': ss.section,
            'roll_no': ss.roll_no,
            'terms': terms_list,
        })
        
    context = {
        'student_results': student_results,
        'parent_phone': phone,
    }
    return render(request, "webview/parent_result.html", context)


def parent_result_detail(request):
    from panel.func import get_percentage, get_grade_point
    from sms.models import GradeFullMarks, Attendance, Rank, SchoolTerminology

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

    student_reg = request.GET.get("student")
    term_id = request.GET.get("term")

    if not student_reg or not term_id:
        return render(request, "webview/error.html", {
            "error_title": "Missing Parameters",
            "error_message": "Student and term parameters are required."
        })

    try:
        phone_int = int(phone)
    except ValueError:
        return render(request, "webview/error.html", {
            "error_title": "Invalid Phone",
            "error_message": "Verified phone format is invalid."
        })

    # Verify student belongs to this parent
    try:
        student = Student.objects.select_related('school').get(
            reg_no=student_reg,
            status=True
        )
    except Student.DoesNotExist:
        return render(request, "webview/error.html", {
            "error_title": "Student Not Found",
            "error_message": "The requested student was not found."
        })

    if not (student.fathers_phone == phone_int or
            student.mothers_phone == phone_int or
            student.guardian_phone == phone_int):
        return render(request, "webview/error.html", {
            "error_title": "Unauthorized",
            "error_message": "You are not authorized to view this student's results."
        })

    # Verify term exists and result is published
    try:
        term = SchoolTerm.objects.select_related('status').get(id=term_id)
    except SchoolTerm.DoesNotExist:
        return render(request, "webview/error.html", {
            "error_title": "Term Not Found",
            "error_message": "The requested term was not found."
        })

    if term.status_id != 3:
        return render(request, "webview/error.html", {
            "error_title": "Results Not Published",
            "error_message": "Results for this term are not yet published."
        })

    # Get student session info
    ss = StudentSession.objects.filter(
        student=student, session=current_session, status=True
    ).select_related('grade', 'section').first()

    if not ss:
        return render(request, "webview/error.html", {
            "error_title": "Enrollment Not Found",
            "error_message": "Student is not enrolled in the current session."
        })

    # Get marks obtained
    marks = MarkObtained.objects.filter(
        student=student,
        session=current_session,
        school=student.school,
        grade=ss.grade,
        term=term
    ).select_related('subject')

    # Get full marks configuration
    full_marks_qs = GradeFullMarks.objects.filter(
        session=current_session,
        school=student.school,
        grade=ss.grade,
        term=term
    )
    full_marks_map = {fm.subject_id: fm for fm in full_marks_qs}

    # Build result rows with GP calculation
    result_rows = []
    grand_total_mo = 0
    grand_total_fm = 0
    total_gp_points = 0
    subject_count = 0
    has_ng = False

    for mark in marks:
        fm = full_marks_map.get(mark.subject_id)
        th_fm = fm.th_fm if fm else 0
        pr_fm = fm.pr_fm if fm else 0
        th_pm = fm.th_pm if fm else 0
        pr_pm = fm.pr_pm if fm else 0
        total_fm = th_fm + pr_fm

        if mark.is_absent:
            row = {
                'subject': mark.subject.subject,
                'th_fm': th_fm, 'pr_fm': pr_fm,
                'th_mo': '-', 'pr_mo': '-',
                'total_mo': 0, 'total_fm': total_fm,
                'th_grade': '-', 'pr_grade': '-',
                'final_grade': 'Abs', 'final_gp': 0,
                'is_absent': True, 'failed': True,
            }
            has_ng = True
        else:
            total_mo = mark.th_mo + mark.pr_mo

            # Calculate GP per subject using existing logic
            th_grade_letter, th_symbol, th_point = '', '', 0
            pr_grade_letter, pr_symbol, pr_point = '', '', 0
            th_failed = False
            pr_failed = False

            if th_fm > 0:
                th_percent = get_percentage(mark.th_mo, th_fm)
                th_grade_letter, th_symbol, th_point = get_grade_point(th_percent)
                if th_pm > 0 and mark.th_mo < th_pm:
                    th_failed = True

            if pr_fm > 0:
                pr_percent = get_percentage(mark.pr_mo, pr_fm)
                pr_grade_letter, pr_symbol, pr_point = get_grade_point(pr_percent)
                if pr_pm > 0 and mark.pr_mo < pr_pm:
                    pr_failed = True

            subject_failed = th_failed or pr_failed

            # Final grade from total percentage
            if total_fm > 0:
                total_percent = get_percentage(total_mo, total_fm)
                final_grade_letter, final_symbol, final_point = get_grade_point(total_percent)
            else:
                final_grade_letter, final_symbol, final_point = 'NG', ' ', 0

            if subject_failed:
                final_grade_display = 'NG'
                final_point = 0
                has_ng = True
            else:
                final_grade_display = f"{final_grade_letter}{final_symbol}".strip()

            row = {
                'subject': mark.subject.subject,
                'th_fm': th_fm, 'pr_fm': pr_fm,
                'th_mo': mark.th_mo, 'pr_mo': mark.pr_mo,
                'total_mo': total_mo, 'total_fm': total_fm,
                'th_grade': f"{th_grade_letter}{th_symbol}".strip() if th_fm > 0 else '-',
                'pr_grade': f"{pr_grade_letter}{pr_symbol}".strip() if pr_fm > 0 else '-',
                'final_grade': final_grade_display,
                'final_gp': final_point,
                'is_absent': False,
                'failed': subject_failed,
            }

            grand_total_mo += total_mo
            grand_total_fm += total_fm
            total_gp_points += final_point
            subject_count += 1

        result_rows.append(row)

    # Calculate GPA
    gpa = round(total_gp_points / subject_count, 2) if subject_count > 0 else 0

    # Get GPA grade using existing gpFromGPA logic
    from panel.func import gpFromGPA
    gpa_grade = gpFromGPA(gpa) if subject_count > 0 else 'N/A'

    # Get attendance if available
    attendance = None
    try:
        attendance = Attendance.objects.get(
            reg_no=student, grade=ss.grade,
            session=current_session, term=term
        )
    except (Attendance.DoesNotExist, Attendance.MultipleObjectsReturned):
        pass

    # Get school terminology
    terminology = None
    try:
        terminology = SchoolTerminology.objects.get(school=student.school)
    except SchoolTerminology.DoesNotExist:
        pass

    context = {
        'student': student,
        'grade': ss.grade,
        'section': ss.section,
        'roll_no': ss.roll_no,
        'term': term,
        'session': current_session,
        'result_rows': result_rows,
        'grand_total_mo': grand_total_mo,
        'grand_total_fm': grand_total_fm,
        'gpa': gpa,
        'gpa_grade': gpa_grade,
        'has_ng': has_ng,
        'attendance': attendance,
        'th_label': terminology.theory_long if terminology else 'Theory',
        'pr_label': terminology.practical_long if terminology else 'Practical',
        'th_short': terminology.theory_short if terminology else 'TH',
        'pr_short': terminology.practical_short if terminology else 'PR',
    }
    return render(request, "webview/parent_result_detail.html", context)


@csrf_exempt
def teacher_homework(request):
    """Render teacher homework webview with robust error handling.

    Any unexpected exception is logged with a full traceback and a generic
    error page is displayed to the user.
    """
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

        # Fetch branch user entries; may be empty for teachers added without explicit branch linkage
        branch_users = BranchUser.objects.filter(user=user, status=True)

        # Determine admin status based on branch admin flag or superuser
        is_admin = user.is_superuser or (branch_users.filter(admin_status=True).exists() if branch_users else False)

        # Identify available schools
        if is_admin:
            if user.is_superuser:
                available_schools = list(SchoolBranch.objects.filter(status=True))
            else:
                available_schools = [bu.school for bu in branch_users if bu.admin_status]
        else:
            # Teacher-specific schools derived from TeacherSubjectAccess; combine with branch_user schools if present
            ts_access = TeacherSubjectAccess.objects.filter(
                teacher=user, session=current_session, status=True
            ).select_related('grade__school')
            schools_from_access = list(set(
                t.grade.school for t in ts_access if t.grade and t.grade.school
            ))
            if branch_users:
                available_schools = list(set(schools_from_access + [bu.school for bu in branch_users]))
            else:
                available_schools = schools_from_access
            if not available_schools:
                available_schools = list(SchoolBranch.objects.filter(status=True))

        if not available_schools:
            return render(request, "webview/error.html", {"error_title": "No Classes", "error_message": "You have no assigned subjects."})

        print("Available Schools: ",available_schools)
        school_id = 1 #request.GET.get('school_id') or request.POST.get('school_id')
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

        selected_date_str = request.GET.get('date')
        if selected_date_str:
            try:
                parts = selected_date_str.split('-')
                selected_date = nepali_datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
                logger = logging.getLogger(__name__)
                logger.debug("Parsed selected_date: %s", selected_date)
            except Exception:
                selected_date = nepali_datetime.date.today()
                logger = logging.getLogger(__name__)
                logger.debug("Failed to parse date '%s', using today: %s", selected_date_str, selected_date)
        else:
            selected_date = nepali_datetime.date.today()
            logger = logging.getLogger(__name__)
            logger.debug("No date provided, using today: %s", selected_date)

        # Prepare context for template rendering
        student_homeworks = []
        context = {
            'student_homeworks': student_homeworks,
            'selected_date': str(selected_date),
            'token': request.GET.get("token", ""),
        }

        message = ""

        # Filter subjects by selected school

        # Admin access: try primary branch filter, fallback to grade's school if no subjects found
        if is_admin:
            # Admin access: fetch all subjects for the current session regardless of school
            access_subjects = Subject.objects.filter(
                session=current_session,
                status=True,
            ).select_related('grade', 'section', 'branch')
            # If there are no subjects (unlikely), fallback to grade->school relationship
            if not access_subjects.exists():
                access_subjects = Subject.objects.filter(
                    session=current_session,
                    status=True,
                ).select_related('grade', 'section')
            access_entries = access_subjects
        else:
            # Teacher-specific subjects – try to locate the teacher record using various identifiers
            logger = logging.getLogger(__name__)
            phone = getattr(user, "mobile_number", None) or request.GET.get('phone')
            logger.info("Teacher lookup phone: %s", phone)
            # Primary attempt: direct FK relationship
            ts_access = TeacherSubjectAccess.objects.filter(
                teacher=user, session=current_session, status=True
            ).select_related('grade__school')
            if not ts_access.exists() and phone:
                # Fallback: match on teacher's mobile_number field
                ts_access = TeacherSubjectAccess.objects.filter(
                    teacher__mobile_number=phone, session=current_session, status=True
                ).select_related('grade__school')
            if not ts_access.exists() and phone:
                # Additional fallback: teacher model may store phone under a different field name
                ts_access = TeacherSubjectAccess.objects.filter(
                    teacher__phone=phone, session=current_session, status=True
                ).select_related('grade__school')
            access_entries = list(ts_access)
            if not access_entries:
                # ---------------------------------------------------
                # NEW: Branch‑User based fallback when no direct access rows
                # ---------------------------------------------------
                if branch_users:
                    inferred_entries = []
                    for bu in branch_users:
                        # Find subjects for the branch, grade & section of this bu
                        subject_qs = Subject.objects.filter(
                            session=current_session,
                            branch=bu.school,
                            grade=bu.grade,
                            section=bu.section,
                            status=True,
                        ).select_related('grade', 'section')
                        for sub in subject_qs:
                            entry = SimpleNamespace(
                                subject=sub,
                                grade=sub.grade,
                                section=sub.section,
                                grade_id=sub.grade.id if sub.grade else None,
                                section_id=sub.section.id if sub.section else None,
                            )
                            inferred_entries.append(entry)
                    access_entries = inferred_entries
                if not access_entries:
                    return render(request, "webview/error.html", {
                        "error_title": "No Subjects Assigned",
                        "error_message": "You have no subjects or classes assigned. Please contact the administrator."
                    })
                access_subjects = [e.subject for e in access_entries]
            else:
                access_subjects = [e.subject for e in access_entries]
        # If no subjects are assigned, try a fallback query using the Subject model for the selected school
        if not access_subjects:
            # Try fallback using branch first, then grade school
            fallback_subjects = Subject.objects.filter(
                session=current_session,
                branch=selected_school,
                status=True,
            ).select_related('grade', 'section')
            if not fallback_subjects.exists():
                fallback_subjects = Subject.objects.filter(
                    session=current_session,
                    grade__school=selected_school,
                    status=True,
                ).select_related('grade', 'section')
            access_subjects = list(fallback_subjects)
            # For fallback, we treat each subject as an entry without grade/section attributes
            # Create dummy entries with grade and section attributes for UI grouping
            # Build dummy access entries with required attributes for UI grouping
            access_entries = []
            for sub in fallback_subjects:
                entry = SimpleNamespace(
                    subject=sub,
                    grade=sub.grade,
                    section=sub.section,
                    grade_id=sub.grade.id if sub.grade else None,
                    section_id=sub.section.id if sub.section else None,
                    subject_id=sub.id,
                )
                access_entries.append(entry)
            if not access_subjects:
                message = "No subjects assigned for the selected school. Please contact the administrator."
            else:
                message = ""
        else:
            message = ""

            # Process bulk POST submissions (save homework)
            if request.method == "POST":
                updates_by_class = {}
                for entry in access_entries:
                    subject = entry.subject
                    # Ensure grade and section are present
                    if not entry.grade or not entry.section:
                        continue
                    input_name = f"hw_{entry.grade_id}_{entry.section_id}_{subject.id}"
                    hw_text = request.POST.get(input_name)
                    if hw_text is not None:
                        class_key = (entry.grade_id, entry.section_id)
                        updates_by_class.setdefault(class_key, {})[str(subject.id)] = hw_text.strip()

                if hasattr(selected_date, "to_datetime_date"):
                    greg_date_val = selected_date.to_datetime_date()
                elif hasattr(selected_date, "to_date"):
                    greg_date_val = selected_date.to_date()
                else:
                    greg_date_val = selected_date

                for (g_id, s_id), subjects_data in updates_by_class.items():
                    # Ensure both Nepali and Gregorian dates are stored
                    homework_obj, _ = Homework.objects.get_or_create(
                        session=current_session,
                        grade_id=g_id,
                        section_id=s_id,
                        nepali_date=selected_date,
                        defaults={"homework": "{}", "date": greg_date_val},
                    )
                    try:
                        hw_dict = json.loads(homework_obj.homework or "{}")
                    except Exception:
                        hw_dict = {}
                    for sub_id_str, text in subjects_data.items():
                        if sub_id_str not in hw_dict or isinstance(hw_dict.get(sub_id_str), str):
                            hw_dict[sub_id_str] = {}

                        if text:
                            hw_dict[sub_id_str][str(user.id)] = {
                                "teacher_name": user.get_full_name() or user.username,
                                "text": text
                            }
                        else:
                            if isinstance(hw_dict.get(sub_id_str), dict):
                                hw_dict[sub_id_str].pop(str(user.id), None)
                                if not hw_dict[sub_id_str]:
                                    hw_dict.pop(sub_id_str, None)
                    homework_obj.homework = json.dumps(hw_dict)
                    homework_obj.save()
                message = "All homework entries saved successfully!"

            # Build existing homework dictionary for UI
            grade_section_pairs = set()
            for entry in access_entries:
                if not entry.grade or not entry.section:
                    continue
                grade_section_pairs.add((entry.grade, entry.section))

            existing_homework = {}
            for grade, section in grade_section_pairs:
                try:
                    hw_obj = Homework.objects.get(
                        session=current_session,
                        grade=grade,
                        section=section,
                        nepali_date=selected_date,
                    )
                    existing_homework[(grade.id, section.id)] = json.loads(hw_obj.homework or "{}")
                except Homework.DoesNotExist:
                    if not grade or not section:
                        continue
                    existing_homework[(grade.id, section.id)] = {}

            # Group UI data
            def get_teacher_hw_text(hw_data, teacher_id_str):
                if isinstance(hw_data, str):
                    return hw_data
                elif isinstance(hw_data, dict):
                    t_data = hw_data.get(teacher_id_str)
                    if isinstance(t_data, dict):
                        return t_data.get("text", "")
                return ""

            grouped_ui = {}
            for entry in access_entries:
                # Determine the subject object based on entry type
                if hasattr(entry, 'subject'):
                    subject_obj = entry.subject
                else:
                    subject_obj = entry

                # Ensure grade and section are present
                if not getattr(entry, 'grade', None) or not getattr(entry, 'section', None):
                    continue

                school_name = entry.grade.school.name
                class_name = f"Grade {entry.grade.grade_name} - Section {entry.section.section}"
                
                hw_val = existing_homework.get((entry.grade_id, entry.section_id), {}).get(str(subject_obj.id), "")
                
                grouped_ui.setdefault(school_name, {}).setdefault(class_name, []).append({
                    "subject": subject_obj,
                    "input_name": f"hw_{entry.grade_id}_{entry.section_id}_{subject_obj.id}",
                    "value": get_teacher_hw_text(hw_val, str(user.id)),
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
    return render(request, "webview/error.html", {"error_title": "No Content", "error_message": "Unable to load teacher homework. Please ensure you are assigned to a school and subjects."})

def teacher_marks(request):
    from django.db.models import Q
    from sms.models import SchoolTerm, SchoolGrade, Section
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
        # Determine available schools for non-admin teachers
        # First, try direct TeacherSubjectAccess entries
        ts_access = TeacherSubjectAccess.objects.filter(
            teacher=user, session=current_session, status=True
        ).select_related('grade__school')
        schools_from_access = list({
            t.grade.school for t in ts_access if getattr(t, 'grade', None) and t.grade.school
        })
        # If no direct entries, fallback to BranchUser linked schools
        if not schools_from_access:
            if branch_users:
                schools_from_access = list({bu.school for bu in branch_users})
        # Ensure we have at least one school
        if not schools_from_access:
            schools_from_access = list(SchoolBranch.objects.filter(status=True))
        available_schools = schools_from_access
        
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
    terms = SchoolTerm.objects.filter(
        Q(active=True) | Q(status__value__iexact='current for marks entry'),
        school=selected_school, 
        year=current_session
    )
    if not term_id:
        return render(request, "webview/teacher_select_step.html", {
            "step": "term", "items": terms, "school": selected_school, "token": token
        })
        
    # 3. Grade & Section Selection
    if is_admin:
        from sms.models import Section, Subject
        all_sections = Section.objects.filter(grade__school=selected_school, session=current_session).select_related('grade')
        unique_classes = set((sec.grade, sec) for sec in all_sections if sec.grade)
    else:
        # Direct TeacherSubjectAccess for the selected school
        ts_access = TeacherSubjectAccess.objects.filter(
            teacher=user,
            session=current_session,
            grade__school=selected_school,
            status=True,
        ).select_related('grade', 'section', 'subject')
        unique_classes = set((t.grade, t.section) for t in ts_access if t.grade and t.section)
        
        # Fallback to BranchUser subjects if none found
        if not unique_classes and branch_users.filter(school=selected_school).exists():
            for bu in branch_users.filter(school=selected_school):
                if bu.grade and bu.section:
                    unique_classes.add((bu.grade, bu.section))
                    
    if not unique_classes:
        return render(request, "webview/error.html", {"error_title": "No Classes Assigned", "error_message": "You have no classes assigned for the selected school. Please contact the administrator."})
        
    if not grade_id or not section_id:
        classes_data = [{'grade': g, 'section': s} for g, s in unique_classes]
        return render(request, "webview/teacher_select_step.html", {
            "step": "class", "items": classes_data, "term_id": term_id, "school": selected_school, "token": token
        })
        
    # 4. Subject Routing
    if is_admin:
        subjects_in_class = list(Subject.objects.filter(
            session=current_session,
            grade_id=grade_id,
            status=True
        ).filter(Q(section_id=section_id) | Q(section__isnull=True)))
    else:
        subjects_in_class = [t.subject for t in ts_access if str(t.grade_id) == str(grade_id) and str(t.section_id) == str(section_id)]
        if not subjects_in_class and branch_users.filter(school=selected_school).exists():
            subjects_in_class = list(Subject.objects.filter(
                session=current_session,
                grade_id=grade_id,
                status=True
            ).filter(Q(section_id=section_id) | Q(section__isnull=True)))
            
    if len(subjects_in_class) == 1 or subject_id:
        final_subject_id = subject_id if subject_id else subjects_in_class[0].id
        # Route directly to the mobile marks entry
        redirect_url = f"{reverse('teacher_marks_entry')}?token={token}&term={term_id}&grade={grade_id}&section={section_id}&subject={final_subject_id}"
        return redirect(redirect_url)
    else:
        term_obj = SchoolTerm.objects.filter(id=term_id).first()
        grade_obj = SchoolGrade.objects.filter(id=grade_id).first()
        section_obj = Section.objects.filter(id=section_id).first()
        
        return render(request, "webview/teacher_select_step.html", {
            "step": "subject", "items": subjects_in_class, "term_id": term_id, 
            "grade_id": grade_id, "section_id": section_id, "school": selected_school, "token": token,
            "term_obj": term_obj, "grade_obj": grade_obj, "section_obj": section_obj
        })


@csrf_exempt
def teacher_marks_entry(request):
    user = validate_webview_token(request, "teacher")
    token = request.GET.get('token') or request.POST.get('token')
    if not user:
        return render(request, "webview/error.html", {"error_title": "Unauthorized Access", "error_message": "Invalid token."})
        
    current_session = get_current_session()
    if not current_session:
        return render(request, "webview/error.html", {"error_title": "Configuration Error", "error_message": "No active academic session."})
        
    term_id = request.POST.get("term") or request.GET.get("term")
    grade_id = request.POST.get("grade") or request.GET.get("grade")
    section_id = request.POST.get("section") or request.GET.get("section")
    subject_id = request.POST.get("subject") or request.GET.get("subject")
    
    if not (term_id and grade_id and section_id and subject_id):
        return render(request, "webview/error.html", {"error_title": "Missing Parameters", "error_message": "Required parameters are missing."})
        
    from sms.models import SchoolGrade, Section, Subject, SchoolTerm, StudentSession, GradeFullMarks, MarkObtained
    grade = SchoolGrade.objects.get(id=grade_id)
    section = Section.objects.get(id=section_id)
    subject = Subject.objects.get(id=subject_id)
    term_exam = SchoolTerm.objects.get(id=term_id)
    school = grade.school
    
    student_query = StudentSession.objects.filter(
        session=current_session, grade=grade, section=section, status=True
    ).select_related('student')
    students = student_query.order_by('roll_no')
    
    try:
        fullmark = GradeFullMarks.objects.get(
            school=school, grade=grade, session=current_session,
            term=term_exam, subject=subject,
        )
    except GradeFullMarks.DoesNotExist:
        return render(request, "webview/error.html", {"error_title": "Configuration Error", "error_message": "Full marks configuration missing for this subject."})
        
    new_desc = {}
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
        
        if request.method == "POST":
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
            
    context = {
        "school": school,
        "term_exam": term_exam,
        "grade": grade,
        "section": section,
        "subject": subject,
        "praMarks": fullmark.pr_fm > 0,
        "fullmark": fullmark,
        "new_desc": new_desc,
        "token": token,
        "success": request.method == "POST",
    }
    return render(request, "webview/teacher_marks_form.html", context)

