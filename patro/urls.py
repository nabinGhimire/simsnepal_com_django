from django.urls import path
from . import views

app_name = 'patro'

urlpatterns = [
    path('', views.calendar, name='calendar'),
]
