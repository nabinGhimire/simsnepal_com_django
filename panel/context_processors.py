"""
Context processor to auto-inject navigation data (grade levels, grades, branchuser)
into every template. This ensures the Tabler navbar with grade menus renders
on all pages — including print pages that previously had no nav.
"""
from sms.models import BranchUser, GradeLevel, SchoolGrade


def nav_context(request):
    """Return grade_level, grades, branchuser, and school for the authenticated user."""
    if not request.user.is_authenticated:
        return {}

    try:
        branchuser = BranchUser.objects.select_related('school').get(user=request.user)
    except BranchUser.DoesNotExist:
        return {}

    school = branchuser.school
    grade_level = GradeLevel.objects.filter(schoolgrade__school=school, schoolgrade__active=True).distinct().order_by('id')
    grades = SchoolGrade.objects.filter(school=school, active=True).order_by('grade_weight')

    return {
        'grade_level': grade_level,
        'grades': grades,
        'nav_grade_levels': grade_level,
        'nav_grades': grades,
        'branchuser': branchuser,
        'school': school,
    }
