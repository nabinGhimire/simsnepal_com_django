from django.urls import path

from . import views

app_name = 'concerns'

urlpatterns = [
    # Admin dashboard
    path('', views.concerns_dashboard, name='dashboard'),
    path('remarks/', views.remark_list, name='remark_list'),
    path('remarks/add/', views.remark_add, name='remark_add'),
    path('student-search/', views.student_search_api, name='student_search_api'),
    path('student-detail/', views.student_detail_api, name='student_detail_api'),
    path('remarks/<int:pk>/escalate/', views.escalate_remark, name='escalate_remark'),
    path('remarks/<int:pk>/dismiss/', views.dismiss_remark, name='dismiss_remark'),
    path('remarks/<int:pk>/toggle-visibility/', views.toggle_remark_visibility, name='toggle_visibility'),
    path('remarks/<int:pk>/convert/', views.convert_remark_to_concern, name='convert_to_concern'),
    path('remarks/<int:pk>/detail/', views.remark_detail_api, name='remark_detail_api'),

    # Concerns
    path('concerns/', views.concern_list, name='concern_list'),
    path('concerns/add/', views.concern_add, name='concern_add'),
    path('concerns/<int:pk>/', views.concern_detail, name='concern_detail'),
    path('concerns/<int:pk>/status/', views.concern_update_status, name='concern_status'),
    path('concerns/<int:pk>/comm/', views.concern_add_comm, name='concern_add_comm'),
    path('concerns/<int:pk>/detail/', views.concern_detail_api, name='concern_detail_api'),

    # Per-student view
    path('student/<str:regno>/', views.student_concerns, name='student_concerns'),

    # Templates management
    path('templates/', views.template_list, name='template_list'),
    path('templates/add/', views.template_add, name='template_add'),
    path('templates/<int:pk>/delete/', views.template_delete, name='template_delete'),
]
