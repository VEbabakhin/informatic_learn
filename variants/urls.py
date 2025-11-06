from django.urls import path
from . import views

app_name = 'variants'

urlpatterns = [
    path('', views.variant_list, name='variant_list'),
    path('create-choice/', views.variant_create_choice, name='variant_create_choice'),
    path('create-from-template/', views.variant_create_from_template, name='variant_create_from_template'),
    path('create-from-tasks/', views.variant_create_from_specific_tasks, name='variant_create_from_specific_tasks'),
    path('<int:variant_id>/', views.variant_detail, name='variant_detail'),
    path('<int:variant_id>/delete/', views.variant_delete, name='variant_delete'),
    path('<int:variant_id>/start/', views.variant_start, name='variant_start'),
    path('<int:variant_id>/statistics/', views.variant_statistics, name='variant_statistics'),
    path('execute/<int:execution_id>/', views.variant_execute, name='variant_execute'),
    path('result/<int:execution_id>/', views.variant_result, name='variant_result'),
    path('executions/', views.variant_execution_list, name='variant_execution_list'),
    path('save-answer/<int:execution_id>/', views.save_answer, name='save_answer'),
    path('assign-to-student/', views.assign_variant_to_student, name='assign_variant_to_student'),
    path('assign-to-group/', views.assign_variants_to_group, name='assign_variants_to_group'),
    path('start-by-number/', views.variant_start_by_number, name='variant_start_by_number'),
]


