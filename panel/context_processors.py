"""
Context processor to auto-inject navigation data (grade levels, grades, branchuser)
into every template. This ensures the Tabler navbar with grade menus renders
on all pages — including print pages that previously had no nav.
"""
from sms.models import BranchUser, GradeLevel, SchoolGrade, EduSession, SchoolModuleSubscription
from django.urls import NoReverseMatch, reverse
import time

this_year = 2083

# Modules listed in the "My Apps" switcher and shown in the top header as "SIMS | <Module>".
# `color` is a Tabler color name (blue/green/purple/...), used as text-<color> / bg-<color>-lt.
# `url_name` is the optional Django URL name used for the tile link ('#' when not wired yet).
PANEL_MODULES = [
    {'key': 'student', 'label': 'Student', 'color': 'blue', 'icon': 'school', 'prefix': '/panel/', 'url_name': 'panel:index'},
    {'key': 'grihakarya', 'label': 'Grihakarya', 'color': 'green', 'icon': 'pencil', 'prefix': '/grihakarya/', 'url_name': 'grihakarya'},
    {'key': 'attendance', 'label': 'Attendance', 'color': 'purple', 'icon': 'clipboard-check', 'prefix': '/attendance/', 'url_name': 'attendance:dashboard'},
    {'key': 'cas', 'label': 'CAS', 'color': 'orange', 'icon': 'clipboard-list', 'prefix': '/cas/', 'url_name': 'cas'},
    {'key': 'billing', 'label': 'Billing', 'color': 'cyan', 'icon': 'receipt', 'prefix': '/billing/', 'url_name': 'billing'},
    {'key': 'calendar', 'label': 'Calendar', 'color': 'emerald', 'icon': 'calendar', 'prefix': '/calendar/', 'url_name': 'patro:calendar'},
]

DEFAULT_MODULE = PANEL_MODULES[0]

# Modules every school always has, regardless of subscription (cannot be unsubscribed).
CORE_MODULE_KEYS = {'student'}

# Match longer prefixes first so e.g. /panel/calendar/ wins over /panel/.
MODULES_BY_PREFIX = sorted(PANEL_MODULES, key=lambda m: len(m['prefix']), reverse=True)


def get_module_url(module):
    """Resolve a module's `url_name` to a link ('#' when it is not wired yet)."""
    if not module['url_name']:
        return '#'
    try:
        return reverse(module['url_name'])
    except NoReverseMatch:
        return '#'


def get_active_module(path):
    """Resolve the active app from the request path (falls back to Student/SIMS)."""
    for module in MODULES_BY_PREFIX:
        if path.startswith(module['prefix']):
            return {**module, 'url': get_module_url(module)}
    return {**DEFAULT_MODULE, 'url': get_module_url(DEFAULT_MODULE)}


def get_panel_modules():
    """Return PANEL_MODULES with each tile's resolved `url` link."""
    return [{**module, 'url': get_module_url(module)} for module in PANEL_MODULES]


def get_school_modules(school):
    """Return the modules visible in a school's "My Apps" switcher.

    Core modules (see CORE_MODULE_KEYS) are always included; every other module
    must have an active SchoolModuleSubscription row for the school. When no
    school is available, all modules are returned.
    """
    if school is None:
        return get_panel_modules()

    active_keys = set(
        SchoolModuleSubscription.objects
        .filter(school=school, active=True)
        .values_list('module_key', flat=True)
    )
    return [
        {**module, 'url': get_module_url(module), 'is_core': module['key'] in CORE_MODULE_KEYS}
        for module in PANEL_MODULES
        if module['key'] in CORE_MODULE_KEYS or module['key'] in active_keys
    ]


def nav_context(request):
    """Return grade_level, grades, branchuser, school, current_session, and all_sessions."""
    context = {
        'active_module': get_active_module(request.path),
        'panel_modules': get_panel_modules(),
    }

    if not request.user.is_authenticated:
        return context

    try:
        branchuser = BranchUser.objects.select_related('school').get(user=request.user)
    except BranchUser.DoesNotExist:
        return context

    school = branchuser.school
    # Only show modules the school is subscribed to (plus core modules).
    context['panel_modules'] = get_school_modules(school)
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

    # Add cache-busting logo URL
    logo_url = None
    if school.logo:
        logo_url = f"https://simsnepal.com/media/{school.logo}?v={int(time.time())}"

    return {
        'grade_level': grade_level,
        'grades': grades,
        'nav_grade_levels': grade_level,
        'nav_grades': grades,
        'branchuser': branchuser,
        'school': school,
        'school_logo_url': logo_url,
        'current_session': current_session,
        'all_sessions': all_sessions,
        **context,
    }

