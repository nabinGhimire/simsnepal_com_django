from django.urls import path

from . import views

app_name = 'grihakarya'

urlpatterns = [
    path('', views.grihakarya_homework_dashboard, name='dashboard'),
    path('homeworks/', views.grihakarya_homework_list, name='homeworks'),
    path('entries/<int:pk>/edit/', views.grihakarya_edit_entry, name='edit_entry'),
    path('entries/<int:pk>/history/', views.grihakarya_entry_history, name='entry_history'),

    path('complains/', views.grihakarya_complaints, name='complains'),
    path('complains/add/', views.grihakarya_add_complain, name='add_complain'),
    path('complains/<int:pk>/resolve/', views.grihakarya_resolve_complain, name='resolve_complain'),
]
