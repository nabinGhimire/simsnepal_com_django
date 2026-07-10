from django.urls import path
from . import views

urlpatterns = [
    path("api/auth-token/", views.generate_auth_token, name="generate_auth_token"),
    path("parent/homework/", views.parent_homework, name="parent_homework"),
    path("parent/result/", views.parent_result, name="parent_result"),
    path("teacher/homework/", views.teacher_homework, name="teacher_homework"),
    path("teacher/marks/", views.teacher_marks, name="teacher_marks"),
    path("teacher/marks/entry/", views.teacher_marks_entry, name="teacher_marks_entry"),
]
