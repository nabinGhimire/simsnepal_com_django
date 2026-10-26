"""
Exam app views.
All views render exam/ templates with the attendance-style design system.
"""
import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib import messages

# Re-use panel helpers — they are lightweight and don't render anything
from panel.views import get_branch_info, get_current_session

# Import print/result views that produce standalone print pages
# (these render their own full-page HTML — no exam navbar needed)
from panel.views import (
    printmarksform as _panel_printmarksform,
    printgradesheetnow2079,
    print_grade_ledger_exam as _panel_print_grade_ledger,
    flip_status_result,
    new_private_result_2080,
    new_public_result_2079,
    inputfullmarksredirector,
)


def _nav_context(request):
    """Common context for exam navbar — grades, levels."""
    from sms.models import SchoolGrade, GradeLevel, BranchUser
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
    from sms.models import SchoolTerm, SchoolGrade, GradeLevel, GradeFullMarks, Subject, LiveResult

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    current_session = get_current_session()

    exam_terms = SchoolTerm.objects.filter(school=school, year=current_session, active=True) if current_session else []
    grades = SchoolGrade.objects.filter(school=school, active=True).select_related('level').order_by('level__id', 'grade_weight', 'grade_name')
    level_ids = grades.values_list('level_id', flat=True).distinct()
    levels = list(GradeLevel.objects.filter(id__in=level_ids).order_by('id'))

    # Quick stats per term
    term_stats = []
    for term in exam_terms:
        grade_count = grades.count()
        fm_count = GradeFullMarks.objects.filter(school=school, session=current_session, term=term).values('grade').distinct().count()
        term_stats.append({'term': term, 'grades_configured': fm_count, 'total_grades': grade_count})

    live_result = LiveResult.objects.filter(school=school).first()

    context = {
        'current_session': current_session,
        'exam_terms': exam_terms,
        'term_stats': term_stats,
        'school': school,
        'branchuser': branchuser,
        'nav_grades': grades,
        'nav_grade_levels': levels,
        'live_result': live_result,
    }
    return render(request, 'exam/dashboard.html', context)


# ── Terms ────────────────────────────────────────────────────────────────────

@login_required
def terms_list(request):
    from sms.models import SchoolTerm, SchoolGrade, SchoolTermStatus

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    current_session = get_current_session()

    action = request.GET.get('action', 'listterm')

    if action == 'addterm':
        if request.method == 'POST':
            term_name = request.POST.get('term_name', '').strip()
            name_in_short = request.POST.get('name_in_short', '').strip() or None
            year_id = request.POST.get('year_id')
            grade_id = request.POST.get('grade_id')
            final_term = request.POST.get('final_term') == 'on'
            status_id = request.POST.get('status', '1')

            if term_name and year_id:
                SchoolTerm.objects.create(
                    school=school,
                    year_id=year_id,
                    term_name=term_name,
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
        })
        return render(request, 'exam/terms_list.html', ctx)

    exam_terms = SchoolTerm.objects.filter(school=school, active=True).order_by('id') if school else []
    ctx = _nav_context(request)
    ctx.update({
        'exam_terms': exam_terms,
        'school': school,
        'branchuser': branchuser,
        'current_session': current_session,
        'is_terms': True,
        'action': 'listterm',
    })
    return render(request, 'exam/terms_list.html', ctx)


# ── Full Marks ───────────────────────────────────────────────────────────────

@login_required
def fullmarks(request):
    from sms.models import SchoolTerm, SchoolGrade

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
    from sms.models import SchoolTerm, SchoolGrade, Subject, GradeFullMarks

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
    from sms.models import SchoolTerm, SchoolGrade, Subject, GradeFullMarks

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
        return redirect(f'/exam/addfullmarks/{grade_obj.id}/{exam_term.id}/')

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
    from sms.models import SchoolTerm, SchoolGrade, Section
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

    if request.method == 'POST':
        term_id = request.POST.get('term')
        grade_id = request.POST.get('grade')
        section_id = request.POST.get('section')
        order = request.POST.get('order', 1)
        # Build subject list for the selected grade
        from sms.models import Subject
        selected_grade = SchoolGrade.objects.get(id=grade_id)
        subjects = Subject.objects.filter(branch=school, grade=selected_grade, status=True).order_by('id')
        ctx = _nav_context(request)
        ctx.update({
            'exam_types': exam_types, 'grades': grades, 'school': school,
            'branchuser': branchuser, 'this_year': current_session.year if current_session else '',
            'section_list': section_list_json, 'is_exam_subject': True,
            'selected_grade': selected_grade, 'term_id': term_id,
            'grade_id': grade_id, 'section_id': section_id, 'order': order,
            'subjects': subjects,
        })
        return render(request, 'exam/subjectwisemarks.html', ctx)

    ctx = _nav_context(request)
    ctx.update({
        'exam_types': exam_types, 'grades': grades, 'school': school,
        'branchuser': branchuser, 'this_year': current_session.year if current_session else '',
        'section_list': section_list_json, 'is_exam_subject': True,
    })
    return render(request, 'exam/subjectwisemarks.html', ctx)


@login_required
def subject_wise_marks_entry(request):
    """Actual marks entry form — delegate to panel view which renders panel/subjectwisemarksform.html."""
    from panel.views import subject_wise_marks_entry as _panel_sw
    return _panel_sw(request)


# ── Result Management ────────────────────────────────────────────────────────

@login_required
def resultmanagement(request):
    from sms.models import (
        SchoolTerm, SchoolGrade, GradeLevel, SchoolResultType,
        LiveResult, ResultManagement
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
            calculation_type = request.POST.get('calculation_type', 'legacy')
            checks = json.dumps([int(i) for i in request.POST.getlist('checks[]')])
            LiveResult.objects.update_or_create(
                school=school,
                defaults={'term': examtype, 'grade_list': checks, 'status': livestatus, 'calculation_type': calculation_type}
            )
            live_result_status = livestatus
        return redirect('exam:resultmanagement')

    schoolresulttype = SchoolResultType.objects.filter(school=school, session=current_session).first()
    sr = schoolresulttype

    rm_qs = ResultManagement.objects.filter(school=school, year=current_session)
    resultmanagement_exists = rm_qs.exists()

    gradelist = []
    if live_result_obj:
        try:
            gradelist = json.loads(live_result_obj.grade_list)
        except Exception:
            gradelist = []

    ctx = _nav_context(request)
    ctx.update({
        'grades': grades, 'gradelist': gradelist, 'branchuser': branchuser,
        'exam_types': exam_types, 'schoolresulttype': bool(schoolresulttype),
        'sr': sr, 'live_result_status': live_result_status,
        'resultmanagement': resultmanagement_exists,
        'rm': rm_qs, 'school': school, 'live_calc_type': live_calc_type,
        'current_session': current_session,
        'is_exam_result': 'manage',
    })
    return render(request, 'exam/resultmanagement.html', ctx)


@login_required
def weighted_result_calculation(request):
    from sms.models import SchoolTerm, SchoolGrade, GradeLevel, LiveResult, WeightedResultManagement

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
                config = json.loads(config)
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
        'terms': terms, 'wc_dic': json.dumps(wc_dic), 'live_calc_type': live_calc_type,
        'current_session': current_session,
        'is_exam_result': 'weighted',
    })
    return render(request, 'exam/weighted_result_calculation.html', ctx)


# ── Print / Grade Sheet ──────────────────────────────────────────────────────

@login_required
def printmarksform(request):
    """Selection form GET; on POST delegates to panel print view."""
    if request.method == 'POST':
        return _panel_printmarksform(request)

    from sms.models import SchoolTerm, SchoolGrade, Section
    import json as _json

    branchuser, error = get_branch_info(request.user)
    if error:
        return HttpResponse(error)

    school = branchuser.school
    current_session = get_current_session()

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


@login_required
def marksgradesheet(request):
    """Selection form GET; on POST delegates to panel (renders print page)."""
    if request.method == 'POST':
        from panel.views import marksgradesheet as _panel_mgs
        return _panel_mgs(request)

    from sms.models import SchoolTerm, SchoolGrade, EduSession, Section, LiveResult
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
    """Selection form GET; on POST delegates to panel (renders print page)."""
    if request.method == 'POST':
        return _panel_print_grade_ledger(request)

    from sms.models import SchoolTerm, SchoolGrade, EduSession, Section, LiveResult
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

    ctx = _nav_context(request)
    ctx.update({
        'edusession': edusession_all, 'current_session': current_session,
        'exam_types': exam_types, 'section_list': _json.dumps(section_list),
        'term_list': _json.dumps(term_dict), 'school': school, 'grades': grades,
        'branchuser': branchuser, 'live_calc_type': live_calc_type,
        'is_exam_print': 'ledger',
    })
    return render(request, 'exam/print_grade_ledger.html', ctx)


# ── Pass-through views (render standalone print pages — no exam navbar) ──────

@login_required
def printgradesheetnow2079(request):
    from panel.views import printgradesheetnow2079 as _p
    return _p(request)


# ── Settings ─────────────────────────────────────────────────────────────────

@login_required
def settings(request):
    from sms.models import SchoolTerminology

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
        messages.success(request, 'Settings saved.')
        return redirect('exam:settings')

    ctx = _nav_context(request)
    ctx.update({
        'school': school, 'branchuser': branchuser,
        'terminology': terminology,
        'is_settings': True,
    })
    return render(request, 'exam/settings.html', ctx)
