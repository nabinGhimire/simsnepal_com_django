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


def parent_homework(request):
    phone = request.GET.get("token") or request.POST.get("token")
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
        
        homework_qs = Homework.objects.filter(
            session=current_session,
            grade=grade,
            section=section,
            nepali_date=selected_date,
        )
        
        if not homework_qs.exists():
            hw_dict = {}
        else:
            hw_dict = json.loads(homework_qs.first().homework or "{}")
            
        subjects = Subject.objects.filter(
            Q(section=section) | Q(section__isnull=True),
            session=current_session,
            grade=grade,
            status=True
        )
                
        hw_list = []
        for sub in subjects:
            content_data = hw_dict.get(str(sub.id))
            if not content_data:
                continue
            if isinstance(content_data, str):
                hw_list.append({
                    'subject': sub.subject,
                    'entries': [{'teacher_name': None, 'text': content_data}]
                })
            elif isinstance(content_data, dict):
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
            'homeworks': hw_list,
        })
        
    context = {
        'student_homeworks': student_homeworks,
        'selected_date': str(selected_date),
        'parent_phone': phone,
        'token': request.GET.get("token", ""),
        'current_session': current_session,
    }
    return render(request, "webview/parent_homework.html", context)


def parent_result(request):
    phone = request.GET.get("token") or request.POST.get("token")
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
    
    # Get school-wide live result settings (term + grade_list + status)
    live_result_obj = LiveResult.objects.filter(school=students.first().school).first() if students.exists() else None
    live_grade_list = []
    live_result_status = False
    live_result_term = None
    if live_result_obj:
        try:
            live_grade_list = json.loads(live_result_obj.grade_list or "[]")
        except Exception:
            live_grade_list = []
        live_result_status = live_result_obj.status
        live_result_term = live_result_obj.term
        
    for student in students:
        ss_qs = StudentSession.objects.filter(
            student=student,
            session=current_session,
            status=True
        ).select_related('grade', 'section')
        
        if not ss_qs.exists():
            continue
            
        ss = ss_qs.first()
        
        # Read per-grade result config (falls back to school-wide defaults if none)
        from exam.models import GradeResultConfig
        grade_config = GradeResultConfig.objects.filter(
            school=student.school,
            year=current_session,
            grade=ss.grade,
        ).first()

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
            # A term is visible to parents only if ALL of:
            # 1. Term status is published (status_id == 3)
            # 2. LiveResult publishing is enabled for the school
            # 3. This term matches the LiveResult term (or LiveResult covers all)
            # 4. Student's grade is in LiveResult.grade_list
            term_published = (
                term.status_id == 3
                and live_result_status
                and (live_result_term is None or int(term.id) == int(live_result_term))
                and int(ss.grade.id) in live_grade_list
            )
            if grade_config and not grade_config.is_published:
                term_published = False
                
            terms_list.append({
                'term': term,
                'is_published': term_published,
                'assessment_source': grade_config.assessment_source if grade_config else 'exam',
                'grading_type': grade_config.grading_type if grade_config else 0,
                'ledger_type': grade_config.ledger_type if grade_config else 1,
                'calculation_type': grade_config.calculation_type if grade_config else 'legacy',
                'detail_url': f"/webview/parent/result/detail/?token={token}&student={student.reg_no}&term={term.id}"
            })
            
        student_results.append({
            'student': student,
            'grade': ss.grade,
            'section': ss.section,
            'roll_no': ss.roll_no,
            'assessment_source': grade_config.assessment_source if grade_config else 'exam',
            'grading_type': grade_config.grading_type if grade_config else 0,
            'ledger_type': grade_config.ledger_type if grade_config else 1,
            'calculation_type': grade_config.calculation_type if grade_config else 'legacy',
            'is_published': grade_config.is_published if grade_config else False,
            'terms': terms_list,
        })
        
    context = {
        'student_results': student_results,
        'parent_phone': phone,
        'current_session': current_session,
    }
    return render(request, "webview/parent_result.html", context)


def parent_result_detail(request):
    from django.shortcuts import get_object_or_404
    from django.db.models import Q
    from exam.models import GradeFullMarks, Attendance, Rank, SchoolTerminology, SchoolResultType, LiveResult
    from django.contrib.auth import get_user_model
    
    phone = request.GET.get("token") or request.POST.get("token")
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
    
    # Verify this grade is included in LiveResult grade_list for this school
    live_result_obj = LiveResult.objects.filter(school=student.school).first()
    if live_result_obj:
        try:
            live_grade_list = json.loads(live_result_obj.grade_list or "[]")
        except Exception:
            live_grade_list = []
        if not live_result_obj.status:
            return render(request, "webview/error.html", {
                "error_title": "Results Not Published",
                "error_message": "Result publishing is disabled for this school."
            })
        if int(live_result_obj.term) != int(term.id):
            return render(request, "webview/error.html", {
                "error_title": "Wrong Term",
                "error_message": f"Results for term '{term.term_name}' are not the currently published term."
            })
        if int(ss.grade.id) not in live_grade_list:
            return render(request, "webview/error.html", {
                "error_title": "Results Not Published for Your Grade",
                "error_message": f"Results for {ss.grade.grade_name} are not published for this term."
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
    
    # Read per-grade result config (falls back to school-wide defaults if none)
    from exam.models import GradeResultConfig
    grade_config = GradeResultConfig.objects.filter(
        school=student.school,
        year=current_session,
        grade=ss.grade,
    ).first()
    
    grading_type = grade_config.grading_type if grade_config else 0
    ledger_type = grade_config.ledger_type if grade_config else 1
    calculation_type = grade_config.calculation_type if grade_config else 'legacy'
    assessment_source = grade_config.assessment_source if grade_config else 'exam'
    
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
    
    # Get school terminology early
    terminology = None
    try:
        terminology = SchoolTerminology.objects.get(school=student.school)
    except SchoolTerminology.DoesNotExist:
        pass
    
    # Build result rows with Non-Graded calculation (same as panel)
    result_rows = []
    grand_total_mo = 0
    grand_total_fm = 0
    total_gp_points = 0
    subject_count = 0
    has_ng = False
    failed_subjects = 0
    absent_subjects = 0
    
    for mark in marks:
        fm = full_marks_map.get(mark.subject_id)
        th_fm = fm.th_fm if fm else 0
        pr_fm = fm.pr_fm if fm else 0
        th_pm = fm.th_pm if fm else 0
        pr_pm = fm.pr_pm if fm else 0
        total_fm = th_fm + pr_fm
        
        if mark.is_absent:
            # Theory row for absent
            th_row = {
                'subject': mark.subject.subject,
                'component': 'TH',
                'th_short': terminology.theory_short if terminology else 'TH',
                'pr_short': terminology.practical_short if terminology else 'IN',
                'th_fm': th_fm, 'pr_fm': 0,
                'th_mo': '-', 'pr_mo': '-',
                'total_mo': 0, 'total_fm': th_fm,
                'th_grade': '-', 'pr_grade': '-',
                'final_grade': 'Abs', 'final_gp': 0,
                'is_absent': True, 'failed': True,
                'percent': 0,
            }
            result_rows.append(th_row)
            
            # Practical row for absent (if practical exists)
            if pr_fm > 0:
                pr_row = {
                    'subject': mark.subject.subject,
                    'component': 'PR',
                    'th_short': terminology.theory_short if terminology else 'TH',
                    'pr_short': terminology.practical_short if terminology else 'IN',
                    'th_fm': 0, 'pr_fm': pr_fm,
                    'th_mo': '-', 'pr_mo': '-',
                    'total_mo': 0, 'total_fm': pr_fm,
                    'th_grade': '-', 'pr_grade': '-',
                    'final_grade': 'Abs', 'final_gp': 0,
                    'is_absent': True, 'failed': True,
                    'percent': 0,
                }
                result_rows.append(pr_row)
                
                has_ng = True
                absent_subjects += 1  # Count at subject level (once per subject)
        else:
            total_mo = mark.th_mo + mark.pr_mo
            
            # Non-Graded calculation: use GradeAndGpaNonGradeTheory/Practical (same as panel)
            from panel.func import GradeAndGpaNonGradeTheory, GradeAndGpaNonGradePractical
            
            # Calculate pass marks like panel: use GradeFullMarks.pm or default to 35%/40%
            th_pm_calc = th_pm if th_pm > 0 else int(th_fm * 0.35) if th_fm > 0 else 0
            pr_pm_calc = pr_pm if pr_pm > 0 else int(pr_fm * 0.40) if pr_fm > 0 else 0
            
            # Theory calculation
            th_grade = th_symbol = th_point = ''
            th_failed = False
            if th_fm > 0:
                th_obj = GradeAndGpaNonGradeTheory(th_fm, mark.th_mo, th_pm_calc)
                th_grade = th_obj.th_grade
                th_symbol = th_obj.th_symbol
                th_point = th_obj.th_point
                th_failed = th_obj.fail > 0
            else:
                th_grade = th_symbol = '-'
                th_point = 0
            
            # Practical calculation
            pr_grade = pr_symbol = pr_point = ''
            pr_failed = False
            if pr_fm > 0:
                pr_obj = GradeAndGpaNonGradePractical(pr_fm, mark.pr_mo, pr_pm_calc)
                pr_grade = pr_obj.pr_grade
                pr_symbol = pr_obj.pr_symbol
                pr_point = pr_obj.pr_point
                pr_failed = pr_obj.fail > 0
            else:
                pr_grade = pr_symbol = '-'
                pr_point = 0
            
            subject_failed = th_failed or pr_failed
            is_absent = False
            
            # Theory row
            if th_failed:
                final_grade_display = 'NG'
                final_gp = 0
            elif th_fm > 0:
                th_percent = get_percentage(mark.th_mo, th_fm)
                th_grade_letter, th_symbol_final, th_point_final = get_grade_point(th_percent)
                final_grade_display = f"{th_grade_letter}{th_symbol_final}".strip()
                final_gp = th_point_final
            else:
                final_grade_display = '-'
                final_gp = 0
                
            th_row = {
                'subject': mark.subject.subject,
                'component': 'TH',
                'th_short': terminology.theory_short if terminology else 'TH',
                'pr_short': terminology.practical_short if terminology else 'IN',
                'th_fm': th_fm, 'pr_fm': 0,
                'th_mo': mark.th_mo, 'pr_mo': 0,
                'total_mo': mark.th_mo, 'total_fm': th_fm,
                'th_grade': f"{th_grade}{th_symbol}".strip() if th_fm > 0 else '-',
                'pr_grade': '-',
                'final_grade': final_grade_display,
                'final_gp': final_gp if not th_failed else 0,
                'is_absent': False,
                'failed': th_failed,
                'percent': round(get_percentage(mark.th_mo, th_fm), 2) if th_fm > 0 else 0,
            }
            result_rows.append(th_row)
            
            if th_failed:
                has_ng = True
                failed_subjects += 1
            else:
                total_gp_points += th_point if th_fm > 0 else 0
                if th_fm > 0:
                    subject_count += 1
                    
            # Practical row (if practical exists)
            if pr_fm > 0:
                if pr_failed:
                    final_grade_display = 'NG'
                    final_gp = 0
                else:
                    pr_percent = get_percentage(mark.pr_mo, pr_fm)
                    pr_grade_letter, pr_symbol_final, pr_point_final = get_grade_point(pr_percent)
                    final_grade_display = f"{pr_grade_letter}{pr_symbol_final}".strip()
                    final_gp = pr_point_final
                    
                pr_row = {
                    'subject': mark.subject.subject,
                    'component': 'PR',
                    'th_short': terminology.theory_short if terminology else 'TH',
                    'pr_short': terminology.practical_short if terminology else 'PR',
                    'th_fm': 0, 'pr_fm': pr_fm,
                    'th_mo': 0, 'pr_mo': mark.pr_mo,
                    'total_mo': mark.pr_mo, 'total_fm': pr_fm,
                    'th_grade': '-',
                    'pr_grade': f"{pr_grade}{pr_symbol}".strip() if pr_fm > 0 else '-',
                    'final_grade': final_grade_display,
                    'final_gp': final_gp if not pr_failed else 0,
                    'is_absent': False,
                    'failed': pr_failed,
                    'percent': round(get_percentage(mark.pr_mo, pr_fm), 2) if pr_fm > 0 else 0,
                }
                result_rows.append(pr_row)
                
                if pr_failed:
                    has_ng = True
                    failed_subjects += 1
                else:
                    total_gp_points += pr_point
                    if pr_fm > 0:
                        subject_count += 1
                        
            if not subject_failed and (th_fm > 0 or pr_fm > 0):
                grand_total_mo += total_mo
                grand_total_fm += total_fm
                
            if not subject_failed and (th_fm > 0 or pr_fm > 0):
                total_gp_points += th_point if th_fm > 0 else 0
                if th_fm > 0:
                    subject_count += 1
                    
    # Add serial numbers and group by subject for rowspan display
    subject_groups = {}
    for row in result_rows:
        subject_name = row['subject']
        if subject_name not in subject_groups:
            subject_groups[subject_name] = []
        subject_groups[subject_name].append(row)
    
    # Create grouped result rows with rowspan info
    grouped_rows = []
    sn = 0
    for subject_name, rows in subject_groups.items():
        sn += 1
        has_pr = any(r['component'] == 'PR' for r in rows)
        for row in rows:
            row['sn'] = sn
            row['rowspan'] = 2 if has_pr else 1
            row['is_first_row'] = row['component'] == 'TH'
        grouped_rows.extend(rows)
    
    result_rows = grouped_rows
    
    # Calculate GPA - if any subject failed or absent, GPA should be 0.0
    if has_ng:
        gpa = '0.0'
    else:
        gpa = round(total_gp_points / subject_count, 2) if subject_count > 0 else '0.0'
    
    # Count NG subjects for display
    ng_count = failed_subjects
    absent_count = absent_subjects
    
    # Calculate overall percent
    overall_percent = round(get_percentage(grand_total_mo, grand_total_fm), 2) if grand_total_fm > 0 else 0
    
    # Get attendance if available
    attendance = None
    try:
        attendance = Attendance.objects.get(
            reg_no=student, grade=ss.grade,
            session=current_session, term=term
        )
    except (Attendance.DoesNotExist, Attendance.MultipleObjectsReturned):
        pass
    
    # Calculate GPA grade
    from panel.func import get_grade_point_from_point
    gpa_float = float(gpa) if isinstance(gpa, str) else gpa
    gpa_grade, gpa_symbol = get_grade_point_from_point(gpa_float) if gpa_float > 0 else ('NG', ' ')
    gpa_grade_display = f"{gpa_grade}{gpa_symbol}".strip()
    
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
        'gpa_grade': gpa_grade_display,
        'has_ng': has_ng,
        'ng_count': ng_count,
        'overall_percent': overall_percent,
        'attendance': attendance,
        'th_label': terminology.theory_long if terminology else 'Theory',
        'pr_label': terminology.practical_long if terminology else 'Practical',
        'th_short': terminology.theory_short if terminology else 'TH',
        'pr_short': terminology.practical_short if terminology else 'PR',
        'current_session': current_session,
        'grading_type': grading_type,
        'ledger_type': ledger_type,
        'calculation_type': calculation_type,
        'assessment_source': assessment_source,
    }
    
    # Always use Non-Graded template for parents (simplified view with attendance)
    return render(request, "webview/parent_result_detail_ng.html", context)


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
        import traceback
        import logging
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