from django.urls import path
from . import views

urlpatterns = [
    path('auto-login/', views.auto_login, name='auto_login'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('logout/', views.logout_user, name='logout'),
]
