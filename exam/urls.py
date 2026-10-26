from django.urls import path
from exam import views

app_name = 'exam'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    # Terms
    path('terms/', views.terms_list, name='terms'),
    # Full marks
    path('fullmarks/', views.fullmarks, name='fullmarks'),
    path('addfullmarks/<grade>/<term>/', views.addfullmarks, name='addfullmarks'),
    path('addfullmarks/<grade>/<term>/edit/', views.addfullmarksedit, name='addfullmarksedit'),
    path('inputfullmarksredirector/', views.inputfullmarksredirector, name='inputfullmarksredirector'),
    # Subject-wise marks
    path('subjectwise/', views.subjectwisemarks, name='subjectwisemarks'),
    path('subjectwisemarksentry/', views.subject_wise_marks_entry, name='subject_wise_mark_sentry'),
    # Results
    path('result/', views.resultmanagement, name='resultmanagement'),
    path('terms/weighted-calculation/', views.weighted_result_calculation, name='weighted_result_calculation'),
    # Print
    path('print/data/', views.printmarksform, name='printmarksform'),
    path('print/marksgradesheet/', views.marksgradesheet, name='marksgradesheet'),
    path('print/marksgradesheet42079/', views.printgradesheetnow2079, name='marksgradesheet42079'),
    path('print/ledger/grade/', views.print_grade_ledger_exam, name='print_grade_ledger'),
    # Result status / public result
    path('status/result/<regno>/', views.flip_status_result, name='flip_status_result'),
    path('privateresult/<regno>/', views.new_private_result_2080, name='school_private'),
    path('publicresult/', views.new_public_result_2079, name='school_public'),
    # Settings
    path('settings/', views.settings, name='settings'),
]
