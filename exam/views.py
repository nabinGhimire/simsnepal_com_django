"""
Exam app views.
All views render exam/ templates with the attendance-style design system.
"""
import os
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

# Re-use panel helpers — they are lightweight and don't render anything
from panel.views import get_branch_info, get_current_session

# Import shared exam functions
from exam.func import (
    calculate_student_result,
    build_grade_ledger_context,
    get_grade_config,
    calculate_rank,
)


def _get_result_config(school, session, grade):
    """
    Get unified result calculation configuration for a grade/session.
    
    Priority:
    1. GradeResultConfig (per-grade settings)
    2. LiveResult (school-wide defaults)
    3. SchoolResultType (session defaults)
    4. Hardcoded defaults
    
    Returns dict with all calculation parameters.
    """
    from exam.models import GradeResultConfig, LiveResult, SchoolResultType
    
    gc = GradeResultConfig.objects.filter(
        school=school, year=session, grade=grade
    ).first()
    
    if gc:
        return {
            'grading_type': gc.grading_type,           # 0=Legacy, 1=Non-Grade, 2=New
            'ledger_type': gc.ledger_type,             # 1=Marks, 2=Grade
            'calculation_type': gc.calculation_type,   # legacy, weighted
            'assessment_source': gc.assessment_source, # exam, internal
            'th_pass_type': gc.th_pass_type,           # percentage, gpa, marks
            'th_pass_value': float(gc.th_pass_value),
            'pr_pass_type': gc.pr_pass_type,
            'pr_pass_value': float(gc.pr_pass_value),
            'source': 'GradeResultConfig',
        }
    
    # Fallback to school-wide LiveResult
    lr = LiveResult.objects.filter(school=school).first()
    sr = SchoolResultType.objects.filter(school=school, session=session).first()
    
    return {
        'grading_type': getattr(lr, 'calculation_type', 0) if lr else 0,
        'ledger_type': 1,
        'calculation_type': 'legacy',
        'assessment_source': 'exam',
        'th_pass_type': 'percentage',
        'th_pass_value': 35.0,
        'pr_pass_type': 'percentage',
        'pr_pass_value': 35.0,
        'source': 'Defaults',
    }


def _get_ledger_config(request, config):
    """
    Merge runtime POST parameters with base config for ledger printing.
    Runtime params override base config.
    """
    cfg = config.copy()
    
    # Override from POST if provided
    if request.method == 'POST':
        if 'grading_type' in request.POST and request.POST.get('grading_type') != '':
            cfg['grading_type'] = int(request.POST.get('grading_type'))
        if 'ledger_type' in request.POST and request.POST.get('ledger_type') != '':
            cfg['ledger_type'] = int(request.POST.get('ledger_type'))
        if 'calculation_type' in request.POST and request.POST.get('calculation_type'):
            cfg['calculation_type'] = request.POST.get('calculation_type')
        if 'ledgermode' in request.POST and request.POST.get('ledgermode') != '':
            cfg['ledgermode'] = int(request.POST.get('ledgermode'))
        if 'ledgerttype' in request.POST and request.POST.get('ledgerttype') != '':
            cfg['ledgerttype'] = int(request.POST.get('ledgerttype'))
        if 'grading_type' in request.POST and request.POST.get('grading_type') != '':
            cfg['grading_type'] = int(request.POST.get('grading_type'))
    
    # Set defaults for ledger-specific params
    cfg.setdefault('ledgermode', 1)      # 1=Standard, 2=Weighted, 3=Consolidated
    cfg.setdefault('ledgerttype', 2)     # 1=Grade, 2=Marks
    cfg.setdefault('printtype', 1)       # 1=Detail, 2=Summary
    
    return cfg


def _nav_context(request):
    """Common context for exam navbar — grades, levels."""
    from sms.models import BranchUser, SchoolGrade, GradeLevel
    try:
        bu = BranchUser.objects.select_related('school').get(user=request.user)
        school = bu.school
    except Exception:
        return {}
    grades = SchoolGrade.objects.filter(school=school, active=True).select_related('level').order_by('level__id', 'grade_weight', 'grade_name')
    level_ids = grades.values_list('level_id', flat=True).distinct()
    levels = list(GradeLevel.objects.filter(id__in=level_ids).order_by('id'))
    return {'nav_grades': grades, 'nav_grade_levels': levels}


# ── Dashboard ───────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    from sms.models import SchoolGrade, GradeLevel, Subject, MarkObtained
    from exam.models import SchoolTerm, GradeFullMarks, LiveResult

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    current_session = get_current_session()

    # Get current term only
    current_term = SchoolTerm.objects.filter(
        school=school, year=current_session, status__value__icontains='Current'
    ).first()
    
    # Fallback to first active term if no "Current" status term
    if not current_term:
        current_term = SchoolTerm.objects.filter(
            school=school, year=current_session, active=True
        ).first()

    grades = SchoolGrade.objects.filter(school=school, active=True).select_related('level').order_by('level__id', 'grade_weight', 'grade_name')
    level_ids = grades.values_list('level_id', flat=True).distinct()
    levels = list(GradeLevel.objects.filter(id__in=level_ids).order_by('id'))

    # Per-grade subject completion stats for CURRENT term only
    grade_stats = []
    if current_term:
        for grade in grades:
            total_subjects = Subject.objects.filter(
                branch=school, session=current_session, grade=grade, status=True
            ).count()

            # Subjects that have at least one MarkObtained entry for this grade/session/term
            subjects_with_marks = Subject.objects.filter(
                branch=school, session=current_session, grade=grade, status=True,
                markobtained__session=current_session,
                markobtained__school=school,
                markobtained__grade=grade,
                markobtained__term=current_term
            ).distinct().count()

            missing_subjects = total_subjects - subjects_with_marks

            grade_stats.append({
                'grade': grade,
                'total_subjects': total_subjects,
                'subjects_with_marks': subjects_with_marks,
                'missing_subjects': missing_subjects,
                'completion_pct': round((subjects_with_marks / total_subjects * 100), 1) if total_subjects > 0 else 0,
            })

    live_result = LiveResult.objects.filter(school=school).first()

    context = {
        'current_session': current_session,
        'current_term': current_term,
        'grade_stats': grade_stats,
        'school': school,
        'branchuser': branchuser,
        'nav_grades': grades,
        'nav_grade_levels': levels,
        'live_result': live_result,
    }
    return render(request, 'exam/dashboard.html', context)

    #vel, Subject, MarkObtained
    #from exam.models import SchoolTerm, GradeFullMarks, LiveResult

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    current_session = get_current_session()

    exam_terms = SchoolTerm.objects.filter(school=school, active=True).order_by('id')
    grades = SchoolGrade.objects.filter(school=school, active=True).select_related('level').order_by('level__id', 'grade_weight', 'grade_name')
    level_ids = grades.values_list('level_id', flat=True).distinct()
    levels = list(GradeLevel.objects.filter(id__in=level_ids).order_by('id'))

    # Per-grade subject completion stats per term (grouped by term)
    term_grade_stats = []

    # Only show current term(s) with status='Current'
    current_term = SchoolTerm.objects.filter(
        school=school, year=current_session, status__value__icontains='Current'
    ).first()

    for term in exam_terms:
        grade_stats = []
        for grade in grades:
            total_subjects = Subject.objects.filter(
                branch=school, session=current_session, grade=grade, status=True
            ).count()

            # Subjects that have at least one MarkObtained entry for this grade/session/term
            subject_data = Subject.objects.filter(
                branch=school, session=current_session, grade=grade, status=True,
                markobtained__session=current_session,
                markobtained__school=school,
                markobtained__grade=grade,
                markobtained__term=term
            ).distinct().count()

            missing_subjects = total_subjects - subjects_with_marks

            grade_stats.append({
                'grade': grade,
                'total_subjects': total_subjects,
                'subjects_with_marks': subjects_with_marks,
                'missing_subjects': missing_subjects,
                'completion_pct': round((subjects_with_marks / total_subjects * 100), 1) if total_subjects > 0 else 0,
            })

        term_grade_stats.append({
            'term': term,
            'grade_stats': grade_stats,
        })

    live_result = LiveResult.objects.filter(school=school).first()

    context = {
        'current_session': current_session,
        'exam_terms': exam_terms,
        'term_grade_stats': term_grade_stats,
        'current_term': current_term,
        'school': school,
        'branchuser': branchuser,
        'nav_grades': grades,
        'nav_grade_levels': levels,
        'live_result': live_result,
    }
    return render(request, 'exam/dashboard.html', context)


def _detect_term_action(request):
    """Detect which term action URL was used and set the appropriate action."""
    url_name = request.resolver_match.url_name if request.resolver_match else ''
    if url_name == 'add_term':
        return 'addterm'
    elif url_name == 'edit_term':
        return 'changeterm'
    elif url_name == 'term_calculation':
        return 'result_calc'
    return None

@login_required
def terms_list(request, term_id=None):
    from sms.models import SchoolGrade
    from exam.models import SchoolTerm, SchoolTermStatus, ResultManagement

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    current_session = get_current_session()

    # action comes from GET for navigation, but form submissions (changeterm,
    # addterm, result_calc) post a hidden <input name="action"> field, so also
    # read it from POST; otherwise the submitted action is ignored and nothing
    # is saved.
    action = request.GET.get('action', 'listterm')
    if request.method == 'POST':
        action = request.POST.get('action', action)
    # URL-based action detection for clean routes
    if action == 'listterm':
        url_action = _detect_term_action(request)
        if url_action:
            action = url_action
    term_status = SchoolTermStatus.objects.all()

    change_name = False
    term_name = None

    # URL-based cn for edit_term route
    if request.method == 'GET' and 'cn' in request.GET:
        cn = request.GET['cn']
    elif request.resolver_match and request.resolver_match.url_name == 'edit_term':
        cn = request.resolver_match.kwargs.get('term_id')
    else:
        cn = None

    if cn:
        try:
            term_name = SchoolTerm.objects.get(id=cn)
            if term_name.school == school:
                change_name = True
            else:
                term_name = None
        except SchoolTerm.DoesNotExist:
            term_name = None

    if action == 'addterm':
        if request.method == 'POST':
            term_name_post = request.POST.get('term_name', '').strip()
            name_in_short = request.POST.get('name_in_short', '').strip() or None
            year_id = request.POST.get('year_id')
            grade_id = request.POST.get('grade_id')
            final_term = request.POST.get('final_term') == 'on'
            status_id = request.POST.get('status', '1')

            if term_name_post and year_id:
                SchoolTerm.objects.create(
                    school=school,
                    year_id=year_id,
                    term_name=term_name_post,
                    name_in_short=name_in_short,
                    status_id=status_id,
                    final_term=final_term,
                    active=True,
                )
                messages.success(request, 'Exam term added.')
            return redirect('exam:terms')

        grades = SchoolGrade.objects.filter(school=school, active=True).order_by('grade_weight') if school else []
        ctx = _nav_context(request)
        ctx.update({
            'school': school,
            'branchuser': branchuser,
            'current_session': current_session,
            'is_terms': True,
            'action': 'addterm',
            'grades': grades,
            'term_status': term_status,
        })
        return render(request, 'exam/terms_list.html', ctx)

    if action == 'changeterm' and request.method == 'POST':
        term_id = request.POST.get('term_id')
        new_name = request.POST.get('term_name', '').strip()
        new_short = request.POST.get('term_name_in_short', '').strip() or None
        new_active = request.POST.get('activeStatus') == '1'
        new_status_id = request.POST.get('termStatus', '1')
        new_final = request.POST.get('final_term') == 'yes'
        new_final_name = request.POST.get('final_term_name', '').strip() or None

        try:
            term = SchoolTerm.objects.get(id=term_id, school=school)
            term.term_name = new_name
            term.name_in_short = new_short
            term.active = new_active
            term.status_id = new_status_id
            term.final_term = new_final
            term.final_term_name = new_final_name
            term.save()
            messages.success(request, 'Term updated.')
        except SchoolTerm.DoesNotExist:
            messages.error(request, 'Term not found.')
        return redirect('exam:terms')

    if action == 'result_calc' and request.method == 'POST':
        term_id = request.POST.get('term_id')
        try:
            term = SchoolTerm.objects.get(id=term_id, school=school)
        except SchoolTerm.DoesNotExist:
            messages.error(request, 'Term not found.')
            return redirect('exam:terms')

        # Build calculation dict for active terms up to and including this one
        calc_terms = SchoolTerm.objects.filter(
            school=school, year=current_session, active=True, id__lte=term_id
        ).order_by('id')

        term_mgmt = {}
        for t in calc_terms:
            val = request.POST.get(str(t.id), '100')
            try:
                term_mgmt[str(t.id)] = int(val)
            except (ValueError, TypeError):
                term_mgmt[str(t.id)] = 100

        import json as _json
        rm, created = ResultManagement.objects.update_or_create(
            school=school, year=current_session, school_term=term,
            defaults={'term_calculation': _json.dumps(term_mgmt)}
        )
        messages.success(request, 'Result calculation updated for ' + term.term_name + '.')
        return redirect(f"{reverse('exam:terms')}?action=result_calc")

    if change_name and term_name:
        ctx = _nav_context(request)
        ctx.update({
            'school': school,
            'branchuser': branchuser,
            'current_session': current_session,
            'is_terms': True,
            'action': action,
            'change_name': True,
            'term_name': term_name,
            'term_status': term_status,
        })
        return render(request, 'exam/terms_list.html', ctx)

    exam_terms = SchoolTerm.objects.filter(school=school).order_by('id') if school else []

    # Fetch saved result calculations for all terms
    saved_calculations = {}
    if school:
        rm_qs = ResultManagement.objects.filter(school=school, year=current_session)
        for rm in rm_qs:
            try:
                saved_calculations[rm.school_term_id] = _json.loads(rm.term_calculation)
            except Exception:
                pass

    ctx = _nav_context(request)
    ctx.update({
        'exam_terms': exam_terms,
        'school': school,
        'branchuser': branchuser,
        'current_session': current_session,
        'is_terms': True,
        'action': action,
        'term_status': term_status,
        'saved_calculations': saved_calculations,
    })
    return render(request, 'exam/terms_list.html', ctx)


# ── Full Marks ───────────────────────────────────────────────────────────────

@login_required
def fullmarks(request):
    from sms.models import SchoolGrade
    from exam.models import SchoolTerm

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    current_session = get_current_session()

    exam_types = SchoolTerm.objects.filter(school=school, year=current_session, active=True)
    grades = SchoolGrade.objects.filter(school=school, active=True).order_by('grade_weight')

    ctx = _nav_context(request)
    ctx.update({
        'grades': grades,
        'school': school,
        'exam_types': exam_types,
        'edusession': current_session,
        'branchuser': branchuser,
        'is_exam_fullmarks': True,
    })
    return render(request, 'exam/fullmarks.html', ctx)


@login_required
def addfullmarks(request, grade, term):
    from sms.models import SchoolGrade, Subject
    from exam.models import SchoolTerm, GradeFullMarks

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    current_session = get_current_session()
    exam_term = SchoolTerm.objects.get(id=term)
    grade_obj = SchoolGrade.objects.get(id=grade)

    subjects = Subject.objects.filter(branch=school, grade=grade_obj, status=True).order_by('id')

    if request.method == 'POST':
        for subject in subjects:
            sid = str(subject.id)
            GradeFullMarks.objects.update_or_create(
                session=current_session, school=school, grade=grade_obj,
                term=exam_term, subject=subject,
                defaults={
                    'th_fm': request.POST.get(sid + '_th_full') or 0,
                    'pr_fm': request.POST.get(sid + '_pr_full') or 0,
                    'th_pm': request.POST.get(sid + '_th_pass') or 0,
                    'pr_pm': request.POST.get(sid + '_pr_pass') or 0,
                }
            )
        messages.success(request, 'Full marks saved.')
        return redirect(request.path)

    subjects_with_marks = GradeFullMarks.objects.filter(
        session=current_session, school=school, grade=grade_obj, term=exam_term
    )
    gs = subjects_with_marks.exists()

    ctx = _nav_context(request)
    ctx.update({
        'grade': grade_obj,
        'school': school,
        'exam_term': exam_term,
        'edusession': current_session,
        'subjects': subjects_with_marks if gs else subjects,
        'gs': gs,
        'branchuser': branchuser,
        'is_exam_fullmarks': True,
    })
    return render(request, 'exam/addfullmarks.html', ctx)


@login_required
def addfullmarksedit(request, grade, term):
    from sms.models import SchoolGrade, Subject
    from exam.models import SchoolTerm, GradeFullMarks

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    current_session = get_current_session()
    exam_term = SchoolTerm.objects.get(id=term)
    grade_obj = SchoolGrade.objects.get(id=grade)

    subjects = Subject.objects.filter(branch=school, grade=grade_obj, status=True).order_by('id')

    if request.method == 'POST':
        for subject in subjects:
            sid = str(subject.id)
            GradeFullMarks.objects.update_or_create(
                session=current_session, school=school, grade=grade_obj,
                term=exam_term, subject=subject,
                defaults={
                    'th_fm': request.POST.get(sid + '_th_full') or 0,
                    'pr_fm': request.POST.get(sid + '_pr_full') or 0,
                    'th_pm': request.POST.get(sid + '_th_pass') or 0,
                    'pr_pm': request.POST.get(sid + '_pr_pass') or 0,
                }
            )
        messages.success(request, 'Full marks updated.')
        return redirect('exam:edit_full_marks', grade=grade_obj.id, term=exam_term.id)

    ctx = _nav_context(request)
    ctx.update({
        'grade': grade_obj,
        'school': school,
        'exam_term': exam_term,
        'edusession': current_session,
        'subjects': subjects,
        'gs': True,
        'branchuser': branchuser,
        'is_exam_fullmarks': True,
    })
    return render(request, 'exam/addfullmarksedit.html', ctx)


# ── Subject-wise Marks ────────────────────────────────────────────────────────

@login_required
def subjectwisemarks(request):
    """Selection form — pick term, grade, section, subject."""
    from sms.models import SchoolGrade, Section
    from exam.models import SchoolTerm
    import json as _json

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    current_session = get_current_session()

    exam_types = SchoolTerm.objects.filter(school=school, year=current_session, active=True)
    grades = SchoolGrade.objects.filter(school=school, active=True).order_by('grade_weight')

    # Build section_list JSON for dynamic section dropdown
    section_list = {}
    for g in grades:
        section_list[str(g.id)] = {
            str(s.id): s.section
            for s in Section.objects.filter(grade=g)
        }
    section_list_json = _json.dumps(section_list)

    ctx = _nav_context(request)
    ctx.update({
        'exam_types': exam_types, 'grades': grades, 'school': school,
        'branchuser': branchuser, 'this_year': current_session.year if current_session else '',
        'section_list': section_list_json, 'is_exam_subject': True,
    })

    if request.method == 'POST':
        term_id = request.POST.get('term')
        grade_id = request.POST.get('grade')
        section_id = request.POST.get('section')
        order = request.POST.get('order', '1')

        if not grade_id:
            messages.error(request, 'Please select a grade.')
        else:
            # Build subject list for the selected grade
            from sms.models import Subject
            try:
                selected_grade = SchoolGrade.objects.get(id=grade_id)
                subjects = Subject.objects.filter(branch=school, grade=selected_grade, status=True).order_by('id')
                # Also get sections for this grade for server-side rendering
                sections_for_grade = {
                    str(s.id): s.section
                    for s in Section.objects.filter(grade=selected_grade)
                }
                ctx.update({
                    'selected_grade': selected_grade, 'term_id': term_id,
                    'grade_id': grade_id, 'section_id': section_id, 'order': order,
                    'subjects': subjects,
                    'sections_for_grade': sections_for_grade,
                })
            except SchoolGrade.DoesNotExist:
                messages.error(request, 'Invalid grade selected.')

    return render(request, 'exam/subjectwisemarks.html', ctx)


@login_required
def subject_wise_marks_entry(request):
    """Actual marks entry form — exam app implementation."""
    from sms.models import SchoolGrade, Section, StudentSession, Subject, MarkObtained
    from exam.models import SchoolTerm

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    current_session = get_current_session()

    if request.method == 'POST':
        term_id = request.POST.get('term')
        grade_id = request.POST.get('grade')
        section_id = request.POST.get('section')
        subject_id = request.POST.get('subject')

        try:
            term = SchoolTerm.objects.get(id=term_id)
            grade = SchoolGrade.objects.get(id=grade_id)
            section = Section.objects.get(id=section_id, session=current_session)
            subject = Subject.objects.get(id=subject_id)
        except (SchoolTerm.DoesNotExist, SchoolGrade.DoesNotExist, Section.DoesNotExist, Subject.DoesNotExist):
            return HttpResponse("Invalid selection.")

        students = StudentSession.objects.filter(
            grade=grade, session=current_session, section=section, status=True
        ).select_related('student').order_by('roll_no')

        # Process marks submission
        for student in students:
            th_mo = request.POST.get(f'{student.student_id}_th_mo', '0')
            pr_mo = request.POST.get(f'{student.student_id}_pr_mo', '0')
            try:
                th_mo = int(th_mo) if th_mo else 0
            except ValueError:
                th_mo = 0
            try:
                pr_mo = int(pr_mo) if pr_mo else 0
            except ValueError:
                pr_mo = 0

            MarkObtained.objects.update_or_create(
                student=student.student,
                session=current_session,
                grade=grade,
                term=term,
                subject=subject,
                defaults={
                    'th_mo': th_mo,
                    'pr_mo': pr_mo,
                    'school': school,
                }
            )

        messages.success(request, 'Marks saved successfully.')
        return redirect('exam:subject_wise_marks')

    # GET - show selection form
    exam_types = SchoolTerm.objects.filter(school=school, active=True)
    grades = SchoolGrade.objects.filter(school=school, active=True).order_by('grade_weight')

    ctx = _nav_context(request)
    ctx.update({
        'exam_types': exam_types, 'grades': grades, 'school': school,
        'branchuser': branchuser, 'is_exam_subject': True,
    })
    return render(request, 'exam/subjectwisemarks.html', ctx)


# ── Result Management ────────────────────────────────────────────────────────

@login_required
def resultmanagement(request):
    from sms.models import SchoolGrade, GradeLevel
    from exam.models import (
        SchoolTerm, SchoolResultType, LiveResult, ResultManagement,
        GradeResultConfig,
    )

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    current_session = get_current_session()
    grades = SchoolGrade.objects.filter(school=school, active=True).order_by('id')
    exam_types = SchoolTerm.objects.filter(school=school)

    live_result_obj = LiveResult.objects.filter(school=school).first()
    live_result_status = live_result_obj.status if live_result_obj else False
    live_calc_type = getattr(live_result_obj, 'calculation_type', 'legacy') if live_result_obj else 'legacy'

    if request.method == 'POST':
        submittype = request.POST.get('submittype')
        if submittype == 'resulttype':
            percent_or_grade = request.POST.get('percentorgrade')
            result_type = 1 if percent_or_grade == 'percent' else 2
            if not SchoolResultType.objects.filter(school=school, session=current_session).exists():
                SchoolResultType.objects.create(school=school, session=current_session, result_type=result_type)
        elif submittype == 'termandgrades':
            examtype = request.POST.get('examtype')
            livestatus = request.POST.get('publishresultswitch') == 'on'
            checks = _json.dumps([int(i) for i in request.POST.getlist('checks[]')])
            LiveResult.objects.update_or_create(
                school=school,
                defaults={'term': examtype, 'grade_list': checks, 'status': livestatus}
            )
            live_result_status = livestatus
        elif submittype == 'gradeconfig':
            grade_id = request.POST.get('grade_id')
            grading_type = int(request.POST.get('grading_type', 0))
            ledger_type = int(request.POST.get('ledger_type', 1))
            calculation_type = request.POST.get('calculation_type', 'legacy')
            if grade_id:
                try:
                    grade_id_int = int(grade_id)
                except (ValueError, TypeError):
                    grade_id_int = None
                if grade_id_int:
                    gc = GradeResultConfig.objects.filter(
                        school=school, year=current_session, grade_id=grade_id_int
                    ).first()
                    if gc and gc.assessment_source == 'cas':
                        messages.warning(request, f'Cannot edit {gc.grade.grade_name}. It uses CAS.')
                    elif gc:
                        gc.grading_type = grading_type
                        gc.ledger_type = ledger_type
                        gc.calculation_type = calculation_type
                        gc.save()
                        messages.success(request, f'{gc.grade.grade_name} updated.')
                    else:
                        GradeResultConfig.objects.create(
                            school=school,
                            year=current_session,
                            grade_id=grade_id_int,
                            assessment_source='exam',
                            grading_type=grading_type,
                            ledger_type=ledger_type,
                            calculation_type=calculation_type,
                        )
                        messages.success(request, f'Grade {grade_id_int} configured.')
        elif submittype == 'enable_cas':
            cas_grade_ids = request.POST.getlist('cas_grade_ids[]')
            # First, set all grades to exam (remove CAS)
            GradeResultConfig.objects.filter(
                school=school, year=current_session, assessment_source='cas'
            ).update(assessment_source='exam')
            # Then set selected grades to CAS
            updated_count = 0
            for grade_id in cas_grade_ids:
                try:
                    grade_id_int = int(grade_id)
                except (ValueError, TypeError):
                    continue
                gc = GradeResultConfig.objects.filter(
                    school=school, year=current_session, grade_id=grade_id_int
                ).first()
                if gc:
                    gc.assessment_source = 'cas'
                    gc.save()
                else:
                    GradeResultConfig.objects.create(
                        school=school,
                        year=current_session,
                        grade_id=grade_id_int,
                        assessment_source='cas',
                        grading_type=0,
                        ledger_type=1,
                        calculation_type='legacy',
                    )
                updated_count += 1
            messages.success(request, f'CAS enabled for {updated_count} grade(s).')
        elif submittype == 'bulk_exam_config':
            bulk_grading_type = int(request.POST.get('bulk_grading_type', 0))
            bulk_ledger_type = int(request.POST.get('bulk_ledger_type', 1))
            bulk_calculation_type = request.POST.get('bulk_calculation_type', 'legacy')
            grades_to_update = request.POST.getlist('bulk_grade_ids[]')
            updated_count = 0
            for grade_id in grades_to_update:
                try:
                    grade_id_int = int(grade_id)
                except (ValueError, TypeError):
                    continue
                gc = GradeResultConfig.objects.filter(
                    school=school, year=current_session, grade_id=grade_id_int
                ).first()
                if gc and gc.assessment_source == 'cas':
                    continue  # Skip CAS grades
                if gc:
                    gc.grading_type = bulk_grading_type
                    gc.ledger_type = bulk_ledger_type
                    gc.calculation_type = bulk_calculation_type
                    gc.save()
                else:
                    GradeResultConfig.objects.create(
                        school=school,
                        year=current_session,
                        grade_id=grade_id_int,
                        assessment_source='exam',
                        grading_type=bulk_grading_type,
                        ledger_type=bulk_ledger_type,
                        calculation_type=bulk_calculation_type,
                    )
                updated_count += 1
            messages.success(request, f'Bulk update applied to {updated_count} grade(s).')
        elif submittype == 'reset_grade_config':
            grade_id = request.POST.get('grade_id')
            if grade_id:
                try:
                    grade_id_int = int(grade_id)
                except (ValueError, TypeError):
                    grade_id_int = None
                if grade_id_int:
                    GradeResultConfig.objects.filter(
                        school=school, year=current_session, grade_id=grade_id_int
                    ).delete()
                    messages.success(request, f'Grade {grade_id_int} reset to default.')
        return redirect('exam:grade_result_config')

    schoolresulttype = SchoolResultType.objects.filter(school=school, session=current_session).first()
    sr = schoolresulttype

    rm_qs = ResultManagement.objects.filter(school=school, year=current_session)
    resultmanagement_exists = rm_qs.exists()

    gradelist = []
    if live_result_obj:
        try:
            gradelist = _json.loads(live_result_obj.grade_list)
        except Exception:
            gradelist = []

    # Determine which section is active based on URL name
    url_name = request.resolver_match.url_name if request.resolver_match else ''
    is_grade_config_page = url_name == 'grade_result_config'

    # Per-grade result configurations for this session (only needed on config page)
    grade_config_rows = []
    cas_grades = []
    exam_grades = []
    if is_grade_config_page:
        grade_configs = GradeResultConfig.objects.filter(
            school=school, year=current_session
        ).select_related('grade')
        grade_config_map = {gc.grade_id: gc for gc in grade_configs}
        for grade in grades:
            gc = grade_config_map.get(grade.id)
            row = {'grade': grade, 'config': gc}
            grade_config_rows.append(row)
            if gc and gc.assessment_source == 'cas':
                cas_grades.append(row)
            else:
                exam_grades.append(row)

    ctx = _nav_context(request)
    ctx.update({
        'grades': grades, 'gradelist': gradelist, 'branchuser': branchuser,
        'exam_types': exam_types, 'schoolresulttype': bool(schoolresulttype),
        'sr': sr, 'live_result_status': live_result_status,
        'resultmanagement': resultmanagement_exists,
        'rm': rm_qs, 'school': school, 'live_calc_type': live_calc_type,
        'current_session': current_session,
        'is_exam_result': 'manage',
        'is_grade_config': is_grade_config_page,
        'is_grade_config_page': is_grade_config_page,
        'grade_config_rows': grade_config_rows,
        'cas_grades': cas_grades,
        'exam_grades': exam_grades,
    })
    return render(request, 'exam/resultmanagement.html', ctx)


@login_required
def weighted_result_calculation(request):
    from sms.models import SchoolGrade, GradeLevel
    from exam.models import SchoolTerm, LiveResult, WeightedResultManagement
    import json as _json

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    current_session = get_current_session()
    grades = SchoolGrade.objects.filter(school=school, active=True).order_by('id')
    terms = SchoolTerm.objects.filter(school=school, year=current_session, active=True).order_by('id')

    live_result = LiveResult.objects.filter(school=school).first()
    live_calc_type = getattr(live_result, 'calculation_type', 'legacy') if live_result else 'legacy'

    wc_dic = {}
    for result in WeightedResultManagement.objects.filter(school=school, year=current_session):
        config = result.weight_config or {}
        if isinstance(config, str):
            try:
                config = _json.loads(config)
            except Exception:
                config = {}
        if 'weights' in config:
            weights_block = config.get('weights', {})
            config = weights_block.get(str(result.school_term_id), {}) or weights_block.get(result.school_term_id, {})
        wc_dic[str(result.school_term_id) + '_meta'] = {
            'plan': config.get('plan', 'direct'),
            'target_fm_th': config.get('target_fm_th', config.get('target_fm', 100)),
            'target_fm_pr': config.get('target_fm_pr', config.get('target_fm', 100)),
        }
        sources = config.get('sources', config)
        wc_dic[str(result.school_term_id)] = sources
        for term_key, value in sources.items():
            try:
                term_id = int(term_key)
            except Exception:
                continue
            if isinstance(value, (int, float)):
                wc_dic[str(result.school_term_id)][str(term_id)] = {'th_th': value, 'th_pr': value, 'pr_th': value, 'pr_pr': value}
            elif isinstance(value, dict):
                th_block = value.get('th', None)
                pr_block = value.get('pr', None)
                has_nested = isinstance(th_block, dict) or isinstance(pr_block, dict)
                if ('th' in value or 'pr' in value) and not has_nested:
                    wc_dic[str(result.school_term_id)][str(term_id)] = {'th_th': value.get('th', 0), 'th_pr': value.get('pr', 0), 'pr_th': value.get('th', 0), 'pr_pr': value.get('pr', 0)}
                else:
                    wc_dic[str(result.school_term_id)][str(term_id)] = {
                        'th_th': (th_block or {}).get('th', 0) if isinstance(th_block, dict) else 0,
                        'th_pr': (th_block or {}).get('pr', 0) if isinstance(th_block, dict) else 0,
                        'pr_th': (pr_block or {}).get('th', 0) if isinstance(pr_block, dict) else 0,
                        'pr_pr': (pr_block or {}).get('pr', 0) if isinstance(pr_block, dict) else 0,
                    }

    ctx = _nav_context(request)
    ctx.update({
        'grades': grades, 'branchuser': branchuser, 'school': school,
        'terms': terms, 'wc_dic': _json.dumps(wc_dic), 'live_calc_type': live_calc_type,
        'current_session': current_session,
        'is_exam_result': 'weighted',
    })
    return render(request, 'exam/weighted_result_calculation.html', ctx)


@login_required
def weighted_term_calculation(request):
    """Handle POST for weighted term calculation configuration."""
    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    if request.method != "POST":
        return HttpResponseRedirect('/exam/terms/weighted/')

    school = branchuser.school
    current_session = get_current_session()
    term_id = request.POST.get("term_id")

    try:
        term_id = int(term_id)
    except Exception:
        return HttpResponseRedirect('/exam/terms/weighted/')

    from exam.models import SchoolTerm
    from exam.models import WeightedResultManagement

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
    all_terms = SchoolTerm.objects.filter(year=current_session, school=school)
    for term in all_terms:
        if term.id > term_id:
            continue
        th_th = _safe_float(request.POST.get(f"th_th_{term.id}", 0))
        th_pr = _safe_float(request.POST.get(f"th_pr_{term.id}", 0))
        pr_th = _safe_float(request.POST.get(f"pr_th_{term.id}", 0))
        pr_pr = _safe_float(request.POST.get(f"pr_pr_{term.id}", 0))

        if th_th != 0 or th_pr != 0 or pr_th != 0 or pr_pr != 0:
            sources[str(term.id)] = {
                "th": {"th": th_th, "pr": th_pr},
                "pr": {"th": pr_th, "pr": pr_pr},
            }

    config = {
        "sources": sources,
        "plan": global_plan,
        "target_fm_th": global_target_fm_th,
        "target_fm_pr": global_target_fm_pr
    }
    school_term = SchoolTerm.objects.get(id=term_id)
    WeightedResultManagement.objects.update_or_create(
        year=current_session,
        school=school,
        school_term=school_term,
        defaults={"weight_config": config},
    )

    return HttpResponseRedirect('/exam/terms/weighted/')


@login_required
def activate_weighted_calculation(request):
    """Toggle weighted calculation mode."""
    if request.method != "POST":
        return HttpResponseRedirect('/exam/terms/weighted/')

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    calc_type = request.POST.get("calculation_type", "legacy")

    LiveResult.objects.update_or_create(
        school=school,
        defaults={"calculation_type": calc_type}
    )

    return HttpResponseRedirect('/exam/terms/weighted/')


# ── Print / Grade Sheet ──────────────────────────────────────────────────────

@login_required
def printmarksform(request):
    """Marks input form - selection GET, on POST shows blank form for marks entry."""
    from sms.models import SchoolGrade, Section, StudentSession
    from exam.models import SchoolTerm
    import json as _json

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    current_session = get_current_session()

    if request.method == 'POST':
        term_id = request.POST.get('term')
        grade_id = request.POST.get('grade2')
        section_id = request.POST.get('section2')

        try:
            term_exam = SchoolTerm.objects.get(id=term_id)
            grade = SchoolGrade.objects.get(id=grade_id)
            section = Section.objects.get(id=section_id, session=current_session)
        except (SchoolTerm.DoesNotExist, SchoolGrade.DoesNotExist, Section.DoesNotExist):
            return HttpResponse("Invalid selection.")

        students = StudentSession.objects.filter(
            grade=grade, session=current_session, section=section, status=True
        ).select_related('student').order_by('roll_no')

        ctx = _nav_context(request)
        ctx.update({
            'school': school,
            'students': students,
            'count': students.count(),
            'term_exam': term_exam,
            'grade': grade,
            'section': section,
            'this_year': current_session.year if current_session else '',
        })
        return render(request, 'exam/printmarksform.html', ctx)

    exam_types = SchoolTerm.objects.filter(school=school, active=True)
    grades = SchoolGrade.objects.filter(school=school, active=True).order_by('grade_weight')
    section_list = {}
    for g in grades:
        section_list[str(g.id)] = {str(s.id): s.section for s in Section.objects.filter(grade=g)}

    ctx = _nav_context(request)
    ctx.update({
        'exam_types': exam_types, 'grades': grades, 'school': school,
        'branchuser': branchuser, 'this_year': current_session.year if current_session else '',
        'section_list': _json.dumps(section_list),
        'is_exam_print': 'marks_form',
    })
    return render(request, 'exam/printmarksform.html', ctx)


def _get_grade_config(school, session, grade):
    """Get GradeResultConfig for a grade/session, or return defaults."""
    from exam.models import GradeResultConfig
    gc = GradeResultConfig.objects.filter(
        school=school, year=session, grade=grade
    ).first()
    if gc:
        return {
            'grading_type': gc.grading_type,
            'ledger_type': gc.ledger_type,
            'calculation_type': gc.calculation_type,
            'assessment_source': gc.assessment_source,
            'th_pass_type': gc.th_pass_type,
            'th_pass_value': gc.th_pass_value,
            'pr_pass_type': gc.pr_pass_type,
            'pr_pass_value': gc.pr_pass_value,
        }
    # Defaults from LiveResult / SchoolResultType
    from exam.models import LiveResult, SchoolResultType
    lr = LiveResult.objects.filter(school=school).first()
    sr = SchoolResultType.objects.filter(school=school, session=session).first()
    return {
        'grading_type': lr.calculation_type if lr and hasattr(lr, 'calculation_type') else 0,
        'ledger_type': 1,
        'calculation_type': 'legacy',
        'assessment_source': 'exam',
        'th_pass_type': 'percentage',
        'th_pass_value': 35.0,
        'pr_pass_type': 'percentage',
        'pr_pass_value': 35.0,
    }


@login_required
def marksgradesheet(request):
    """Grade sheet - selection form GET, on POST shows calculated results."""
    from sms.models import SchoolGrade, EduSession, Section, StudentSession, Subject
    from exam.models import SchoolTerm, LiveResult
    import json as _json

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    current_session = get_current_session()
    edusession_all = EduSession.objects.all().order_by('-year')
    grades = SchoolGrade.objects.filter(school=school, active=True).order_by('id')
    exam_types = SchoolTerm.objects.filter(school=school, active=True)

    section_list = {}
    for session in edusession_all:
        sid = str(session.id)
        section_list[sid] = {}
        for g in grades:
            section_list[sid][str(g.id)] = {str(s.id): s.section for s in Section.objects.filter(grade=g, session=session)}

    term_dict = {}
    for term in exam_types:
        year_id = str(term.year.id)
        if year_id not in term_dict:
            term_dict[year_id] = []
        term_dict[year_id].append({'id': term.id, 'name': f"{term.term_name.upper()} {term.year.year}"})

    live_result = LiveResult.objects.filter(school=school).first()
    live_calc_type = getattr(live_result, 'calculation_type', 'legacy') if live_result else 'legacy'

    if request.method == 'POST':
        edusession_id = request.POST.get('edusession')
        term_id = request.POST.get('term')
        grade_id = request.POST.get('grade2')
        section_id = request.POST.get('section2')
        printtype = int(request.POST.get('printtype', 1))  # 1=detail, 2=summary

        try:
            session = EduSession.objects.get(id=edusession_id)
            term = SchoolTerm.objects.get(id=term_id)
            grade = SchoolGrade.objects.get(id=grade_id)
        except (EduSession.DoesNotExist, SchoolTerm.DoesNotExist, SchoolGrade.DoesNotExist):
            return HttpResponse("Invalid selection.")

        if section_id and int(section_id) > 0:
            try:
                section = Section.objects.get(id=section_id)
            except Section.DoesNotExist:
                section = None
        else:
            section = None

        # Get grading config
        config = _get_grade_config(school, session, grade)

        # Get students
        students_qs = StudentSession.objects.filter(
            session=session, grade=grade, status=True
        )
        if section:
            students_qs = students_qs.filter(section=section)
        students = list(students_qs.select_related('student').order_by('roll_no'))

        # Calculate rank
        ranks = calculate_rank(school.id, session, grade, term, section, config=config)

        # Calculate results for each student
        student_data = []
        for student in students:
            result = calculate_student_result(school, session, grade, term, student, config)
            rank = ranks.get(student.student.reg_no, '-')
            student_data.append({
                'student': student,
                'rank': rank,
                **result,
            })

        # Get subjects for header
        subjects = Subject.objects.filter(
            branch=school, grade=grade, status=True
        ).order_by('id')

        # Get terminology
        from exam.models import SchoolTerminology
        try:
            terminology = SchoolTerminology.objects.get(school=school)
        except SchoolTerminology.DoesNotExist:
            terminology = None

        # Build term list (for single term, just the current term)
        term_list = [term.id]
        term_acronym = {term.id: term.name_in_short or term.term_name[:3]}
        no_of_terms = 1
        no_of_terms_range = range(no_of_terms)
        no_of_terms_marks_count = no_of_terms * 2  # TH + PR per term
        gpa_colspan = 4 + no_of_terms_marks_count  # S.N + Subject + TH/PR columns + Aggregate

        # Get attendance data
        from sms.models import Attendance
        attendance_data = {}
        for student in students:
            attendance = Attendance.objects.filter(
                reg_no=student.student.reg_no,
                session=session,
                grade=grade,
                term=term
            ).first()
            if attendance:
                attendance_data[student.student.reg_no] = {
                    'present': attendance.no_of_present_days,
                    'total': attendance.no_of_school_days,
                }

        # Add attendance to student_data
        for item in student_data:
            reg_no = item['student'].student.reg_no
            item['attendance'] = attendance_data.get(reg_no, {'present': 0, 'total': 0})

        # Build mo_dict for JavaScript (matching panel format)
        mo_dict = {}
        for item in student_data:
            for sub_id, sub_data in item['mo_dict'].items():
                for term_id in term_list:
                    prefix = f"{item['student'].student.reg_no}_{sub_id}_{term_id}"
                    mo_dict[f"{prefix}_th_grade"] = sub_data.get('th_grade', '-')
                    mo_dict[f"{prefix}_th_symbol"] = sub_data.get('th_symbol', '')
                    mo_dict[f"{prefix}_th_point"] = sub_data.get('th_point', '-')
                    mo_dict[f"{prefix}_pr_grade"] = sub_data.get('pr_grade', '-')
                    mo_dict[f"{prefix}_pr_symbol"] = sub_data.get('pr_symbol', '')
                    mo_dict[f"{prefix}_pr_point"] = sub_data.get('pr_point', '-')
                    mo_dict[f"{prefix}_total_grade"] = sub_data.get('total_grade', '-')
                    mo_dict[f"{prefix}_total_symbol"] = sub_data.get('total_symbol', '')
                    mo_dict[f"{prefix}_total_point"] = sub_data.get('total_point', '-')

        # Add GPA and remarks to mo_dict for each student (panel template expects these via JS)
        for item in student_data:
            reg_no = item['student'].student.reg_no
            mo_dict[f"{reg_no}_gpa"] = item.get('cgpa', 0)
            mo_dict[f"{reg_no}_remarks"] = item.get('remarks', '')

        # Get terminology
        from exam.models import SchoolTerminology
        try:
            terminology = SchoolTerminology.objects.get(school=school)
        except SchoolTerminology.DoesNotExist:
            terminology = None

        # Transform student_data into panel-compatible dict format (keyed by reg_no)
        pass_fail_filter = int(request.POST.get('pass_fail_filter', 0))
        panel_data = {}
        for item in student_data:
            student_session = item['student']
            student_obj = student_session.student
            reg_no = student_obj.reg_no
            attendance = item.get('attendance', {'present': 0, 'total': 0})
            fail_count = item.get('fail_count', 0)

            if pass_fail_filter == 0:
                show_data = True
            elif pass_fail_filter == 1:  # Pass Only
                show_data = fail_count == 0
            elif pass_fail_filter == 2:  # Fail Only
                show_data = fail_count > 0
            else:
                show_data = True

            panel_data[reg_no] = {
                'name': student_obj.name,
                'reg_no': reg_no,
                'grade': grade,
                'section': student_session.section,
                'session_detail': {'roll_no': student_session.roll_no},
                'student_detail': {
                    'dob': student_obj.dob,
                    'mothers_phone': student_obj.mothers_phone,
                    'fathers_phone': student_obj.fathers_phone,
                    'guardian_phone': student_obj.guardian_phone,
                    'fathers_name': student_obj.fathers_name,
                    'temporary_address': student_obj.temporary_address,
                },
                'no_of_school_days': attendance.get('total', 0),
                'no_of_present_days': attendance.get('present', 0),
                'show_data': show_data,
                'fail_count': fail_count,
                'cgpa': item.get('cgpa', 0),
                'percentage': item.get('percentage', 0),
                'total_fm': item.get('total_fm', 0),
                'total_mo': item.get('total_mo', 0),
                'overall_grade': item.get('overall_grade', ''),
                'overall_symbol': item.get('overall_symbol', ''),
                'remarks': item.get('remarks', ''),
            }

        # Get logo URL and slogan
        logo = school.logo.url if school.logo else ''
        slogan = school.slogan or ''

        ctx = _nav_context(request)
        ctx.update({
            'school': school,
            'term': term,
            'year': term.year,
            'data': panel_data,
            'grade': grade,
            'section': section,
            'subjects': subjects,
            'printtype': printtype,
            'config': config,
            'is_exam_print': 'gradesheet',
            # Panel-compatible variables
            'terminology': terminology,
            'term_list': term_list,
            'term_acronym': term_acronym,
            'no_of_terms': no_of_terms,
            'no_of_terms_range': no_of_terms_range,
            'no_of_terms_marks_count': no_of_terms_marks_count,
            'gpa_colspan': gpa_colspan,
            'mo_dict': _json.dumps(mo_dict),
            'the_space': range(0),  # Empty for single term
            'slogan': slogan,
            'logo': logo,
        })

        if printtype == 2:
            return render(request, 'exam/gradesheet_summary.html', ctx)
        else:
            # Select template based on grading_type (result_type)
            grading_type = config.get('grading_type', 0)
            if grading_type == 1:
                template_name = 'exam/gradesheet_nongraded.html'
            elif grading_type == 2:
                template_name = 'exam/gradesheet_newgrading.html'
            else:
                template_name = 'exam/gradesheet_legacy.html'
            return render(request, template_name, ctx)

    ctx = _nav_context(request)
    ctx.update({
        'edusession': edusession_all, 'current_session': current_session,
        'exam_types': exam_types, 'section_list': _json.dumps(section_list),
        'term_list': _json.dumps(term_dict), 'school': school, 'grades': grades,
        'branchuser': branchuser, 'live_calc_type': live_calc_type,
        'is_exam_print': 'gradesheet',
    })
    return render(request, 'exam/marksgradesheet.html', ctx)


@login_required
def print_grade_ledger_exam(request):
    """Grade ledger - selection form GET, on POST shows multi-term ledger."""
    from sms.models import SchoolGrade, EduSession, Section, StudentSession
    from exam.models import SchoolTerm, LiveResult
    import json as _json

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    current_session = get_current_session()
    edusession_all = EduSession.objects.all().order_by('-year')
    grades = SchoolGrade.objects.filter(school=school, active=True).order_by('id')
    exam_types = SchoolTerm.objects.filter(school=school, active=True)

    section_list = {}
    for session in edusession_all:
        sid = str(session.id)
        section_list[sid] = {}
        for g in grades:
            section_list[sid][str(g.id)] = {str(s.id): s.section for s in Section.objects.filter(grade=g, session=session)}

    term_dict = {}
    for term in exam_types:
        year_id = str(term.year.id)
        if year_id not in term_dict:
            term_dict[year_id] = []
        term_dict[year_id].append({'id': term.id, 'name': f"{term.term_name.upper()} {term.year.year}"})

    live_result = LiveResult.objects.filter(school=school).first()
    live_calc_type = getattr(live_result, 'calculation_type', 'legacy') if live_result else 'legacy'

    if request.method == 'POST':
        edusession_id = request.POST.get('edusession')
        term_id = request.POST.get('term')
        grade_id = request.POST.get('grade2')
        section_id = request.POST.get('section2')
        printtype = int(request.POST.get('printtype', 1))
        data_filter = int(request.POST.get('filter', 0))  # 0=all, 1=pass, 2=fail
        data_order = int(request.POST.get('data_order', 1))
        grading_type = int(request.POST.get('grading_type', 0))
        rank_by = request.POST.get('rank_by', 'total')
        calculation_type = request.POST.get('calculation_type', 'legacy')
        export = request.POST.get('export')

        from exam.models import ResultManagement

        try:
            session = EduSession.objects.get(id=edusession_id)
            term = SchoolTerm.objects.get(id=term_id)
            grade = SchoolGrade.objects.get(id=grade_id)
        except (EduSession.DoesNotExist, SchoolTerm.DoesNotExist, SchoolGrade.DoesNotExist):
            return HttpResponse("Invalid selection.")

        if section_id and int(section_id) > 0:
            try:
                section = Section.objects.get(id=section_id)
            except Section.DoesNotExist:
                section = None
        else:
            section = None

        # Get grading config first (needed for calculate_rank)
        config = _get_grade_config(school, session, grade)
        # Override grading_type from POST if provided
        if grading_type in [0, 1, 2]:
            config['grading_type'] = grading_type
        # Override calculation_type
        config['calculation_type'] = calculation_type

        # Get term calculation for multi-term ledger
        try:
            term_calc = ResultManagement.objects.get(school=school, year=session, school_term=term)
            term_calc_data = _json.loads(term_calc.term_calculation)
        except (ResultManagement.DoesNotExist, _json.JSONDecodeError):
            term_calc_data = {}

        # Build term list from calculation
        term_list = []
        term_acronym = {}
        no_of_terms = 0
        for key, value in term_calc_data.items():
            if int(value) > 0:
                no_of_terms += 1
                try:
                    t = SchoolTerm.objects.get(id=key)
                    term_acronym[int(key)] = t.name_in_short or t.term_name[:3]
                    term_list.append(int(key))
                except SchoolTerm.DoesNotExist:
                    continue

        # Get students with ordering
        students_qs = StudentSession.objects.filter(session=session, grade=grade, status=True)
        if section:
            students_qs = students_qs.filter(section=section)
        
        if data_order == 1:
            students = list(students_qs.select_related('student').order_by('student__reg_no'))
        elif data_order == 2:
            students = list(students_qs.select_related('student').order_by('roll_no'))
        elif data_order == 3:
            ranks = calculate_rank(school.id, session, grade, term, section, rank_by=rank_by, config=config)
            students = list(students_qs.select_related('student'))
            students.sort(key=lambda s: ranks.get(s.student.reg_no, 9999))
        else:
            students = list(students_qs.select_related('student').order_by('roll_no'))

        # Get ranks for all students (for display)
        all_ranks = calculate_rank(school.id, session, grade, term, section, rank_by=rank_by, config=config)

        # Get subjects
        from sms.models import Subject
        subjects = Subject.objects.filter(
            session=session, branch=school, grade=grade, status=True
        ).order_by('id')

        # Calculate results for each term for each student
        student_data = []
        for student in students:
            student_terms = {}
            total_fm = 0
            total_mo = 0
            cgpa_sum = 0
            cgpa_count = 0
            any_fail = False
            for t_id in term_list:
                try:
                    t = SchoolTerm.objects.get(id=t_id)
                    result = calculate_student_result(school, session, grade, t, student, config)
                    student_terms[t_id] = {
                        'term': t,
                        'term_name': t.term_name,
                        'term_short': t.name_in_short,
                        **result,
                    }
                    total_fm += result['total_fm']
                    total_mo += result['total_mo']
                    cgpa_sum += result['cgpa']
                    cgpa_count += 1
                    if result['fail_count'] > 0:
                        any_fail = True
                except SchoolTerm.DoesNotExist:
                    continue

            avg_cgpa = round(cgpa_sum / cgpa_count, 2) if cgpa_count > 0 else 0
            percentage = round((total_mo / total_fm * 100), 2) if total_fm > 0 else 0
            if avg_cgpa >= 4.0:
                overall_grade, overall_symbol = "A", "+"
            elif avg_cgpa >= 3.6:
                overall_grade, overall_symbol = "A", " "
            elif avg_cgpa >= 3.2:
                overall_grade, overall_symbol = "B", "+"
            elif avg_cgpa >= 2.8:
                overall_grade, overall_symbol = "B", " "
            elif avg_cgpa >= 2.4:
                overall_grade, overall_symbol = "C", "+"
            elif avg_cgpa >= 2.0:
                overall_grade, overall_symbol = "C", " "
            elif avg_cgpa >= 1.6:
                overall_grade, overall_symbol = "D", " "
            else:
                overall_grade, overall_symbol = "NG", ""

            student_data.append({
                'student': student,
                'rank': all_ranks.get(student.student.reg_no, '-'),
                'terms': student_terms,
                'totals': {
                    'total_fm': total_fm,
                    'total_mo': total_mo,
                    'percentage': percentage,
                    'cgpa': avg_cgpa,
                    'overall_grade': overall_grade,
                    'overall_symbol': overall_symbol,
                    'any_fail': any_fail,
                },
            })

        # Apply filter
        if data_filter == 1:  # Pass only
            student_data = [s for s in student_data if not s['totals']['any_fail']]
        elif data_filter == 2:  # Fail only
            student_data = [s for s in student_data if s['totals']['any_fail']]

        ctx = _nav_context(request)
        ctx.update({
            'school': school,
            'term': term,
            'grade': grade,
            'section': section,
            'subjects': subjects,
            'term_list': term_list,
            'term_acronym': term_acronym,
            'no_of_terms': no_of_terms,
            'student_data': student_data,
            'config': config,
            'data_filter': data_filter,
            'data_order': data_order,
            'grading_type': config['grading_type'],
            'is_exam_print': 'ledger',
        })

        if term.final_term:
            return render(request, 'exam/grade_ledger_final.html', ctx)
        else:
            return render(request, 'exam/grade_ledger.html', ctx)

    ctx = _nav_context(request)
    ctx.update({
        'edusession': edusession_all, 'current_session': current_session,
        'exam_types': exam_types, 'section_list': _json.dumps(section_list),
        'term_list': _json.dumps(term_dict), 'school': school, 'grades': grades,
        'branchuser': branchuser, 'live_calc_type': live_calc_type,
        'is_exam_print': 'ledger',
    })
    return render(request, 'exam/print_grade_ledger.html', ctx)


# Additional legacy redirect helper for a mis‑named URL.
    return response


@login_required
def printgradesheetnow2079(request):
    """Legacy 2079 grade sheet - delegates to new implementation."""
    return marksgradesheet(request)


# ── Print Ledger (exam app replica of panel/print/ledger/) ──────────────────

@login_required
def print_ledger(request):
    """Print Ledger form — GET shows selection form."""
    return HttpResponse("PRINT_LEDGER_VIEW_CALLED")

    school = branchuser.school
    current_session = get_current_session()
    edusession_all = EduSession.objects.all().order_by('-year')
    grades = SchoolGrade.objects.filter(school=school, active=True).order_by('id')
    exam_types = SchoolTerm.objects.filter(school=school, active=True)

    section_list = {}
    for session in edusession_all:
        sid = str(session.id)
        section_list[sid] = {}
        for g in grades:
            section_list[sid][str(g.id)] = {str(s.id): s.section for s in Section.objects.filter(grade=g, session=session)}

    term_dict = {}
    for term in exam_types:
        year_id = str(term.year.id)
        if year_id not in term_dict:
            term_dict[year_id] = []
        term_dict[year_id].append({'id': term.id, 'name': f"{term.term_name.upper()} {term.year.year}"})

    ctx = _nav_context(request)
    ctx.update({
        'edusession': edusession_all, 'current_session': current_session,
        'exam_types': exam_types, 'section_list': _json.dumps(section_list),
        'term_list': _json.dumps(term_dict), 'school': school, 'grades': grades,
        'branchuser': branchuser,
    })
    from django.template import loader, Context
    import os
    template_path = os.path.join(settings.BASE_DIR, 'exam', 'templates', 'exam', 'printledger.html')
    with open(template_path, 'r') as f:
        template_source = f.read()
    tmpl = loader.Template(template_source)
    rendered = tmpl.render(Context(ctx))
    return HttpResponse(rendered)


@login_required
def print_ledger_preview(request):
    """Print Ledger Preview — POST shows calculated marks preview."""
    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school

    if request.method != 'POST':
        return HttpResponseRedirect('/exam/')

    edusession_id = request.POST.get('edusession')
    term_id = request.POST.get('term')
    grade_id = request.POST.get('grade')
    section_id = request.POST.get('section')
    ledgermode = request.POST.get('ledgermode', '1')
    order = request.POST.get('order', '1')

    from sms.models import EduSession, SchoolTerm, SchoolGrade, Section, Subject, StudentSession

    try:
        session = EduSession.objects.get(id=edusession_id)
        term = SchoolTerm.objects.get(id=term_id)
        grade = SchoolGrade.objects.get(id=grade_id)
    except (EduSession.DoesNotExist, SchoolTerm.DoesNotExist, SchoolGrade.DoesNotExist):
        return HttpResponse("Invalid selection.")

    if section_id and str(section_id).strip() not in ('', '0'):
        try:
            section = Section.objects.get(id=section_id)
        except Section.DoesNotExist:
            section = None
    else:
        section = None

    subjects = Subject.objects.filter(
        session=session, branch=school, grade=grade, status=True
    ).order_by('id')

    from exam.func import _parse_weighted_term_config
    from exam.models import WeightedResultManagement, GradeFullMarks
    from sms.models import Subject, StudentSession, MarkObtained
    normalized_wconfig, global_wsettings = {}, {}
    source_terms = []
    if ledgermode in ['2', '3']:
        weighted_config_obj = WeightedResultManagement.objects.filter(
            school=school, year=session, school_term=term
        ).first()
        if weighted_config_obj:
            normalized_wconfig, global_wsettings = _parse_weighted_term_config(
                weighted_config_obj.weight_config, term.id, include_current=True
            )
            source_term_ids = list(normalized_wconfig.keys())
            term_objects = {str(t.id): t for t in SchoolTerm.objects.filter(id__in=source_term_ids)}
            source_terms = [term_objects[tid] for tid in source_term_ids if tid in term_objects]
            if not source_terms:
                ledgermode = '1'
        else:
            ledgermode = '1'

    base_qs_kwargs = {'grade': grade, 'session': session, 'status': True}
    if section:
        base_qs_kwargs['section'] = section

    try:
        order = int(order or '1')
    except:
        order = 1

    if order == 1:
        students = StudentSession.objects.filter(**base_qs_kwargs).order_by('student__reg_no')
    else:
        students = StudentSession.objects.filter(**base_qs_kwargs).order_by('roll_no')

    # Pre-fetch marks for source terms
    all_marks_map = {}
    source_fm_map = {}
    if ledgermode in ['2', '3']:
        source_term_ids = [t.id for t in source_terms]
        marks_qs = MarkObtained.objects.filter(
            school=school, session=session, grade=grade, term_id__in=source_term_ids
        )
        for m in marks_qs:
            all_marks_map[(m.student_id, m.term_id, m.subject_id)] = (m.th_mo or 0, m.pr_mo or 0)
        source_fm_qs = GradeFullMarks.objects.filter(
            school=school, session=session, grade=grade, term_id__in=source_term_ids
        )
        source_fm_map = {(fm.term_id, fm.subject_id): (fm.th_fm or 0, fm.pr_fm or 0) for fm in source_fm_qs}
    else:
        marks_qs = MarkObtained.objects.filter(
            school=school, session=session, grade=grade, term=term
        )
        for m in marks_qs:
            all_marks_map[(m.student_id, term.id, m.subject_id)] = (m.th_mo or 0, m.pr_mo or 0)

    # Build student data
    this_term_fm_cache = {fm.subject_id: fm for fm in GradeFullMarks.objects.filter(
        school=school, session=session, grade=grade, term=term
    )}

    student_data_list = []
    for student in students:
        std_entry = {
            'reg_no': student.student.reg_no,
            'name': student.student.name,
            'roll_no': student.roll_no,
            'breakdown_terms': [],
        }

        if ledgermode == '1':
            term_entry = {'term_label': term.term_name, 'subjects': []}
            for sub in subjects:
                th_obt, pr_obt = all_marks_map.get((student.student_id, term.id, sub.id), (0, 0))
                fm = this_term_fm_cache.get(sub.id)
                term_entry['subjects'].append({
                    'th_val': int(th_obt) if th_obt == int(th_obt) else round(th_obt, 2),
                    'pr_val': int(pr_obt) if pr_obt == int(pr_obt) else round(pr_obt, 2),
                    'th_max': fm.th_fm if fm else 0,
                    'pr_max': fm.pr_fm if fm else 0,
                })
            std_entry['breakdown_terms'].append(term_entry)
        else:
            student_subject_totals = {sub.id: {'th': 0, 'pr': 0} for sub in subjects}
            for src_term in source_terms:
                term_label = getattr(src_term, 'name_in_short', None) or src_term.term_name
                if ledgermode == '2':
                    term_label += ' (WGT)'
                term_entry = {'term_label': term_label, 'subjects': []}
                w_info = normalized_wconfig.get(str(src_term.id))
                for sub in subjects:
                    s_th, s_pr = all_marks_map.get((student.student_id, src_term.id, sub.id), (0, 0))
                    s_th_fm, s_pr_fm = source_fm_map.get((src_term.id, sub.id), (0, 0))
                    if ledgermode == '2' and w_info:
                        # Cross-mixing: TH gets contribution from both TH and PR
                        val_th = s_th * w_info.get('th_from_th', 0) + s_pr * w_info.get('th_from_pr', 0)
                        val_pr = s_th * w_info.get('pr_from_th', 0) + s_pr * w_info.get('pr_from_pr', 0)
                        # For scaling plan (if implemented in future)
                        if w_info.get('plan') == 'scaling':
                            # Note: scaling not fully implemented in breakdown view
                            pass
                    else:
                        val_th = s_th
                        val_pr = s_pr
                    student_subject_totals[sub.id]['th'] += val_th
                    student_subject_totals[sub.id]['pr'] += val_pr
                    # For breakdown display, show the weighted contribution
                    term_entry['subjects'].append({
                        'th_val': int(val_th) if val_th == int(val_th) else round(val_th, 2),
                        'pr_val': int(val_pr) if val_pr == int(val_pr) else round(val_pr, 2),
                        'th_max': s_th_fm,
                        'pr_max': s_pr_fm,
                    })
                std_entry['breakdown_terms'].append(term_entry)

            total_label = 'TOTAL'
            if ledgermode == '2':
                total_label += ' (WGT)'
            total_entry = {'term_label': total_label, 'subjects': [], 'is_total': True}
            for sub in subjects:
                t_th = student_subject_totals[sub.id]['th']
                t_pr = student_subject_totals[sub.id]['pr']
                total_entry['subjects'].append({
                    'th_val': int(t_th) if t_th == int(t_th) else round(t_th, 2),
                    'pr_val': int(t_pr) if t_pr == int(t_pr) else round(t_pr, 2),
                    'th_max': 0,
                    'pr_max': 0,
                })
            std_entry['breakdown_terms'].append(total_entry)

        student_data_list.append(std_entry)

    # Subject FM list for header reference
    subject_fm_list = []
    for sub in subjects:
        if ledgermode in ['2', '3']:
            th_max = 0
            pr_max = 0
            if ledgermode == '3':
                th_max = sum(source_fm_map.get((t.id, sub.id), (0, 0))[0] for t in source_terms)
                pr_max = sum(source_fm_map.get((t.id, sub.id), (0, 0))[1] for t in source_terms)
            else:
                th_max = 0
                pr_max = 0
                for t in source_terms:
                    w_info = normalized_wconfig.get(str(t.id), {})
                    s_th_fm, s_pr_fm = source_fm_map.get((t.id, sub.id), (0, 0))
                    # Cross-mixing for FM: TH gets contribution from both TH and PR FM
                    if w_info.get('plan') == 'scaling':
                        th_target = global_wsettings.get('target_fm_th', 100)
                        pr_target = global_wsettings.get('target_fm_pr', 100)
                        th_max += s_th_fm * w_info.get('th_from_th', 0) * (th_target / 100 if s_th_fm > 0 else 0)
                        th_max += s_pr_fm * w_info.get('th_from_pr', 0) * (pr_target / 100 if s_pr_fm > 0 else 0)
                        pr_max += s_th_fm * w_info.get('pr_from_th', 0) * (th_target / 100 if s_th_fm > 0 else 0)
                        pr_max += s_pr_fm * w_info.get('pr_from_pr', 0) * (pr_target / 100 if s_pr_fm > 0 else 0)
                    else:
                        th_max += s_th_fm * w_info.get('th_from_th', 0)
                        th_max += s_pr_fm * w_info.get('th_from_pr', 0)
                        pr_max += s_th_fm * w_info.get('pr_from_th', 0)
                        pr_max += s_pr_fm * w_info.get('pr_from_pr', 0)
        else:
            fm = this_term_fm_cache.get(sub.id)
            th_max = fm.th_fm if fm else 0
            pr_max = fm.pr_fm if fm else 0

        subject_fm_list.append({
            'name': sub.subject,
            'th_fm': int(th_max),
            'pr_fm': int(pr_max),
        })

    from exam.models import SchoolTerminology
    try:
        terminology = SchoolTerminology.objects.get(school=school)
    except SchoolTerminology.DoesNotExist:
        terminology = None

    ctx = _nav_context(request)
    ctx.update({
        'school': school, 'term': term, 'year': term.year,
        'student_data': student_data_list, 'grade': grade, 'section': section,
        'subjects': subjects, 'ledgermode': ledgermode, 'ledgertype': '2',
        'subject_fm_list': subject_fm_list,
        'terminology': terminology,
    })
    return render(request, 'exam/printledgerpreview.html', ctx)


@login_required
def print_ledger_now(request):
    """Print Ledger final output — POST renders detailed ledger."""
    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school

    if request.method != 'POST':
        return HttpResponseRedirect('/exam/')

    edusession_id = request.POST.get('edusession')
    term_id = request.POST.get('term')
    printtype = int(request.POST.get('printtype', 1))
    grade_id = request.POST.get('grade2', 0)
    section_id = request.POST.get('section2', 0)
    ledgermode = request.POST.get('ledgermode', '1')
    ledgertype = request.POST.get('ledgertype', '1')
    grading_type = int(request.POST.get('grading_type', '2'))
    data_filter = int(request.POST.get('filter', '0'))
    rank_by = request.POST.get('rank_by', 'total')

    if grade_id == 0 or grade_id is None or grade_id == '':
        return HttpResponse("Sorry! something went wrong. Please take care while submitting data.")

    grade = SchoolGrade.objects.get(id=grade_id)
    session = EduSession.objects.get(id=edusession_id)
    term = SchoolTerm.objects.get(id=term_id)

    weighted_config_obj = None
    if ledgermode in ['2', '3']:
        weighted_config_obj = WeightedResultManagement.objects.filter(
            school=school, year=session, school_term=term
        ).first()
        if not weighted_config_obj:
            ledgermode = '1'

    if int(section_id) > 0:
        section = Section.objects.get(id=section_id)
    else:
        section = False

    subjects = Subject.objects.filter(
        branch=school, grade=grade, session=session, status=True
    ).order_by('id')

    if section == False:
        students = StudentSession.objects.filter(grade=grade, session=session, status=True)
    else:
        students = StudentSession.objects.filter(grade=grade, section=section, session=session, status=True)

    source_terms = []
    normalized_wconfig = {}
    global_wsettings = {}
    if ledgermode in ['2', '3'] and weighted_config_obj:
        normalized_wconfig, global_wsettings = _parse_weighted_term_config(
            weighted_config_obj.weight_config, term.id, include_current=True
        )
        source_term_ids = list(normalized_wconfig.keys())
        term_objects = {str(t.id): t for t in SchoolTerm.objects.filter(id__in=source_term_ids)}
        source_terms = [term_objects[tid] for tid in source_term_ids if tid in term_objects]
    else:
        ledgermode = '1'
        source_terms = [term]

    for sub in subjects:
        sub.source_list = source_terms
        sub.source_count = len(source_terms)
        sub.source_count_x2 = len(source_terms) * 2

    # FM cache
    gfm_qs = GradeFullMarks.objects.filter(
        school=school, session=session, grade=grade, term=term
    )
    gfm_cache = {g.subject_id: g for g in gfm_qs}

    all_marks_map = {}
    source_fm_map = {}
    source_term_ids = [t.id for t in source_terms]
    marks_qs = MarkObtained.objects.filter(
        school=school, session=session, grade=grade,
        term_id__in=source_term_ids, subject_id__in=[s.id for s in subjects]
    )
    for m in marks_qs:
        all_marks_map[(m.student_id, m.term_id, m.subject_id)] = (m.th_mo or 0, m.pr_mo or 0)

    source_fm_qs = GradeFullMarks.objects.filter(
        school=school, session=session, grade=grade, term_id__in=source_term_ids
    )
    for fm in source_fm_qs:
        source_fm_map[(fm.term_id, fm.subject_id)] = (fm.th_fm or 0, fm.pr_fm or 0)

    subject_fm_data = {}
    for sub in subjects:
        if ledgermode == '1':
            gfm = gfm_cache.get(sub.id)
            th_max = gfm.th_fm if gfm else 0
            pr_max = gfm.pr_fm if gfm else 0
        elif ledgermode == '3':
            th_max = sum(source_fm_map.get((t.id, sub.id), (0, 0))[0] for t in source_terms)
            pr_max = sum(source_fm_map.get((t.id, sub.id), (0, 0))[1] for t in source_terms)
        else:
            th_max = 0
            pr_max = 0
            for t in source_terms:
                w_info = normalized_wconfig.get(str(t.id), {})
                s_th_fm, s_pr_fm = source_fm_map.get((t.id, sub.id), (0, 0))
                # Cross-mixing for FM: TH gets contribution from both TH and PR FM
                if w_info.get('plan') == 'scaling':
                    th_target = global_wsettings.get('target_fm_th', 100)
                    pr_target = global_wsettings.get('target_fm_pr', 100)
                    th_max += s_th_fm * w_info.get('th_from_th', 0) * (th_target / 100 if s_th_fm > 0 else 0)
                    th_max += s_pr_fm * w_info.get('th_from_pr', 0) * (pr_target / 100 if s_pr_fm > 0 else 0)
                    pr_max += s_th_fm * w_info.get('pr_from_th', 0) * (th_target / 100 if s_th_fm > 0 else 0)
                    pr_max += s_pr_fm * w_info.get('pr_from_pr', 0) * (pr_target / 100 if s_pr_fm > 0 else 0)
                else:
                    th_max += s_th_fm * w_info.get('th_from_th', 0)
                    th_max += s_pr_fm * w_info.get('th_from_pr', 0)
                    pr_max += s_th_fm * w_info.get('pr_from_th', 0)
                    pr_max += s_pr_fm * w_info.get('pr_from_pr', 0)
        subject_fm_data[sub.id] = {'th_max': th_max, 'pr_max': pr_max}

    subject_fm_list = []
    for sub in subjects:
        fm_info = subject_fm_data.get(sub.id, {'th_max': 0, 'pr_max': 0})
        subject_fm_list.append({
            'name': sub.subject,
            'th_fm': int(fm_info['th_max']),
            'pr_fm': int(fm_info['pr_max']),
            'th_pm': int(fm_info['th_max'] * 0.4) if (fm_info['th_max'] * 0.4) == int(fm_info['th_max'] * 0.4) else round(fm_info['th_max'] * 0.4, 2),
            'pr_pm': int(fm_info['pr_max'] * 0.4) if (fm_info['pr_max'] * 0.4) == int(fm_info['pr_max'] * 0.4) else round(fm_info['pr_max'] * 0.4, 2),
        })

    sn = 0
    data = {}
    from exam.func import get_percentage
    from exam.models import GradeResultConfig
    
    # Get grade config for pass thresholds
    grade_config = GradeResultConfig.objects.filter(
        school=school, year=session, grade=grade
    ).first()
    
    if grade_config:
        th_pass_type = grade_config.th_pass_type
        th_pass_value = float(grade_config.th_pass_value)
        pr_pass_type = grade_config.pr_pass_type
        pr_pass_value = float(grade_config.pr_pass_value)
    else:
        th_pass_type = 'percentage'
        th_pass_value = 35.0
        pr_pass_type = 'percentage'
        pr_pass_value = 35.0
    
    for student in students:
        sn += 1
        data[sn] = {}
        data[sn]['reg_no'] = student.student.reg_no
        data[sn]['name'] = student.student.name
        data[sn]['roll_no'] = student.roll_no
        data[sn]['section'] = student.section

        # Use exam's calculate_student_result for each subject
        # Map ledgermode to calculation_type: '1'=legacy, '2'=weighted, '3'=legacy, '4'=weighted
        calc_type_map = {'1': 'legacy', '2': 'weighted', '3': 'legacy', '4': 'weighted'}
        calculation_type = calc_type_map.get(ledgermode, 'legacy')
        
        config = {
            'grading_type': grading_type,
            'ledger_type': 2,
            'calculation_type': calculation_type,
            'assessment_source': 'exam',
            'th_pass_type': th_pass_type,
            'th_pass_value': th_pass_value,
            'pr_pass_type': pr_pass_type,
            'pr_pass_value': pr_pass_value,
        }
        result = calculate_student_result(school, session, grade, term, student, config)

        weighted_subjects_data = []
        for sub in subjects:
            m = result['mo_dict'].get(sub.id, {})
            weighted_subjects_data.append({
                'subject_name': sub.subject,
                'sources': [],  # Simplified for exam version
                'total_th': m.get('th_mo', 0),
                'total_pr': m.get('pr_mo', 0),
                'total_th_grade': m.get('th_grade', '-'),
                'total_th_grade_s': m.get('th_symbol', ''),
                'total_pr_grade': m.get('pr_grade', '-'),
                'total_pr_grade_s': m.get('pr_symbol', ''),
                'th_fail': m.get('th_fail', False),
                'pr_fail': m.get('pr_fail', False),
                'total_gp': m.get('total_point', 0),
            })
        data[sn]['weighted_subjects'] = weighted_subjects_data

        data[sn].update({
            'mo_th': result.get('total_th_mo', 0),
            'mo_pr': result.get('total_pr_mo', 0),
            'total': result.get('total_mo', 0),
            'gp': result.get('cgpa', 0),
            'subjects': result['mo_dict'],
        })

        # Pass/Fail detection - use pre-calculated results from calculate_student_result
        is_failed = False
        fail_count = 0
        for sub in subjects:
            sub_id = sub.id
            marks = data[sn]['subjects'].get(sub_id, {})
            # Use the th_fail and pr_fail flags calculated by calculate_student_result
            if marks.get('th_fail', False):
                is_failed = True
                fail_count += 1
            if marks.get('pr_fail', False):
                is_failed = True
                fail_count += 1

        data[sn]['is_failed'] = is_failed
        data[sn]['fail_count'] = fail_count
        data[sn]['rank'] = '-'

    # Apply filter
    if data_filter == 1:
        data = {k: v for k, v in data.items() if not v['is_failed']}
    elif data_filter == 2:
        data = {k: v for k, v in data.items() if v['is_failed']}

    from exam.models import SchoolTerminology
    try:
        terminology = SchoolTerminology.objects.get(school=school)
    except SchoolTerminology.DoesNotExist:
        terminology = None

    ctx = _nav_context(request)
    ctx.update({
        'school': school, 'term': term, 'year': term.year,
        'data': data, 'grade': grade, 'section': section,
        'subjects': subjects, 'subject_fm_list': subject_fm_list,
        'ledgermode': ledgermode, 'ledgertype': ledgertype,
        'terminology': terminology,
    })
    return render(request, 'exam/printledgernow_detailed.html', ctx)


# ── Entrance Card (exam app replica of panel/print/entrancecard/) ───────────

@login_required
def print_entrance_card(request):
    """Entrance Card form — GET shows selection, POST generates cards."""
    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    current_session = get_current_session()

    width = 55
    logo = school.logo.url if school.logo else ''

    grades = SchoolGrade.objects.filter(school=school, session=current_session)
    exam_types = SchoolTerm.objects.filter(school=school, year=current_session)

    if request.method == 'POST' or request.GET.get('term'):
        term = request.GET.get('term') or request.POST.get('term')
        whattype = request.GET.get('whattype') or request.POST.get('whattype')

        std_reg = {}
        count = 0
        school_grade = SchoolGrade.objects.filter(school=school, active=True).order_by('id')
        if school_grade:
            for sg in school_grade:
                student_in_session = StudentSession.objects.filter(
                    session=current_session, grade=sg, status=True
                ).order_by('section', 'roll_no', 'student')
                for sis in student_in_session:
                    count += 1
                    std_reg[sis.student.reg_no] = {
                        'reg_no': sis.student.reg_no,
                        'name': sis.student.name,
                        'grade': sg.grade_name if hasattr(sg, 'grade_name') else str(sg),
                        'section': sis.section.section if sis.section else '',
                        'roll_no': sis.roll_no,
                        'avatar': sis.avatar.url if sis.avatar else (sis.student.avatar.url if sis.student.avatar else None),
                    }

        term_exam = SchoolTerm.objects.get(id=term)

        if whattype == 'detail':
            ctx = _nav_context(request)
            ctx.update({
                'school': school, 'students': {}, 'count': count, 'term_exam': term_exam,
                'year': current_session.year, 'logo': logo, 'width': width,
                'blankcount': '12345678', 'std_reg': std_reg, 'whattype': whattype,
            })
            return render(request, 'exam/entrancecard_dict.html', ctx)
        elif whattype == 'blank':
            ctx = _nav_context(request)
            ctx.update({
                'school': school, 'term_exam': term_exam, 'year': current_session.year,
                'logo': logo, 'width': width, 'blankcount': '12345678',
                'std_reg': std_reg, 'whattype': whattype,
            })
            return render(request, 'exam/entrancecardblank.html', ctx)
        elif whattype == 'image':
            ctx = _nav_context(request)
            ctx.update({
                'school': school, 'students': {}, 'count': count, 'term_exam': term_exam,
                'year': current_session.year, 'logo': logo, 'width': width,
                'blankcount': '12345678', 'std_reg': std_reg, 'whattype': whattype,
            })
            return render(request, 'exam/entrancecard_dict.html', ctx)

    ctx = _nav_context(request)
    ctx.update({
        'grades': grades, 'school': school, 'exam_types': exam_types,
    })
    return render(request, 'exam/entrancecardbase.html', ctx)


# ── Settings ─────────────────────────────────────────────────────────────────

@login_required
def settings(request):
    """Settings landing page — links to Terminologies and Result Config."""
    from exam.models import SchoolTerminology

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    terminology, _ = SchoolTerminology.objects.get_or_create(school=school)

    ctx = _nav_context(request)
    ctx.update({
        'school': school, 'branchuser': branchuser,
        'terminology': terminology,
        'is_settings': True,
    })
    return render(request, 'exam/settings.html', ctx)


@login_required
def settings_terminologies(request):
    """Terminology settings — Theory/Practical labels used across the system."""
    from exam.models import SchoolTerminology

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    terminology, _ = SchoolTerminology.objects.get_or_create(school=school)

    if request.method == 'POST':
        terminology.theory_short = request.POST.get('theory_short', 'TH').strip() or 'TH'
        terminology.theory_long = request.POST.get('theory_long', 'Theory').strip() or 'Theory'
        terminology.practical_short = request.POST.get('practical_short', 'PR').strip() or 'PR'
        terminology.practical_long = request.POST.get('practical_long', 'Practical').strip() or 'Practical'
        terminology.save()
        messages.success(request, 'Terminology settings saved.')
        return redirect('exam:settings_terminologies')

    ctx = _nav_context(request)
    ctx.update({
        'school': school, 'branchuser': branchuser,
        'terminology': terminology,
        'is_settings_terminologies': True,
    })
    return render(request, 'exam/settings_terminologies.html', ctx)

# ----------------------------------------------------------------------
# Legacy redirect helpers – keep compatibility with old URLs used in previous
# versions of the system. The panel app has similar helpers; we provide the
# same pattern here for the exam app.
# ----------------------------------------------------------------------

def inputfullmarksredirector(request):
    """Redirect legacy "inputfullmarks" URL to the current full‑marks list.

    Historically the system used a separate endpoint for full‑marks input.
    Modern code consolidates this UI under the ``exam:full_marks`` view, which
    displays a list of existing full‑marks and options to add new ones. Since the
    legacy URL does not contain the ``grade`` and ``term`` parameters required by
    ``addfullmarks``, we redirect to the list view where the user can select the
    appropriate term/grade.
    """
    # ``redirect`` is already imported from django.shortcuts.
    if request.method == 'POST':
        grade = request.POST.get('grade')
        term = request.POST.get('term')
        if grade and term:
            return redirect('exam:add_full_marks', grade=grade, term=term)
    return redirect('exam:full_marks')

# ----------------------------------------------------------------------
# ── Unified Result Print (Raw Marks + Calculated) ────────────────────────────

@login_required
def print_result(request):
    """
    Unified result print view for admin.
    
    Supports two modes via GradeResultConfig:
    - Raw Marks: shows actual marks obtained per subject per term
    - Calculated: applies grading logic from result config
    
    Both modes support: Rank By, Order By, Filter, Export Excel
    """
    from sms.models import SchoolGrade, EduSession, Section, StudentSession, Subject, MarkObtained
    from exam.models import SchoolTerm, GradeResultConfig, LiveResult, SchoolResultType
    import json as _json

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    current_session = get_current_session()
    edusession_all = EduSession.objects.all().order_by('-year')
    grades = SchoolGrade.objects.filter(school=school, active=True).order_by('id')
    exam_types = SchoolTerm.objects.filter(school=school, active=True)

    section_list = {}
    for session in edusession_all:
        sid = str(session.id)
        section_list[sid] = {}
        for g in grades:
            section_list[sid][str(g.id)] = {str(s.id): s.section for s in Section.objects.filter(grade=g, session=session)}

    term_dict = {}
    for term in exam_types:
        year_id = str(term.year.id)
        if year_id not in term_dict:
            term_dict[year_id] = []
        term_dict[year_id].append({'id': term.id, 'name': f"{term.term_name.upper()} {term.year.year}"})

    live_result = LiveResult.objects.filter(school=school).first()
    live_calc_type = getattr(live_result, 'calculation_type', 'legacy') if live_result else 'legacy'

    if request.method == 'POST':
        edusession_id = request.POST.get('edusession')
        term_id = request.POST.get('term')
        grade_id = request.POST.get('grade2')
        section_id = request.POST.get('section2')
        printtype = int(request.POST.get('printtype', 1))  # 1=detail, 2=summary
        data_filter = int(request.POST.get('filter', 0))  # 0=all, 1=pass, 2=fail
        data_order = int(request.POST.get('data_order', 1))
        rank_by = request.POST.get('rank_by', 'total')
        mode = request.POST.get('mode', 'calculated')  # 'raw' or 'calculated'
        export = request.POST.get('export')

        try:
            session = EduSession.objects.get(id=edusession_id)
            term = SchoolTerm.objects.get(id=term_id)
            grade = SchoolGrade.objects.get(id=grade_id)
        except (EduSession.DoesNotExist, SchoolTerm.DoesNotExist, SchoolGrade.DoesNotExist):
            return HttpResponse("Invalid selection.")

        if section_id and int(section_id) > 0:
            try:
                section = Section.objects.get(id=section_id)
            except Section.DoesNotExist:
                section = None
        else:
            section = None

        # Get result config for this grade/session
        config_obj = GradeResultConfig.objects.filter(
            school=school, year=session, grade=grade
        ).first()
        
        if config_obj:
            config = {
                'grading_type': config_obj.grading_type,
                'ledger_type': config_obj.ledger_type,
                'calculation_type': config_obj.calculation_type,
                'assessment_source': config_obj.assessment_source,
            }
        else:
            # Fallback to school-wide defaults
            lr = LiveResult.objects.filter(school=school).first()
            sr = SchoolResultType.objects.filter(school=school, session=session).first()
            config = {
                'grading_type': getattr(lr, 'calculation_type', 0) if lr else 0,
                'ledger_type': 1,
                'calculation_type': 'legacy',
                'assessment_source': 'exam',
            }

        # Override from POST if provided (admin can override)
        if 'grading_type' in request.POST and request.POST.get('grading_type'):
            config['grading_type'] = int(request.POST.get('grading_type'))
        if 'ledger_type' in request.POST and request.POST.get('ledger_type'):
            config['ledger_type'] = int(request.POST.get('ledger_type'))
        if 'calculation_type' in request.POST and request.POST.get('calculation_type'):
            config['calculation_type'] = request.POST.get('calculation_type')

        # Get subjects
        subjects = Subject.objects.filter(
            session=session, branch=school, grade=grade, status=True
        ).order_by('id')

        # Get students
        students_qs = StudentSession.objects.filter(session=session, grade=grade, status=True)
        if section:
            students_qs = students_qs.filter(section=section)
        
        if data_order == 1:
            students = list(students_qs.select_related('student').order_by('student__reg_no'))
        elif data_order == 2:
            students = list(students_qs.select_related('student').order_by('roll_no'))
        elif data_order == 3:
            ranks = calculate_rank(school.id, session, grade, term, section, rank_by=rank_by, config=config)
            students = list(students_qs.select_related('student'))
            students.sort(key=lambda s: ranks.get(s.student.reg_no, 9999))
        else:
            students = list(students_qs.select_related('student').order_by('roll_no'))

        all_ranks = calculate_rank(school.id, session, grade, term, section, rank_by=rank_by, config=config)

        student_data = []
        for student in students:
            if mode == 'raw':
                # Raw marks - just get actual marks per subject
                mo_dict = {}
                total_th_mo = 0
                total_pr_mo = 0
                total_th_fm = 0
                total_pr_fm = 0
                subject_count = 0

                for subject in subjects:
                    subject_count += 1
                    mo_dict[subject.id] = {
                        'subject_name': subject.subject,
                        'subject_id': subject.id,
                    }

                    try:
                        marks = MarkObtained.objects.get(
                            student=student.student,
                            session=session,
                            grade=grade,
                            term=term,
                            subject=subject
                        )
                        th_mo = marks.th_mo or 0
                        pr_mo = marks.pr_mo or 0
                    except MarkObtained.DoesNotExist:
                        th_mo = 0
                        pr_mo = 0

                    try:
                        gfm = GradeFullMarks.objects.get(
                            session=session, school=school, grade=grade, term=term, subject=subject
                        )
                        th_fm = gfm.th_fm or 0
                        pr_fm = gfm.pr_fm or 0
                        th_pm = gfm.th_pm or 0
                        pr_pm = gfm.pr_pm or 0
                    except GradeFullMarks.DoesNotExist:
                        th_fm = pr_fm = th_pm = pr_pm = 0

                    mo_dict[subject.id]['th_fm'] = th_fm
                    mo_dict[subject.id]['pr_fm'] = pr_fm
                    mo_dict[subject.id]['th_pm'] = th_pm
                    mo_dict[subject.id]['pr_pm'] = pr_pm
                    mo_dict[subject.id]['th_mo'] = th_mo
                    mo_dict[subject.id]['pr_mo'] = pr_mo

                    total_th_mo += th_mo
                    total_pr_mo += pr_mo
                    total_th_fm += th_fm
                    total_pr_fm += pr_fm

                total_mo = total_th_mo + total_pr_mo
                total_fm = total_th_fm + total_pr_fm
                percentage = round((total_mo / total_fm * 100), 2) if total_fm > 0 else 0

                result = {
                    'mo_dict': mo_dict,
                    'total_th_mo': total_th_mo,
                    'total_pr_mo': total_pr_mo,
                    'total_mo': total_mo,
                    'total_fm': total_fm,
                    'total_th_fm': total_th_fm,
                    'total_pr_fm': total_pr_fm,
                    'percentage': percentage,
                    'cgpa': None,
                    'overall_grade': '',
                    'overall_symbol': '',
                    'overall_point': 0,
                    'fail_count': 0,
                    'remarks': '',
                    'subjects': subjects,
                }
            else:
                # Calculated mode - use full grading logic
                result = calculate_student_result(school, session, grade, term, student, config)

            rank = all_ranks.get(student.student.reg_no, '-')
            student_data.append({
                'student': student,
                'rank': rank,
                **result,
            })

        # Apply filter
        if data_filter == 1:  # Pass only
            student_data = [s for s in student_data if s.get('fail_count', 0) == 0]
        elif data_filter == 2:  # Fail only
            student_data = [s for s in student_data if s.get('fail_count', 0) > 0]

        ctx = _nav_context(request)
        ctx.update({
            'school': school,
            'term': term,
            'grade': grade,
            'section': section,
            'subjects': subjects,
            'data': student_data,
            'config': config,
            'mode': mode,
            'data_filter': data_filter,
            'data_order': data_order,
            'rank_by': rank_by,
            'printtype': printtype,
            'is_exam_print': 'result',
        })

        if printtype == 2:
            return render(request, 'exam/result_summary.html', ctx)
        else:
            return render(request, 'exam/result_detail.html', ctx)

    ctx = _nav_context(request)
    ctx.update({
        'edusession': edusession_all, 'current_session': current_session,
        'exam_types': exam_types, 'section_list': _json.dumps(section_list),
        'term_list': _json.dumps(term_dict), 'school': school, 'grades': grades,
        'branchuser': branchuser, 'live_calc_type': live_calc_type,
        'is_exam_print': 'result',
    })
    return render(request, 'exam/print_result.html', ctx)


# Additional legacy redirect helper for a mis‑named URL.
# The URL pattern in exam/urls.py expects ``_redirect_marks_input_form`` but the
# original implementation defined ``_redirect_printmarksform``.  To keep the
# routing functional without touching the URL config, we provide a thin wrapper
# that forwards to the correct view.
# ----------------------------------------------------------------------

def _redirect_marks_input_form(request):
    """Redirect legacy ``print/data/`` URL to the marks input form.

    The correct target is the ``exam:marks_input_form`` view, which is already
    handled by ``_redirect_printmarksform``.  This wrapper preserves backward
    compatibility.
    """
    return redirect('exam:marks_input_form')


# ── Ledger Print Views ─────────────────────────────────────────────────────────

@login_required
def print_ledger(request):
    """Selection form for ledger preview and print."""
    from sms.models import SchoolGrade, EduSession, Section
    from exam.models import SchoolTerm
    import json as _json

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    current_session = get_current_session()
    edusession_all = EduSession.objects.all().order_by('-year')
    grades = SchoolGrade.objects.filter(school=school, active=True).order_by('id')
    exam_types = SchoolTerm.objects.filter(school=school, active=True)

    section_list = {}
    for session in edusession_all:
        sid = str(session.id)
        section_list[sid] = {}
        for g in grades:
            section_list[sid][str(g.id)] = {str(s.id): s.section for s in Section.objects.filter(grade=g, session=session)}

    section_list_json = _json.dumps(section_list)

    term_dict = {}
    for term in exam_types:
        year_id = str(term.year.id)
        if year_id not in term_dict:
            term_dict[year_id] = []
        term_dict[year_id].append({'id': term.id, 'name': f"{term.term_name.upper()} {term.year.year}"})
    term_list_json = _json.dumps(term_dict)

    ctx = _nav_context(request)
    ctx.update({
        'edusession': edusession_all, 'current_session': current_session,
        'exam_types': exam_types, 'grades': grades, 'school': school,
        'branchuser': branchuser, 'section_list': section_list_json, 'term_list': term_list_json,
        'is_exam_print': 'mark_ledger',
    })
    return render(request, 'exam/print_ledger.html', ctx)


@login_required
def print_ledger_from_calc(request, term_id):
    """Generate ledger based on term_calculation from ResultManagement."""
    from sms.models import SchoolGrade, EduSession, Section, Subject, StudentSession, MarkObtained, Attendance
    from exam.models import SchoolTerm, ResultManagement, SchoolTerminology, GradeFullMarks
    from exam.func import calculate_student_result, calculate_rank
    import json as _json

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    current_session = get_current_session()

    try:
        this_term = SchoolTerm.objects.get(id=term_id, school=school)
    except SchoolTerm.DoesNotExist:
        return HttpResponse("Term not found.")

    # Get the term calculation config from ResultManagement
    try:
        term_calc = ResultManagement.objects.get(school=school, year=current_session, school_term=this_term)
        term_calc_data = _json.loads(term_calc.term_calculation)
    except (ResultManagement.DoesNotExist, _json.JSONDecodeError):
        term_calc_data = {}

    # Build term list from calculation config
    term_list = []
    term_acronym = {}
    for key, value in term_calc_data.items():
        if int(value) > 0:
            try:
                t = SchoolTerm.objects.get(id=key)
                term_acronym[int(key)] = t.name_in_short or t.term_name[:3]
                term_list.append(int(key))
            except SchoolTerm.DoesNotExist:
                continue

    # Always include the target term
    if this_term.id not in term_list:
        term_list.append(this_term.id)
        term_acronym[this_term.id] = this_term.name_in_short or this_term.term_name[:3]

    no_of_terms = len(term_list)
    no_of_terms_range = range(len(term_list))
    no_of_terms_marks_count = no_of_terms * 2
    gpa_colspan = 4 + no_of_terms_marks_count

    # GET request - show selection form
    if request.method == 'GET':
        from sms.models import SchoolGrade, EduSession, Section
        from exam.models import SchoolTerm

        current_session = get_current_session()
        edusession_all = EduSession.objects.all().order_by('-year')
        grades = SchoolGrade.objects.filter(school=school, active=True).order_by('id')
        exam_types = SchoolTerm.objects.filter(school=school, active=True)

        section_list = {}
        for session in edusession_all:
            sid = str(session.id)
            section_list[sid] = {}
            for g in grades:
                section_list[sid][str(g.id)] = {str(s.id): s.section for s in Section.objects.filter(grade=g, session=session)}

        ctx = _nav_context(request)
        ctx.update({
            'edusession': edusession_all, 'current_session': current_session,
            'exam_types': exam_types, 'grades': grades, 'school': school,
            'branchuser': branchuser, 'term': this_term,
            'term_list': term_list, 'term_acronym': term_acronym,
            'no_of_terms': len(term_list),
            'is_exam_print': 'mark_ledger',
        })
        return render(request, 'exam/print_ledger.html', ctx)

# POST - generate ledger
    grade_id = request.POST.get('grade2')
    section_id = request.POST.get('section2')
    printtype = int(request.POST.get('printtype', 1))
    ledgerttype = int(request.POST.get('ledgerttype', 2))
    grading_type = int(request.POST.get('grading_type', 2))
    ledgermode = int(request.POST.get('ledgermode', 1))
    rank_by = request.POST.get('rank_by', 'total')
    order = request.POST.get('order_print', '1')
    data_filter = int(request.POST.get('filter', 0))

    try:
        grade = SchoolGrade.objects.get(id=grade_id)
        session = current_session
        term = this_term

        if section_id and str(section_id).strip() not in ("", "0"):
            section = Section.objects.get(id=section_id, session=session)
        else:
            section = None

        # Build term list from term_calc_data (for RESULT CALC CONFIG mode)
        term_list = []
        term_acronym = {}
        source_terms = []
        normalized_wconfig = {}
        
        if ledgermode in [2, 3, 4]:  # WEIGHTED, CONSOLIDATED RAW, or RESULT CALC CONFIG
            if ledgermode == 4:  # RESULT CALC CONFIG - use ResultManagement.term_calculation
                # term_calc_data already parsed from ResultManagement
                normalized_wconfig, _ = _parse_weighted_term_config(term_calc_data, this_term.id, include_current=True)
                source_term_ids = list(normalized_wconfig.keys())
                term_objects = {str(t.id): t for t in SchoolTerm.objects.filter(id__in=source_term_ids)}
                source_terms = [term_objects[tid] for tid in source_term_ids if tid in term_objects]
            else:  # WEIGHTED (2) or CONSOLIDATED RAW (3) - use WeightedResultManagement
                weighted_config_obj = WeightedResultManagement.objects.filter(school=school, year=current_session, school_term=this_term).first()
                if weighted_config_obj:
                    normalized_wconfig, _ = _parse_weighted_term_config(weighted_config_obj.weight_config, this_term.id, include_current=True)
                    source_term_ids = list(normalized_wconfig.keys())
                    term_objects = {str(t.id): t for t in SchoolTerm.objects.filter(id__in=source_term_ids)}
                    source_terms = [term_objects[tid] for tid in source_term_ids if tid in term_objects]
                else:
                    ledgermode = 1  # Fallback to standard
            
            if not source_terms:
                ledgermode = 1  # Fallback to standard if no source terms

            # Build term_list from source_terms
            term_list = [t.id for t in source_terms]
            term_acronym = {t.id: t.name_in_short or t.term_name[:3] for t in source_terms}
        else:  # Standard mode (1)
            term_list = [this_term.id]
            term_acronym = {this_term.id: this_term.name_in_short or this_term.term_name[:3]}

        # Get ranks
        config = _get_result_config(school, session, grade)
        config['grading_type'] = grading_type
        config['ledgerttype'] = ledgerttype
        config['ledgermode'] = ledgermode
        config['calculation_type'] = 'legacy'  # term_calc uses legacy calculation

        ranks = calculate_rank(school.id, session, grade, term, section, rank_by=rank_by, config=config)

        subjects = Subject.objects.filter(session=session, branch=school, grade=grade, status=True).order_by('id')

        # Build student queryset
        base_qs = StudentSession.objects.filter(session=session, grade=grade, status=True)
        if section:
            base_qs = base_qs.filter(section=section)
        
        if order == '1':
            students = list(base_qs.select_related('student').order_by('student__reg_no'))
        elif order == '2':
            students = list(base_qs.select_related('student').order_by('roll_no'))
        elif order == '3':
            students = list(base_qs.select_related('student'))
            students.sort(key=lambda s: ranks.get(s.student.reg_no, 9999))
        else:
            students = list(base_qs.select_related('student').order_by('roll_no'))

        # Get ranks for all students (for display)
        all_ranks = calculate_rank(school.id, session, grade, term, section, rank_by=rank_by, config=config)

        # Calculate results for each student
        student_data_list = []
        
        if ledgermode == 4:  # RESULT CALC CONFIG - use term_calc_data for weighted calculation
            # Parse the weighted config for this term
            normalized_wconfig, _ = _parse_weighted_term_config(term_calc_data, this_term.id, include_current=True)
            
            # Build source term IDs and fetch terms
            source_term_ids = list(normalized_wconfig.keys())
            term_objects = {str(t.id): t for t in SchoolTerm.objects.filter(id__in=source_term_ids)}
            source_terms = [term_objects[tid] for tid in source_term_ids if tid in term_objects]
            
            # Pre-fetch marks and full marks for all source terms
            all_marks_map = {}
            source_fm_map = {}
            
            source_term_ids = [t.id for t in source_terms]
            marks_qs = MarkObtained.objects.filter(
                school=school, session=session, grade=grade, 
                term_id__in=source_term_ids, 
                subject_id__in=[s.id for s in subjects]
            )
            for m in marks_qs:
                all_marks_map[(m.student_id, m.term_id, m.subject_id)] = (m.th_mo or 0, m.pr_mo or 0)

            source_fm_qs = GradeFullMarks.objects.filter(
                school=school, session=session, grade=grade, term_id__in=source_term_ids
            )
            source_fm_map = {(fm.term_id, fm.subject_id): (fm.th_fm or 0, fm.pr_fm or 0) for fm in source_fm_qs}

            for student in students:
                student_subject_totals = {sub.id: {"th": 0, "pr": 0} for sub in subjects}
                student_breakdown = []
                
                for src_term in source_terms:
                    term_label = getattr(src_term, 'name_in_short', None) or src_term.term_name
                    term_entry = {"term_label": term_label, "subjects": []}
                    w_info = normalized_wconfig.get(str(src_term.id))
                    
                    for sub in subjects:
                        s_th, s_pr = all_marks_map.get((student.student_id, src_term.id, sub.id), (0, 0))
                        s_th_fm, s_pr_fm = source_fm_map.get((src_term.id, sub.id), (100, 100))
                        
                        if w_info:  # Weighted mode
                            if w_info.get("plan") == "scaling":
                                val_th = (s_th / s_th_fm * w_info["th_target_fm"] * w_info["th_from_th"]) if s_th_fm > 0 else 0
                                val_pr = (s_pr / s_pr_fm * w_info["pr_target_fm"] * w_info["pr_from_pr"]) if s_pr_fm > 0 else 0
                            else:
                                val_th = s_th * w_info["th_from_th"]
                                val_pr = s_pr * w_info["pr_from_pr"]
                        else:  # Consolidated raw mode
                            val_th = s_th
                            val_pr = s_pr
                        
                        student_subject_totals[sub.id]["th"] += val_th
                        student_subject_totals[sub.id]["pr"] += val_pr
                        
                        term_entry["subjects"].append({
                            "th_val": int(val_th) if val_th == int(val_th) else round(val_th, 2),
                            "pr_val": int(val_pr) if val_pr == int(val_pr) else round(val_pr, 2),
                            "th_max": s_th_fm,
                            "pr_max": s_pr_fm,
                        })
                    student_breakdown.append(term_entry)
                
                # Add TOTAL row
                total_label = "TOTAL"
                total_entry = {"term_label": total_label, "subjects": [], "is_total": True}
                for sub in subjects:
                    t_th = student_subject_totals[sub.id]["th"]
                    t_pr = student_subject_totals[sub.id]["pr"]
                    total_entry["subjects"].append({
                        "th_val": int(t_th) if t_th == int(t_th) else round(t_th, 2),
                        "pr_val": int(t_pr) if t_pr == int(t_pr) else round(t_pr, 2),
                        "th_max": 0,
                        "pr_max": 0,
                    })
                student_breakdown.append(total_entry)
                
                # Calculate rank
                rank = all_ranks.get(student.student.reg_no, '-')
                
                student_data_list.append({
                    'student': student,
                    'rank': rank,
                    'breakdown_terms': student_breakdown,
                })
        else:
            # Standard mode (1), Weighted (2), Consolidated (3) - use single term calculation
            for student in students:
                result = calculate_student_result(school, session, grade, term, student, config)
                result['student'] = student
                result['rank'] = all_ranks.get(student.student.reg_no, '-')
                student_data_list.append({
                    'student': student,
                    'rank': result['rank'],
                    'breakdown_terms': [{
                        'term_label': term.term_name,
                        'subjects': [],
                        'is_total': False
                    } for bt in [result]],  # Simplified - will be handled by template
                    'totals': {
                        'total_fm': result['total_fm'],
                        'total_mo': result['total_mo'],
                        'percentage': result['percentage'],
                        'cgpa': result['cgpa'],
                        'overall_grade': result['overall_grade'],
                        'overall_symbol': result['overall_symbol'],
                        'any_fail': result['fail_count'] > 0,
                    },
                })

        # Get terminology
        try:
            terminology = SchoolTerminology.objects.get(school=school)
        except SchoolTerminology.DoesNotExist:
            terminology = None

        # Build term list for ledger (from term_calc_data)
        term_list = []
        term_acronym = {}
        for key, value in term_calc_data.items():
            if int(value) > 0:
                try:
                    t = SchoolTerm.objects.get(id=key)
                    term_acronym[int(key)] = t.name_in_short or t.term_name[:3]
                    term_list.append(int(key))
                except SchoolTerm.DoesNotExist:
                    continue

        # Always include the target term
        if this_term.id not in term_list:
            term_list.append(this_term.id)
            term_acronym[this_term.id] = this_term.name_in_short or this_term.term_name[:3]

        no_of_terms = len(term_list)
        no_of_terms_range = range(len(term_list))
        no_of_terms_marks_count = no_of_terms * 2
        gpa_colspan = 4 + no_of_terms_marks_count

        # Get attendance data
        from sms.models import Attendance
        attendance_data = {}
        for item in student_data_list:
            student = item['student']
            attendance = Attendance.objects.filter(
                reg_no=student.student.reg_no,
                session=session,
                grade=grade,
                term=term
            ).first()
            if attendance:
                attendance_data[student.student.reg_no] = {
                    'present': attendance.no_of_present_days,
                    'total': attendance.no_of_school_days,
                }
            else:
                attendance_data[student.student.reg_no] = {'present': 0, 'total': 0}
            item['attendance'] = attendance_data.get(item['student'].student.reg_no, {'present': 0, 'total': 0})

        # Build mo_dict for JavaScript (matching panel format)
        mo_dict = {}
        for item in student_data_list:
            for sub_id, sub_data in item['mo_dict'].items():
                for term_id in term_list:
                    prefix = f"{item['student'].student.reg_no}_{sub_id}_{term_id}"
                    mo_dict[f"{prefix}_th_grade"] = sub_data.get('th_grade', '-')
                    mo_dict[f"{prefix}_th_symbol"] = sub_data.get('th_symbol', '')
                    mo_dict[f"{prefix}_th_point"] = sub_data.get('th_point', '-')
                    mo_dict[f"{prefix}_pr_grade"] = sub_data.get('pr_grade', '-')
                    mo_dict[f"{prefix}_pr_symbol"] = sub_data.get('pr_symbol', '')
                    mo_dict[f"{prefix}_pr_point"] = sub_data.get('pr_point', '-')
                    mo_dict[f"{prefix}_total_grade"] = sub_data.get('total_grade', '-')
                    mo_dict[f"{prefix}_total_symbol"] = sub_data.get('total_symbol', '')
                    mo_dict[f"{prefix}_total_point"] = sub_data.get('total_point', '-')

        # Add GPA and remarks to mo_dict for each student
        for item in student_data_list:
            reg_no = item['student'].student.reg_no
            mo_dict[f"{reg_no}_gpa"] = item.get('cgpa', 0)
            mo_dict[f"{reg_no}_remarks"] = item.get('remarks', '')

        # Subject FM list for header reference
        subject_fm_list = []
        for sub in subjects:
            fm = GradeFullMarks.objects.filter(school=school, session=session, grade=grade, term=term, subject=sub).first()
            th_max = fm.th_fm if fm else 0
            pr_max = fm.pr_fm if fm else 0

            subject_fm_list.append({
                "name": sub.subject,
                "th_fm": int(th_max),
                "pr_fm": int(pr_max),
            })

        ctx = _nav_context(request)
        ctx.update({
            'school': school,
            'term': term,
            'year': term.year,
            'student_data': student_data_list,
            'grade': grade,
            'section': section,
            'subjects': subjects,
            'ledgermode': ledgermode,
            'ledgerttype': ledgerttype,
            'subject_fm_list': subject_fm_list,
            'terminology': terminology,
            'term_list': term_list,
            'term_acronym': term_acronym,
            'no_of_terms': len(term_list),
            'no_of_terms_range': range(len(term_list)),
            'no_of_terms_marks_count': len(term_list) * 2,
            'gpa_colspan': 4 + len(term_list) * 2,
            'mo_dict': json.dumps(mo_dict),
            'the_space': range(0),
        })
        return render(request, 'exam/ledger_preview.html', ctx)
    except Exception as e:
        messages.error(request, f"Error generating ledger: {str(e)}")
        return redirect('exam:print_ledger_from_calc', term_id=term_id)


@login_required
def ledger_preview(request):
    """Generate ledger preview with weighted/consolidated options."""
    from sms.models import SchoolGrade, EduSession, Section, Subject, StudentSession, MarkObtained
    from exam.models import SchoolTerm, WeightedResultManagement, SchoolTerminology, GradeFullMarks
    from exam.func import _parse_weighted_term_config
    import json as _json

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school

    try:
        terminology = SchoolTerminology.objects.get(school=school)
    except SchoolTerminology.DoesNotExist:
        terminology = None

    if request.method == "POST":
        edusession_id = request.POST.get("edusession")
        term_id = request.POST.get("term")
        grade_id = request.POST.get("grade")
        section_id = request.POST.get("section")
        order = request.POST.get("order")
        ledgermode = request.POST.get("ledgermode", "1")

        # Validate grade_id
        if not grade_id or grade_id == "0" or grade_id == "":
            messages.error(request, "Please select a valid grade.")
            return redirect('exam:ledger_preview')

        this_grade = SchoolGrade.objects.get(id=grade_id)
        this_session = EduSession.objects.get(id=edusession_id)
        this_term = SchoolTerm.objects.get(id=term_id)

        if section_id and str(section_id).strip() not in ("", "0"):
            this_section = Section.objects.get(id=section_id)
        else:
            this_section = None

        subjects = Subject.objects.filter(session=this_session, branch=school, grade=this_grade, status=True).order_by("id")

        normalized_wconfig = {}
        source_terms = []
        if ledgermode in ["2", "3"]:
            weighted_config_obj = WeightedResultManagement.objects.filter(school=school, year=this_session, school_term=this_term).first()
            if weighted_config_obj:
                normalized_wconfig, _ = _parse_weighted_term_config(weighted_config_obj.weight_config, this_term.id, include_current=True)
                source_term_ids = list(normalized_wconfig.keys())
                term_objects = {str(t.id): t for t in SchoolTerm.objects.filter(id__in=source_term_ids)}
                source_terms = [term_objects[tid] for tid in source_term_ids if tid in term_objects]

                if not source_terms:
                    ledgermode = "1"
            else:
                ledgermode = "1"

        base_qs_kwargs = {"grade": this_grade, "session": this_session, "status": True}
        if this_section:
            base_qs_kwargs["section"] = this_section

        try:
            order = int(order or "1")
        except:
            order = 1

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

                        if ledgermode == "2" and w_info:  # Weighted
                            # Cross-mixing: TH gets contribution from both TH and PR
                            val_th = s_th * w_info.get("th_from_th", 0) + s_pr * w_info.get("th_from_pr", 0)
                            val_pr = s_th * w_info.get("pr_from_th", 0) + s_pr * w_info.get("pr_from_pr", 0)
                            # For scaling plan (if implemented in future)
                            if w_info.get("plan") == "scaling":
                                # Note: scaling not fully implemented in breakdown view
                                pass
                        else:  # Consolidated Raw
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
                if ledgermode == "2":
                    total_label += " (WGT)"

                total_entry = {"term_label": total_label, "subjects": [], "is_total": True}
                for sub in subjects:
                    t_th = student_subject_totals[sub.id]["th"]
                    t_pr = student_subject_totals[sub.id]["pr"]
                    total_entry["subjects"].append({
                        "th_val": int(t_th) if t_th == int(t_th) else round(t_th, 2),
                        "pr_val": int(t_pr) if t_pr == int(t_pr) else round(t_pr, 2),
                        "th_max": 0,
                        "pr_max": 0
                    })
                std_entry["breakdown_terms"].append(total_entry)

            student_data_list.append(std_entry)

        # Subject FM list for header reference
        subject_fm_list = []
        for sub in subjects:
            if ledgermode in ["2", "3"]:
                th_max = 0
                pr_max = 0
                if ledgermode == "3":  # Consolidated (Sum of all source FMs)
                    th_max = sum(source_fm_map.get((t.id, sub.id), (0, 0))[0] for t in source_terms)
                    pr_max = sum(source_fm_map.get((t.id, sub.id), (0, 0))[1] for t in source_terms)
                else:  # Weighted (Mode 2)
                    th_max = 0
                    pr_max = 0
                    for t in source_terms:
                        w_info = normalized_wconfig.get(str(t.id), {})
                        s_th_fm, s_pr_fm = source_fm_map.get((t.id, sub.id), (0, 0))
                        # Cross-mixing for FM: TH gets contribution from both TH and PR FM
                        if w_info.get("plan") == "scaling":
                            # Note: scaling plan would need target_fm from global settings
                            # For now, use the same logic as direct but with scaling
                            th_max += s_th_fm * w_info.get("th_from_th", 0)
                            th_max += s_pr_fm * w_info.get("th_from_pr", 0)
                            pr_max += s_th_fm * w_info.get("pr_from_th", 0)
                            pr_max += s_pr_fm * w_info.get("pr_from_pr", 0)
                        else:
                            th_max += s_th_fm * w_info.get("th_from_th", 0)
                            th_max += s_pr_fm * w_info.get("th_from_pr", 0)
                            pr_max += s_th_fm * w_info.get("pr_from_th", 0)
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

        ctx = _nav_context(request)
        ctx.update({
            "school": school, "term": this_term, "year": this_term.year,
            "student_data": student_data_list, "grade": this_grade, "section": this_section,
            "subjects": subjects, "ledgermode": ledgermode, "ledgertype": "2",
            "subject_fm_list": subject_fm_list,
            "terminology": terminology,
            "edusession_id": edusession_id, "term_id": term_id, "grade_id": grade_id, "section_id": section_id,
        })
        return render(request, 'exam/ledger_preview.html', ctx)

    # GET request - show selection form (same as print_ledger)
    from sms.models import SchoolGrade, EduSession
    from exam.models import SchoolTerm

    current_session = get_current_session()
    edusession_all = EduSession.objects.all().order_by('-year')
    grades = SchoolGrade.objects.filter(school=school, active=True).order_by('id')
    exam_types = SchoolTerm.objects.filter(school=school, active=True)

    section_list = {}
    for session in edusession_all:
        sid = str(session.id)
        section_list[sid] = {}
        for g in grades:
            section_list[sid][str(g.id)] = {str(s.id): s.section for s in Section.objects.filter(grade=g, session=session)}

    section_list_json = _json.dumps(section_list)

    term_dict = {}
    for term in exam_types:
        year_id = str(term.year.id)
        if year_id not in term_dict:
            term_dict[year_id] = []
        term_dict[year_id].append({'id': term.id, 'name': f"{term.term_name.upper()} {term.year.year}"})
    term_list_json = _json.dumps(term_dict)

    ctx = _nav_context(request)
    ctx.update({
        'edusession': edusession_all, 'current_session': current_session,
        'exam_types': exam_types, 'grades': grades, 'school': school,
        'branchuser': branchuser, 'section_list': section_list_json, 'term_list': term_list_json,
        'is_exam_print': 'mark_ledger',
    })
    return render(request, 'exam/print_ledger.html', ctx)


@login_required
def print_ledger_now(request):
    """Generate full ledger for printing using centralized calculation."""
    from sms.models import SchoolGrade, EduSession, Section, Subject, StudentSession, Attendance
    from exam.models import SchoolTerm, WeightedResultManagement, SchoolTerminology, GradeFullMarks
    from exam.func import _parse_weighted_term_config, calculate_rank, calculate_student_result
    import json as _json

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school

    if request.method == "POST":
        edusession_id = request.POST.get("edusession")
        term_id = request.POST.get("term")
        grade_id = request.POST.get("grade2")
        section_id = request.POST.get("section2")
        printtype = int(request.POST.get("printtype", 1))
        ledgerttype = int(request.POST.get("ledgerttype", 2))
        grading_type = int(request.POST.get("grading_type", 2))
        ledgermode = int(request.POST.get("ledgermode", 1))
        rank_by = request.POST.get("rank_by", "total")
        order = request.POST.get("order_print", "1")
        filter_mode = int(request.POST.get("filter", 0))

        this_grade = SchoolGrade.objects.get(id=grade_id)
        this_session = EduSession.objects.get(id=edusession_id)
        this_term = SchoolTerm.objects.get(id=term_id)

        if section_id and str(section_id).strip() not in ("", "0"):
            this_section = Section.objects.get(id=section_id)
        else:
            this_section = None

# Get ranks
        config = _get_result_config(school, this_session, this_grade)
        config['grading_type'] = grading_type
        config['ledgerttype'] = ledgerttype
        config['ledgermode'] = ledgermode
        # Use weighted calculation when ledgermode is 2 (Weighted Breakdown)
        config['calculation_type'] = 'weighted' if ledgermode == 2 else 'legacy'
        ranks = calculate_rank(school.id, this_session, this_grade, this_term, this_section, rank_by=rank_by, config=config)

        subjects = Subject.objects.filter(session=this_session, branch=school, grade=this_grade, status=True).order_by("id")

        # Build student queryset
        base_qs = StudentSession.objects.filter(session=this_session, grade=this_grade, status=True)
        if this_section:
            base_qs = base_qs.filter(section=this_section)

        if order == "1":
            students = list(base_qs.select_related('student').order_by('student__reg_no'))
        elif order == "2":
            students = list(base_qs.select_related('student').order_by('roll_no'))
        elif order == "3":
            students = list(base_qs.select_related('student'))
            students.sort(key=lambda s: ranks.get(s.student.reg_no, 9999))
        else:
            students = list(base_qs.select_related('student').order_by('roll_no'))

        # Get weighted config if needed
        normalized_wconfig = {}
        source_terms = []
        if ledgermode in [2, 3]:
            weighted_config_obj = WeightedResultManagement.objects.filter(school=school, year=this_session, school_term=this_term).first()
            if weighted_config_obj:
                normalized_wconfig, _ = _parse_weighted_term_config(weighted_config_obj.weight_config, this_term.id, include_current=True)
                source_term_ids = list(normalized_wconfig.keys())
                term_objects = {str(t.id): t for t in SchoolTerm.objects.filter(id__in=source_term_ids)}
                source_terms = [term_objects[tid] for tid in source_term_ids if tid in term_objects]
                if not source_terms:
                    ledgermode = 1
            else:
                ledgermode = 1

        # Build term list for ledger
        term_list = [this_term.id]
        term_acronym = {this_term.id: this_term.name_in_short or this_term.term_name[:3]}
        if ledgermode in [2, 3]:
            for src_term in source_terms:
                term_list.append(src_term.id)
                term_acronym[src_term.id] = src_term.name_in_short or src_term.term_name[:3]
        no_of_terms = len(term_list)
        no_of_terms_range = range(len(term_list))
        no_of_terms_marks_count = no_of_terms * 2  # TH + PR per term
        gpa_colspan = 4 + no_of_terms_marks_count  # S.N + Subject + TH/PR columns + Aggregate

        # Calculate results for each student using centralized function
        student_data_list = []
        for student in students:
            result = calculate_student_result(school, this_session, this_grade, this_term, student, config)
            result['student'] = student
            result['rank'] = ranks.get(student.student.reg_no, '-')
            student_data_list.append(result)

        # Get terminology
        try:
            terminology = SchoolTerminology.objects.get(school=school)
        except Exception:
            terminology = None

        # Get attendance data
        from sms.models import Attendance
        attendance_data = {}
        for item in student_data_list:
            student = item['student']
            attendance = Attendance.objects.filter(
                reg_no=student.student.reg_no,
                session=this_session,
                grade=this_grade,
                term=this_term
            ).first()
            if attendance:
                attendance_data[student.student.reg_no] = {
                    'present': attendance.no_of_present_days,
                    'total': attendance.no_of_school_days,
                }
            else:
                attendance_data[student.student.reg_no] = {'present': 0, 'total': 0}
            item['attendance'] = attendance_data.get(item['student'].student.reg_no, {'present': 0, 'total': 0})

        # Build mo_dict for JavaScript (matching panel format)
        mo_dict = {}
        for item in student_data_list:
            for sub_id, sub_data in item['mo_dict'].items():
                for term_id in term_list:
                    prefix = f"{item['student'].student.reg_no}_{sub_id}_{term_id}"
                    mo_dict[f"{prefix}_th_grade"] = sub_data.get('th_grade', '-')
                    mo_dict[f"{prefix}_th_symbol"] = sub_data.get('th_symbol', '')
                    mo_dict[f"{prefix}_th_point"] = sub_data.get('th_point', '-')
                    mo_dict[f"{prefix}_pr_grade"] = sub_data.get('pr_grade', '-')
                    mo_dict[f"{prefix}_pr_symbol"] = sub_data.get('pr_symbol', '')
                    mo_dict[f"{prefix}_pr_point"] = sub_data.get('pr_point', '-')
                    mo_dict[f"{prefix}_total_grade"] = sub_data.get('total_grade', '-')
                    mo_dict[f"{prefix}_total_symbol"] = sub_data.get('total_symbol', '')
                    mo_dict[f"{prefix}_total_point"] = sub_data.get('total_point', '-')

        # Add GPA and remarks to mo_dict for each student
        for item in student_data_list:
            reg_no = item['student'].student.reg_no
            mo_dict[f"{reg_no}_gpa"] = item.get('cgpa', 0)
            mo_dict[f"{reg_no}_remarks"] = item.get('remarks', '')

        # Subject FM list for header reference
        subject_fm_list = []
        for sub in subjects:
            if len(term_list) > 1:
                th_max = 0
                pr_max = 0
                if ledgermode == 3:  # Consolidated (Sum of all source FMs)
                    th_max = sum(source_fm_map.get((t.id, sub.id), (0, 0))[0] for t in source_terms)
                    pr_max = sum(source_fm_map.get((t.id, sub.id), (0, 0))[1] for t in source_terms)
                else:  # Weighted (Mode 2) or standard
                    fm = GradeFullMarks.objects.filter(school=school, session=this_session, grade=this_grade, term=this_term).filter(subject=sub).first()
                    th_max = fm.th_fm if fm else 0
                    pr_max = fm.pr_fm if fm else 0
            else:
                fm = GradeFullMarks.objects.filter(school=school, session=this_session, grade=this_grade, term=this_term).filter(subject=sub).first()
                th_max = fm.th_fm if fm else 0
                pr_max = fm.pr_fm if fm else 0

            subject_fm_list.append({
                "name": sub.subject,
                "th_fm": int(th_max),
                "pr_fm": int(pr_max),
            })

        ctx = _nav_context(request)
        ctx.update({
            'school': school,
            'term': this_term,
            'year': this_term.year,
            'student_data': student_data_list,
            'grade': this_grade,
            'section': this_section,
            'subjects': subjects,
            'ledgermode': ledgermode,
            'ledgertype': ledgerttype,
            'subject_fm_list': subject_fm_list,
            'terminology': terminology,
            'term_list': term_list,
            'term_acronym': term_acronym,
            'no_of_terms': len(term_list),
            'no_of_terms_range': range(len(term_list)),
            'no_of_terms_marks_count': len(term_list) * 2,
            'gpa_colspan': 4 + len(term_list) * 2,
            'mo_dict': json.dumps(mo_dict),
            'the_space': range(0),  # Empty for single term
        })
        return render(request, 'exam/ledger_preview.html', ctx)

    return HttpResponseRedirect('/exam/')


# ── Result Status / Public Result Views ───────────────────────────────────────

@login_required
def result_status(request, regno):
    """Toggle result publish status for a student."""
    from sms.models import Student, BranchUser
    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    try:
        student = Student.objects.get(reg_no=regno)
        if branchuser.school == student.school:
            student.publish_result = not student.publish_result
            student.save()
    except Student.DoesNotExist:
        pass

    return_url = request.GET.get('return_path', '/exam/')
    return HttpResponseRedirect(return_url)


@login_required
def private_result(request, regno):
    """Private result view for a single student."""
    from sms.models import Student, BranchUser, StudentSession, Subject
    from exam.models import LiveResult, SchoolTerm, ResultManagement
    import json as _json

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    this_session = get_current_session()

    try:
        student = Student.objects.get(reg_no=int(regno))
        if student.school != school:
            return HttpResponse("Not allowed.")
    except Student.DoesNotExist:
        return HttpResponse("Student not found.")

    try:
        std_session = StudentSession.objects.get(student=student, session=this_session, status=True)
    except StudentSession.DoesNotExist:
        return HttpResponse("Student session not found.")

    result_status = LiveResult.objects.filter(school=school).first()
    if not result_status:
        return HttpResponse("Result not configured.")

    try:
        grade_list = _json.loads(result_status.grade_list)
    except Exception:
        grade_list = []

    term = result_status.term
    try:
        this_term = SchoolTerm.objects.get(id=term)
    except SchoolTerm.DoesNotExist:
        return HttpResponse("Term not found.")

    if std_session.grade.id not in grade_list:
        return HttpResponse("Result not published for this grade.")

    # Calculate term list from result management
    try:
        term_calc = ResultManagement.objects.get(school=school, year=this_session, school_term=this_term)
        term_calc_data = _json.loads(term_calc.term_calculation)
    except (ResultManagement.DoesNotExist, _json.JSONDecodeError):
        term_calc_data = {}

    term_list = []
    for key, value in term_calc_data.items():
        if int(value) > 0:
            try:
                t = SchoolTerm.objects.get(id=key)
                term_list.append(t.id)
            except SchoolTerm.DoesNotExist:
                continue

    # Get subjects
    subjects = Subject.objects.filter(
        session=this_session, branch=school, grade=std_session.grade, status=True
    ).order_by('id')

    # Build marks map
    term_ids = list(term_list) + [this_term.id]
    marks_qs = MarkObtained.objects.filter(
        school=school, session=this_session, grade=std_session.grade,
        term_id__in=term_ids, student=student
    )
    marks_map = {}
    for m in marks_qs:
        marks_map[(m.term_id, m.subject_id)] = (m.th_mo or 0, m.pr_mo or 0)

    # Build full marks map
    fm_qs = GradeFullMarks.objects.filter(
        school=school, session=this_session, grade=std_session.grade, term_id__in=term_ids
    )
    fm_map = {}
    for fm in fm_qs:
        fm_map[(fm.term_id, fm.subject_id)] = (fm.th_fm or 0, fm.pr_fm or 0, fm.th_pm or 0, fm.pr_pm or 0)

    student_terms = {}
    for t_id in term_ids:
        try:
            t = SchoolTerm.objects.get(id=t_id)
        except SchoolTerm.DoesNotExist:
            continue
        term_data = {'term': t, 'subjects': []}
        for sub in subjects:
            th_mo, pr_mo = marks_map.get((t_id, sub.id), (0, 0))
            th_fm, pr_fm, th_pm, pr_pm = fm_map.get((t_id, sub.id), (0, 0, 0, 0))
            term_data['subjects'].append({
                'name': sub.subject,
                'th_fm': th_fm, 'pr_fm': pr_fm,
                'th_pm': th_pm, 'pr_pm': pr_pm,
                'th_mo': th_mo, 'pr_mo': pr_mo,
            })
        student_terms[t_id] = term_data

    ctx = _nav_context(request)
    ctx.update({
        'student': student, 'session': this_session, 'grade': std_session.grade,
        'term': this_term, 'student_terms': student_terms,
        'school': school,
    })
    return render(request, 'exam/private_result.html', ctx)


@login_required
def public_result(request):
    """Public result view with pincode verification."""
    from sms.models import Student, BranchUser, StudentSession, Subject
    from exam.models import LiveResult, SchoolTerm, ResultManagement, WeightedResultManagement
    from exam.func import _parse_weighted_term_config
    import json as _json

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    this_session = get_current_session()

    if request.method == 'POST':
        regno = request.POST.get('regno')
        code = request.POST.get('scode')

        try:
            student = Student.objects.get(reg_no=int(regno))
            if student.school != school:
                return HttpResponse("Not allowed.")
        except (Student.DoesNotExist, ValueError):
            return HttpResponse("Student not found.")

        if student.pin_code != int(code):
            return HttpResponse("Invalid pincode.")

        try:
            std_session = StudentSession.objects.get(student=student, session=this_session, status=True)
        except StudentSession.DoesNotExist:
            return HttpResponse("Student session not found.")

        result_status = LiveResult.objects.filter(school=school).first()
        if not result_status:
            return HttpResponse("Result not configured.")

        try:
            grade_list = _json.loads(result_status.grade_list)
        except Exception:
            grade_list = []

        term = result_status.term
        try:
            this_term = SchoolTerm.objects.get(id=term)
        except SchoolTerm.DoesNotExist:
            return HttpResponse("Term not found.")

        calc_type = getattr(result_status, 'calculation_type', 'legacy')
        weighted_cfg = None
        if calc_type == 'weighted':
            weighted_cfg = WeightedResultManagement.objects.filter(
                school=school, year=this_session, school_term=this_term
            ).first()

        if std_session.grade.id not in grade_list:
            return HttpResponse("Result not published for this grade.")

        # Calculate term list
        term_list = []
        weights = {}
        if calc_type == 'weighted' and weighted_cfg:
            weights, _ = _parse_weighted_term_config(weighted_cfg.weight_config, this_term.id, include_current=True)
            term_list = sorted(set([this_term.id] + list(weights.keys())))
        else:
            try:
                term_calc = ResultManagement.objects.get(school=school, year=this_session, school_term=this_term)
                term_calc_data = _json.loads(term_calc.term_calculation)
                for key, value in term_calc_data.items():
                    if int(value) > 0:
                        term_list.append(int(key))
            except (ResultManagement.DoesNotExist, _json.JSONDecodeError):
                term_list = [this_term.id]

        # Get subjects
        subjects = Subject.objects.filter(
            session=this_session, branch=school, grade=std_session.grade, status=True
        ).order_by('id')

        # Build marks map
        marks_qs = MarkObtained.objects.filter(
            school=school, session=this_session, grade=std_session.grade,
            term_id__in=term_list, student=student
        )
        marks_map = {}
        for m in marks_qs:
            marks_map[(m.term_id, m.subject_id)] = (m.th_mo or 0, m.pr_mo or 0)

        # Build full marks map
        fm_qs = GradeFullMarks.objects.filter(
            school=school, session=this_session, grade=std_session.grade, term_id__in=term_list
        )
        fm_map = {}
        for fm in fm_qs:
            fm_map[(fm.term_id, fm.subject_id)] = (fm.th_fm or 0, fm.pr_fm or 0, fm.th_pm or 0, fm.pr_pm or 0)

        student_terms = {}
        for t_id in term_list:
            try:
                t = SchoolTerm.objects.get(id=t_id)
            except SchoolTerm.DoesNotExist:
                continue
            term_data = {'term': t, 'subjects': []}
            for sub in subjects:
                th_mo, pr_mo = marks_map.get((t_id, sub.id), (0, 0))
                th_fm, pr_fm, th_pm, pr_pm = fm_map.get((t_id, sub.id), (0, 0, 0, 0))
                term_data['subjects'].append({
                    'name': sub.subject,
                    'th_fm': th_fm, 'pr_fm': pr_fm,
                    'th_pm': th_pm, 'pr_pm': pr_pm,
                    'th_mo': th_mo, 'pr_mo': pr_mo,
                })
            student_terms[t_id] = term_data

        ctx = _nav_context(request)
        ctx.update({
            'student': student, 'session': this_session, 'grade': std_session.grade,
            'term': this_term, 'student_terms': student_terms,
            'school': school, 'calc_type': calc_type,
        })
        return render(request, 'exam/public_result.html', ctx)

    # GET - show pincode form
    return render(request, 'exam/public_result_form.html', {})
