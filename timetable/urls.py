from django.urls import path
from . import views

app_name = 'timetable'

urlpatterns = [
    path('section/<int:section_id>/', views.section_grid, name='section_grid'),
    path('teacher/<int:teacher_id>/', views.teacher_grid, name='teacher_grid'),
]
