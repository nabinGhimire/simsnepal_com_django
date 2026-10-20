from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from panel.views import (
    fullmarks, subjectwisemarksformbase as subjectwisemarks, weighted_result_calculation,
    resultmanagement, printmarksform, marksgradesheet, printgradesheetnow2079,
    print_grade_ledger_exam, inputfullmarksredirector, addfullmarks, addfullmarksedit,
    flip_status_result, new_private_result_2080, new_public_result_2079,
    subject_wise_marks_entry
)


@login_required
def dashboard(request):
    """Exam management dashboard - overview of exam terms, results, and marks entry."""
    from sms.models import SchoolTerm, BranchUser

    # Get current session
    active_session_id = request.session.get('active_session_id')
    current_session = None
    if active_session_id:
        try:
            from sms.models import EduSession as SessionModel
            current_session = SessionModel.objects.get(id=active_session_id)
        except Exception:
            pass

    if not current_session:
        try:
            from sms.models import EduSession as SessionModel2
            current_session = SessionModel2.objects.get(year=2083)
        except Exception:
            current_session = None

    # Get exam terms for the school
    school = None
    branch_user = None
    try:
        branch_user = BranchUser.objects.select_related('school').get(user=request.user)
        school = branch_user.school
    except Exception:
        pass

    exam_terms = SchoolTerm.objects.filter(school=school, year=current_session.year, active=True) if school else []

    context = {
        'current_session': current_session,
        'exam_terms': exam_terms,
        'school': school,
        'branch_user': branch_user,
        # Sidebar context variables
        'is_exam_fullmarks': False,
        'is_exam_result': False,
        'is_exam_print': False,
        'is_exam_input': False,
        'is_exam_subject': False,
        'is_settings': False,
    }
    return render(request, 'exam/dashboard.html', context)


@login_required
def terms_list(request):
    """List exam terms for the school."""
    from sms.models import SchoolTerm, BranchUser

    school = None
    try:
        branch_user = BranchUser.objects.select_related('school').get(user=request.user)
        school = branch_user.school
    except Exception:
        pass

    exam_terms = SchoolTerm.objects.filter(school=school, active=True) if school else []

    context = {
        'exam_terms': exam_terms,
        'school': school,
    }
    return render(request, 'exam/terms_list.html', context)


@login_required
def settings(request):
    """Exam settings page."""
    return render(request, 'exam/settings.html', {
        'title': 'Exam Settings',
        'is_settings': True,
    })