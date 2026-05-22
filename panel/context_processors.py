"""
Context processor to auto-inject navigation data (grade levels, grades, branchuser)
into every template. This ensures the Tabler navbar with grade menus renders
on all pages — including print pages that previously had no nav.
"""
from sms.models import BranchUser, GradeLevel, SchoolGrade, EduSession
this_year = 2083

def nav_context(request):
    """Return grade_level, grades, branchuser, school, current_session, and all_sessions."""
    if not request.user.is_authenticated:
        return {}

    try:
        branchuser = BranchUser.objects.select_related('school').get(user=request.user)
    except BranchUser.DoesNotExist:
        return {}

    school = branchuser.school
    grade_level = GradeLevel.objects.filter(schoolgrade__school=school, schoolgrade__active=True).distinct().order_by('id')
    grades = SchoolGrade.objects.filter(school=school, active=True).order_by('grade_weight')

    # Retrieve current session from the session store
    active_session_id = request.session.get('active_session_id')
    current_session = None
    if active_session_id:
        try:
            current_session = EduSession.objects.get(id=active_session_id)
        except EduSession.DoesNotExist:
            pass

    if not current_session:
        try:
            current_session = EduSession.objects.get(year=this_year)
        except EduSession.DoesNotExist:
            current_session = EduSession.objects.filter(status=True).order_by('-year').first()

    all_sessions = EduSession.objects.all().order_by('-year')

    return {
        'grade_level': grade_level,
        'grades': grades,
        'nav_grade_levels': grade_level,
        'nav_grades': grades,
        'branchuser': branchuser,
        'school': school,
        'current_session': current_session,
        'all_sessions': all_sessions,
    }

