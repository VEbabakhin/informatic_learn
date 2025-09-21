from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('users/', views.user_list, name='user_list'),
    path('add-teacher/', views.add_teacher, name='add_teacher'),
    path('add-student/', views.add_student, name='add_student'),
    path('delete-user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('groups/', views.group_list, name='group_list'),
    path('create-group/', views.create_group, name='create_group'),
    path('add-students-to-group/<int:group_id>/', views.add_students_to_group, name='add_students_to_group'),
    path('group/<int:group_id>/', views.group_detail, name='group_detail'),
    path('edit-group/<int:group_id>/', views.edit_group, name='edit_group'),
    path('delete-group/<int:group_id>/', views.delete_group, name='delete_group'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('change-password/', views.change_password, name='change_password'),
    path('edit-user/<int:user_id>/', views.edit_user, name='edit_user'),
    path('reset-password/<int:user_id>/', views.reset_password, name='reset_password'),
    path('set-selected-group/', views.set_selected_group, name='set_selected_group'),
    path('clear-selected-group/', views.clear_selected_group, name='clear_selected_group'),
    path('logout/', views.logout_view, name='logout'),
    path('add-student-to-group/<int:group_id>/<int:student_id>/', views.add_student_to_group, name='add_student_to_group'),
    path('remove-student-from-group/<int:group_id>/<int:student_id>/', views.remove_student_from_group, name='remove_student_from_group'),
]
