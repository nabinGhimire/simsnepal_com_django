from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.attendance_dashboard, name='dashboard'),
    path('print/', views.print_sheet, name='print_sheet'),
    path('daily-report/', views.daily_report, name='daily_report'),
    path('monthly-report/', views.monthly_report, name='monthly_report'),
    path('yearly-report/', views.yearly_report, name='yearly_report'),
    path('transfer-date/', views.transfer_attendance_date, name='transfer_date'),
    path('bulk-backfill/', views.bulk_backfill_attendance, name='bulk_backfill'),
    path('student-search/', views.student_search, name='student_search'),
    path('student/<str:reg_no>/', views.student_attendance_profile, name='student_profile'),
    path('export-monthly-excel/', views.export_monthly_excel, name='export_monthly_excel'),
    path('export-yearly-excel/', views.export_yearly_excel, name='export_yearly_excel'),
    path('export-daily-excel/', views.export_daily_excel, name='export_daily_excel'),
    path('settings/', views.attendance_settings, name='settings'),
]
