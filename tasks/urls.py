from django.urls import path
from . import views

urlpatterns = [
    path('', views.task_list, name='task_list'),
    path('add/', views.add_task, name='add_task'),
    path('bulk-import/', views.bulk_import, name='bulk_import'),
    path('delete-session/<uuid:session_id>/', views.delete_session_tasks, name='delete_session_tasks'),
    path('edit/<int:task_id>/', views.edit_task, name='edit_task'),
    path('delete/<int:task_id>/', views.delete_task, name='delete_task'),
    path('detail/<int:task_id>/', views.task_detail, name='task_detail'),
]
