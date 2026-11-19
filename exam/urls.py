from django.urls import path
from django.shortcuts import redirect
from exam import views

app_name = 'exam'

# ── Redirect views for legacy URLs ──────────────────────────────────────────────

def _redirect_dashboard(request):
    return redirect('exam:dashboard')

def _redirect_terms(request):
    return redirect('exam:terms')

def _redirect_full_marks(request):
    return redirect('exam:full_marks')

def _redirect_printmarksform(request):
    return redirect('exam:marks_input_form')

def _redirect_marks_input_form(request):
    return redirect('exam:marks_input_form')

def _redirect_marks_grade_sheet(request):
    return redirect('exam:marks_grade_sheet')

def _redirect_marks_grade_sheet_2079(request):
    return redirect('exam:marks_grade_sheet_2079')

def _redirect_grade_ledger(request):
    return redirect('exam:grade_ledger')

def _redirect_result_status(request, regno):
    return redirect('exam:result_status', regno=regno)

def _redirect_private_result(request, regno):
    return redirect('exam:private_result', regno=regno)

def _redirect_public_result(request):
    return redirect('exam:public_result')


urlpatterns = [
    # ── Dashboard ───────────────────────────────────────────────────────────────
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', _redirect_dashboard, name='dashboard_redirect'),

    # ── Terms ───────────────────────────────────────────────────────────────────
    path('terms/', views.terms_list, name='terms'),
    path('terms/add/', views.terms_list, name='add_term'),
    path('terms/<int:term_id>/edit/', views.terms_list, name='edit_term'),
    path('terms/<int:term_id>/calculation/', views.terms_list, name='term_calculation'),
    path('terms/weighted/', views.weighted_result_calculation, name='weighted_calculation'),

    # ── Full Marks ───────────────────────────────────────────────────────────────
    path('full-marks/', views.fullmarks, name='full_marks'),
    path('full-marks/<int:grade>/<int:term>/', views.addfullmarks, name='add_full_marks'),
    path('full-marks/<int:grade>/<int:term>/edit/', views.addfullmarksedit, name='edit_full_marks'),
    path('inputfullmarksredirector/', views.inputfullmarksredirector, name='inputfullmarksredirector'),

    # ── Subject-wise Marks ────────────────────────────────────────────────────────
    path('marks-entry/subject-wise/', views.subjectwisemarks, name='subject_wise_marks'),
    path('marks-entry/subject-wise/save/', views.subject_wise_marks_entry, name='save_subject_wise_marks'),

    # ── Results ───────────────────────────────────────────────────────────────────
    path('result/', views.resultmanagement, name='publish_result'),

    # ── Settings ─────────────────────────────────────────────────────────────────
    path('settings/', views.settings, name='settings'),
    path('settings/terminologies/', views.settings_terminologies, name='settings_terminologies'),
    path('settings/result-config/', views.resultmanagement, name='grade_result_config'),

    # ── Print / Ledger / Entrance Card ───────────────────────────────────────────
    path('print/marks-input-form/', views.printmarksform, name='marks_input_form'),
    path('print/marks-grade-sheet/', views.marksgradesheet, name='marks_grade_sheet'),
    path('print/marks-grade-sheet-2079/', views.printgradesheetnow2079, name='marks_grade_sheet_2079'),
    path('print/grade-ledger/', views.print_grade_ledger_exam, name='grade_ledger'),
    path('print/result/', views.print_result, name='print_result'),
    path('print/ledger/', views.print_ledger, name='print_ledger'),
    path('print/ledger/preview/', views.print_ledger_preview, name='print_ledger_preview'),
    path('print/ledger/now/', views.print_ledger_now, name='print_ledger_now'),
    path('print/entrancecard/', views.print_entrance_card, name='print_entrance_card'),

    # ── Result status / public result ─────────────────────────────────────────────
    path('result-status/<str:regno>/', views.result_status, name='result_status'),
    path('private-result/<str:regno>/', views.private_result, name='private_result'),
    path('public-result/', views.public_result, name='public_result'),
]

# ── Legacy redirects (old URLs → new URLs) ──────────────────────────────────────
urlpatterns += [
    path('cas/', _redirect_dashboard, name='cas_redirect'),
    path('billing/', _redirect_dashboard, name='billing_redirect'),
    path('calendar/', _redirect_dashboard, name='calendar_redirect'),
    path('print/data/', _redirect_marks_input_form, name='printmarksform_redirect'),
    path('print/marksgradesheet/', _redirect_marks_grade_sheet, name='marksgradesheet_redirect'),
    path('print/marksgradesheet42079/', _redirect_marks_grade_sheet_2079, name='marksgradesheet42079_redirect'),
    path('print/ledger/grade/', _redirect_grade_ledger, name='print_grade_ledger_redirect'),
    path('status/result/<str:regno>/', _redirect_result_status, name='flip_status_result_redirect'),
    path('privateresult/<str:regno>/', _redirect_private_result, name='school_private_redirect'),
    path('publicresult/', _redirect_public_result, name='school_public_redirect'),
]
