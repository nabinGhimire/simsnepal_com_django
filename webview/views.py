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
            logger = logging.getLogger(__name__)
            logger.debug("parent_homework: token=%s, validated phone=%s, selected_date=%s", request.GET.get('token'), phone, selected_date)
        except Exception:
            selected_date = nepali_datetime.date.today()
            logger = logging.getLogger(__name__)
            logger.debug("Failed to parse date '%s', using today: %s", selected_date_str, selected_date)
    else:
        selected_date = nepali_datetime.date.today()
        logger = logging.getLogger(__name__)
        logger.debug("No date provided, using today: %s", selected_date)
        
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
            if hw_dict:
                logger.debug("Homework found for grade %s, section %s on %s: %s", grade.id, section.id, selected_date, hw_dict)
            else:
                logger.debug("No homework entry for grade %s, section %s on %s", grade.id, section.id, selected_date)
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
        context = {
            'student_homeworks': student_homeworks,
            'selected_date': str(selected_date),
            'parent_phone': phone,
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

                for (g_id, s_id), subjects_data in updates_by_class.items():
                    # Ensure both Nepali and Gregorian dates are stored
                    homework_obj, _ = Homework.objects.get_or_create(
                        session=current_session,
                        grade_id=g_id,
                        section_id=s_id,
                        nepali_date=selected_date,
                        defaults={"homework": "{}", "date": selected_date.to_date()},
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
                grouped_ui.setdefault(school_name, {}).setdefault(class_name, []).append({
                    "subject": subject_obj,
                    "input_name": f"hw_{entry.grade_id}_{entry.section_id}_{subject_obj.id}",
                    "value": existing_homework.get((entry.grade_id, entry.section_id), {}).get(str(subject_obj.id), ""),
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
    terms = SchoolTerm.objects.filter(school=selected_school, year=current_session, active=True)
    if not term_id:
        return render(request, "webview/teacher_select_step.html", {
            "step": "term", "items": terms, "school": selected_school, "token": token
        })
        
    # 3. Grade & Section Selection
    if is_admin:
        access_subjects = Subject.objects.filter(
            session=current_session,
            branch=selected_school,
            status=True,
        ).select_related('grade', 'section')
    else:
        # Direct TeacherSubjectAccess for the selected school
        ts_access = TeacherSubjectAccess.objects.filter(
            teacher=user,
            session=current_session,
            grade__school=selected_school,
            status=True,
        ).select_related('grade', 'section', 'subject')
        access_subjects = [t.subject for t in ts_access]
        # Fallback to BranchUser subjects if none found
        if not access_subjects and branch_users.filter(school=selected_school).exists():
            inferred = []
            for bu in branch_users.filter(school=selected_school):
                subject_qs = Subject.objects.filter(
                    session=current_session,
                    branch=bu.school,
                    grade=bu.grade,
                    section=bu.section,
                    status=True,
                ).select_related('grade', 'section')
                inferred.extend(subject_qs)
            access_subjects = inferred
    if not access_subjects:
        return render(request, "webview/error.html", {"error_title": "No Subjects Assigned", "error_message": "You have no subjects assigned for the selected school. Please contact the administrator."})
        
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
