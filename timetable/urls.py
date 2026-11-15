from django.urls import path
from . import views

app_name = 'timetable'

urlpatterns = [
    # Dashboard
    path('', views.timetable_dashboard, name='dashboard'),
    path('sections/', views.section_list, name='section_list'),
    path('section/<int:section_id>/', views.section_grid, name='section_grid'),
    path('teachers/', views.teacher_list, name='teacher_list'),
    path('teacher/<int:teacher_id>/', views.teacher_grid, name='teacher_grid'),

    # Management
    path('manage/', views.timetable_management, name='management'),
    path('manage/profiles/', views.profile_list, name='profile_list'),
    path('manage/profiles/add/', views.profile_add, name='profile_add'),
    path('manage/profiles/<int:profile_id>/periods/', views.profile_periods, name='profile_periods'),
    path('manage/profiles/<int:profile_id>/periods/add/', views.period_add, name='period_add'),
    path('manage/versions/', views.version_list, name='version_list'),
    path('manage/versions/add/', views.version_add, name='version_add'),
    path('manage/sections/<int:section_id>/entries/', views.entry_list, name='entry_list'),
    path('manage/sections/<int:section_id>/entries/add/', views.entry_add, name='entry_add'),
    path('manage/holidays/', views.holiday_list, name='holiday_list'),
    path('manage/holidays/add/', views.holiday_add, name='holiday_add'),
    path('manage/exceptions/', views.exception_list, name='exception_list'),
    path('manage/exceptions/add/', views.exception_add, name='exception_add'),

    # Grade Structures (standard class schedules per grade/shift)
    path('manage/structures/', views.grade_structure_list, name='grade_structure_list'),
    path('manage/structures/add/', views.grade_structure_add, name='grade_structure_add'),
    path('manage/structures/<int:structure_id>/periods/', views.grade_structure_periods, name='grade_structure_periods'),
    path('manage/structures/<int:structure_id>/periods/add/', views.grade_structure_period_add, name='grade_structure_period_add'),

    # School-Level Timetable Settings (global shifts, class times, etc.)
    path('manage/settings/', views.school_settings, name='school_settings'),
    path('manage/settings/edit/', views.school_settings_edit, name='school_settings_edit'),
]
