from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    # Курсы
    path('', views.course_list, name='course_list'),
    path('create/', views.course_create, name='course_create'),
    path('<int:course_id>/', views.course_detail, name='course_detail'),
    path('<int:course_id>/edit/', views.course_edit, name='course_edit'),
    path('<int:course_id>/delete/', views.course_delete, name='course_delete'),
    
    # Уроки
    path('<int:course_id>/lesson/create/', views.lesson_create, name='lesson_create'),
    path('<int:course_id>/lesson/<int:lesson_id>/edit/', views.lesson_edit, name='lesson_edit'),
    path('<int:course_id>/lesson/<int:lesson_id>/delete/', views.lesson_delete, name='lesson_delete'),
    
    # Задания в уроках
    path('<int:course_id>/lesson/<int:lesson_id>/tasks/', views.lesson_tasks, name='lesson_tasks'),
    path('<int:course_id>/lesson/<int:lesson_id>/add-tasks/', views.add_tasks_to_lesson, name='add_tasks_to_lesson'),
    path('<int:course_id>/lesson/<int:lesson_id>/add-task/<int:task_id>/', views.add_task_to_lesson, name='add_task_to_lesson'),
    path('<int:course_id>/lesson/<int:lesson_id>/remove-task/<int:task_id>/', views.remove_task_from_lesson, name='remove_task_from_lesson'),
    
    # Блоки курса
    path('<int:course_id>/blocks/', views.course_blocks, name='course_blocks'),
    path('<int:course_id>/block/create/', views.create_block, name='create_block'),
    path('<int:course_id>/block/<int:block_id>/edit/', views.edit_block, name='edit_block'),
    path('<int:course_id>/block/<int:block_id>/delete/', views.delete_block, name='delete_block'),
    
    # Назначение уроков группам
    path('lesson-assignments/', views.lesson_assignments, name='lesson_assignments'),
    path('<int:course_id>/lessons-for-assignment/', views.course_lessons_for_assignment, name='course_lessons_for_assignment'),
    path('<int:course_id>/lesson/<int:lesson_id>/assign/', views.assign_lesson, name='assign_lesson'),
    path('<int:course_id>/lesson/<int:lesson_id>/assignments/', views.lesson_assignments_list, name='lesson_assignments_list'),
    path('<int:course_id>/lesson/<int:lesson_id>/statistics/', views.lesson_statistics, name='lesson_statistics'),
    path('<int:course_id>/lesson/<int:lesson_id>/unassign/<int:assignment_id>/', views.unassign_lesson, name='unassign_lesson'),
    
    # Выполнение уроков учениками
    path('execute/<int:execution_id>/', views.start_lesson, name='start_lesson'),
    path('execute/<int:execution_id>/save-answer/<int:task_id>/', views.save_task_answer, name='save_task_answer'),
    path('execute/<int:execution_id>/next/', views.next_task, name='next_task'),
    path('execute/<int:execution_id>/prev/', views.prev_task, name='prev_task'),
    path('execute/<int:execution_id>/complete/', views.complete_lesson, name='complete_lesson'),
    path('completed/<int:execution_id>/', views.view_completed_lesson, name='view_completed_lesson'),
    
    # Варианты контрольных работ
    path('<int:course_id>/lesson/<int:lesson_id>/generate-variants/', views.generate_control_variants, name='generate_control_variants'),
    path('<int:course_id>/lesson/<int:lesson_id>/variants/', views.control_variants, name='control_variants'),
    path('<int:course_id>/lesson/<int:lesson_id>/assign-variants/', views.assign_variants, name='assign_variants'),
    
    # Многоэтапное создание контрольных работ
    path('<int:course_id>/control-wizard/', views.control_lesson_wizard, name='control_lesson_wizard'),
    path('<int:course_id>/control-wizard/<int:step>/', views.control_lesson_wizard, name='control_lesson_wizard'),
    path('<int:course_id>/control-wizard/reset/', views.control_lesson_wizard_reset, name='control_lesson_wizard_reset'),
    path('<int:course_id>/load-tasks-ajax/', views.load_tasks_ajax, name='load_tasks_ajax'),
]
