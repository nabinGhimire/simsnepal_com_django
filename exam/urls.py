from django.urls import path
from exam import views

app_name = 'exam'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    # Full marks management
    path('fullmarks/', views.fullmarks, name='fullmarks'),
    path('subjectwise/', views.subjectwisemarks, name='subjectwisemarks'),
    # Exam Terms
    path('terms/', views.terms_list, name='terms'),
    path('terms/weighted-calculation/', views.weighted_result_calculation, name='weighted_result_calculation'),
    path('result/', views.resultmanagement, name='resultmanagement'),
    # Print marks forms
    path('print/data/', views.printmarksform, name='printmarksform'),
    path('print/marksgradesheet/', views.marksgradesheet, name='marksgradesheet'),
    path('print/marksgradesheet42079/', views.printgradesheetnow2079, name='marksgradesheet42079'),
    path('print/ledger/grade/', views.print_grade_ledger_exam, name='print_grade_ledger'),
    # Input Full Marks
    path('inputfullmarksredirector/', views.inputfullmarksredirector, name='inputfullmarksredirector'),
    path('addfullmarks/<grade>/<term>/', views.addfullmarks, name='addfullmarks'),
    path('addfullmarks/<grade>/<term>/edit/', views.addfullmarksedit, name='addfullmarksedit'),
    # Result status
    path('status/result/<regno>/', views.flip_status_result, name='flip_status_result'),
    path('privateresult/<regno>/', views.new_private_result_2080, name='school_private'),
    path('publicresult/', views.new_public_result_2079, name='school_public'),
    # Subject-wise Marks Entry
    path('subjectwisemarksentry/', views.subject_wise_marks_entry, name='subject_wise_mark_sentry'),
    # Exam Settings
    path('settings/', views.settings, name='settings'),
]