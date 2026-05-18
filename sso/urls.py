from django.urls import path
from . import views

urlpatterns = [
    path('', views.auto_login, name='auto_login_root'),
    path('auto-login/', views.auto_login, name='auto_login'),
    path('dashboard/', views.dashboard, name='dashboard'),
]
