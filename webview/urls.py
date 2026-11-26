from django.urls import path
from . import views

urlpatterns = [
    path("api/auth-token/", views.generate_auth_token, name="generate_auth_token"),
    path("parent/homework/", views.parent_homework, name="parent_homework"),
    path("parent/result/", views.parent_result, name="parent_result"),
    path("parent/result/detail/", views.parent_result_detail, name="parent_result_detail"),
    path("teacher/attendance/", views.teacher_attendance, name="teacher_attendance"),
    path("teacher/concerns/", views.teacher_concerns, name="teacher_concerns"),
]