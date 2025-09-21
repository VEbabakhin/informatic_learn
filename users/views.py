from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from .models import User, Group, UserGroup
from .forms import AddTeacherForm, AddStudentForm, CreateGroupForm, AddStudentsToGroupForm, EditGroupForm, RemoveStudentsFromGroupForm, SimpleGroupEditForm

@login_required
def dashboard(request):
    """Главная страница платформы"""
    # Для учителей и администраторов перенаправляем на страницу "Занятия"
    if request.user.role in ['admin', 'teacher']:
        return redirect('courses:lesson_assignments')
    
    # Для учеников показываем назначенные уроки
    context = {
        'user': request.user,
    }
    
    if request.user.role == 'student':
        from courses.models import LessonAssignment, LessonExecution
        from django.utils import timezone
        
        # Получаем группы ученика
        user_groups = Group.objects.filter(students=request.user)
        
        # Отладочная информация о группах ученика
        print(f"DEBUG: Пользователь {request.user.username} состоит в группах: {[g.name for g in user_groups]}")
        
        # Получаем активные назначения уроков для групп ученика
        assigned_lessons = LessonAssignment.objects.filter(
            group__in=user_groups,
            is_active=True
        ).select_related('lesson', 'lesson__course', 'assigned_by').order_by('-assigned_at')
        
        # Отладочная информация
        print(f"DEBUG: Найдено {assigned_lessons.count()} активных назначений для пользователя {request.user.username}")
        for assignment in assigned_lessons:
            print(f"DEBUG: Назначение ID {assignment.id}, урок '{assignment.lesson.title}', тип '{assignment.lesson.lesson_type}', группа '{assignment.group.name}', активен: {assignment.is_active}")
        
        # Создаем LessonExecution для всех типов уроков
        for assignment in assigned_lessons:
            # Проверяем, есть ли уже выполнение для этого конкретного назначения
            existing_execution = LessonExecution.objects.filter(
                student=request.user,
                assignment=assignment
            ).first()
            
            print(f"DEBUG: Проверяем выполнение для назначения ID {assignment.id}, урок '{assignment.lesson.title}', тип '{assignment.lesson.lesson_type}', существующее: {existing_execution is not None}")
            
            # Создаем выполнение только если его еще нет для этого назначения
            if not existing_execution:
                execution = LessonExecution.objects.create(
                    lesson=assignment.lesson,
                    student=request.user,
                    assignment=assignment,
                    status='assigned'
                )
                print(f"DEBUG: Создано новое выполнение ID {execution.id} для урока ID {assignment.id} (тип: {assignment.lesson.lesson_type})")
            else:
                print(f"DEBUG: Пропускаем создание выполнения для назначения ID {assignment.id} - уже существует")
        
        # Получаем выполнения уроков учеником (после создания новых)
        lesson_executions = LessonExecution.objects.filter(
            student=request.user,
            is_active=True
        ).select_related('lesson', 'lesson__course', 'assignment').order_by('-started_at')
        
        print(f"DEBUG: Найдено {lesson_executions.count()} активных выполнений для пользователя {request.user.username}")
        for execution in lesson_executions:
            print(f"DEBUG: Выполнение ID {execution.id}, урок '{execution.lesson.title}', статус '{execution.status}', активен: {execution.is_active}")
        
        # Разделяем выполнения по статусам
        assigned_executions = lesson_executions.filter(status='assigned')
        in_progress_executions = lesson_executions.filter(status='in_progress')
        # Завершенные уроки сортируем по дате завершения (последний завершенный первым)
        completed_executions = lesson_executions.filter(status='completed').order_by('-completed_at')
        
        # Объединяем assigned и in_progress для отображения в "Заданных уроках"
        active_executions = lesson_executions.filter(status__in=['assigned', 'in_progress'])
        
        context.update({
            'assigned_executions': active_executions,  # Показываем все активные уроки
            'in_progress_executions': in_progress_executions,
            'completed_executions': completed_executions,
        })
    
    return render(request, 'users/dashboard.html', context)

@login_required
def user_list(request):
    """Список пользователей в зависимости от роли текущего пользователя"""
    # Проверяем, запрашивается ли раздел "Мои ученики"
    my_students = request.GET.get('my_students', False)
    
    if request.user.role == 'admin':
        if my_students:
            # Администратор как учитель видит только своих учеников
            users = User.objects.filter(created_by=request.user, role='student')
        else:
            # Администратор видит всех пользователей
            users = User.objects.all()
    elif request.user.role == 'teacher':
        users = User.objects.filter(created_by=request.user)
    else:
        users = User.objects.none()
    
    # Добавляем информацию о правах для каждого пользователя
    users_with_permissions = []
    for user in users:
        can_manage = request.user.can_manage_user(user)
        users_with_permissions.append({
            'user': user,
            'can_manage': can_manage
        })
    
    # Определяем заголовок страницы
    if request.user.role == 'admin' and my_students:
        page_title = 'Мои ученики'
    elif request.user.role == 'admin':
        page_title = 'Управление пользователями'
    elif request.user.role == 'teacher':
        page_title = 'Мои ученики'
    else:
        page_title = 'Пользователи'
    
    return render(request, 'users/user_list.html', {
        'users': users_with_permissions,
        'current_user': request.user,
        'page_title': page_title
    })

@login_required
def add_teacher(request):
    """Добавление учителя (только для администраторов)"""
    if request.user.role != 'admin':
        messages.error(request, 'У вас нет прав для добавления учителей')
        return redirect('user_list')
    
    if request.method == 'POST':
        form = AddTeacherForm(request.POST)
        if form.is_valid():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            
            # Генерируем логин teacher1, teacher2, и т.д.
            counter = 1
            username = 'teacher1'
            while User.objects.filter(username=username).exists():
                counter += 1
                username = f'teacher{counter}'
            
            # Создаем пользователя с ролью учителя
            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                role='teacher',
                created_by=request.user,
                password='teacher_psw'
            )
            
            messages.success(request, f'Учитель {user.get_full_name()} успешно добавлен')
            return redirect('user_list')
    else:
        form = AddTeacherForm()
    
    return render(request, 'users/add_teacher.html', {'form': form})

@login_required
def add_student(request):
    """Добавление ученика (для администраторов и учителей)"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для добавления учеников')
        return redirect('user_list')
    
    if request.method == 'POST':
        form = AddStudentForm(request.POST)
        if form.is_valid():
            students_data = form.cleaned_data['students_data']
            students_list = [line.strip() for line in students_data.split('\n') if line.strip()]
            
            created_students = []
            for student_data in students_list:
                try:
                    last_name, first_name = student_data.split(' ', 1)
                    
                    # Генерируем логин student1, student2, и т.д.
                    counter = 1
                    username = 'student1'
                    while User.objects.filter(username=username).exists():
                        counter += 1
                        username = f'student{counter}'
                    
                    user = User.objects.create_user(
                        username=username,
                        first_name=first_name,
                        last_name=last_name,
                        role='student',
                        created_by=request.user,
                        password='student_psw'
                    )
                    created_students.append(user)
                except ValueError:
                    messages.error(request, f'Неверный формат данных: {student_data}')
                    continue
            
            if created_students:
                messages.success(request, f'Успешно добавлено {len(created_students)} учеников')
            
            return redirect('user_list')
    else:
        form = AddStudentForm()
    
    return render(request, 'users/add_student.html', {'form': form})

@login_required
def delete_user(request, user_id):
    """Удаление пользователя"""
    user_to_delete = get_object_or_404(User, id=user_id)
    
    if not request.user.can_manage_user(user_to_delete):
        messages.error(request, 'У вас нет прав для удаления этого пользователя')
        return redirect('user_list')
    
    if request.method == 'POST':
        user_to_delete.delete()
        messages.success(request, f'Пользователь {user_to_delete.get_full_name()} удален')
        return redirect('user_list')
    
    return render(request, 'users/delete_user.html', {'user': user_to_delete})

@login_required
def group_list(request):
    """Список групп (только для администраторов и учителей)"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для просмотра групп')
        return redirect('user_list')
    
    groups = Group.objects.filter(created_by=request.user).prefetch_related('students')
    return render(request, 'users/group_list.html', {'groups': groups})

@login_required
def create_group(request):
    """Создание группы (только для администраторов и учителей)"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для создания групп')
        return redirect('user_list')
    
    if request.method == 'POST':
        form = CreateGroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.created_by = request.user
            group.save()
            messages.success(request, f'Группа "{group.name}" создана')
            return redirect('add_students_to_group', group_id=group.id)
    else:
        form = CreateGroupForm()
    
    return render(request, 'users/create_group.html', {'form': form})

@login_required
def add_students_to_group(request, group_id):
    """Добавление учеников в группу"""
    group = get_object_or_404(Group, id=group_id, created_by=request.user)
    
    if request.method == 'POST':
        form = AddStudentsToGroupForm(request.POST, user=request.user, group=group)
        if form.is_valid():
            students = form.cleaned_data['students']
            for student in students:
                UserGroup.objects.get_or_create(user=student, group=group)
            messages.success(request, f'В группу "{group.name}" добавлено {len(students)} учеников')
            return redirect('group_detail', group_id=group.id)
    else:
        form = AddStudentsToGroupForm(user=request.user, group=group)
    
    return render(request, 'users/add_students_to_group.html', {
        'form': form,
        'group': group
    })

@login_required
def group_detail(request, group_id):
    """Детали группы"""
    group = get_object_or_404(Group, id=group_id, created_by=request.user)
    students = User.objects.filter(user_groups__group=group)
    return render(request, 'users/group_detail.html', {
        'group': group,
        'students': students
    })

@login_required
def edit_profile(request):
    """Редактирование профиля"""
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        
        if first_name and last_name:
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.save()
            messages.success(request, 'Профиль успешно обновлен')
            return redirect('dashboard')
        else:
            messages.error(request, 'Имя и фамилия не могут быть пустыми')
    
    return render(request, 'users/edit_profile.html')

@login_required
def change_password(request):
    """Смена пароля"""
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '').strip()
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        
        if not current_password or not new_password or not confirm_password:
            messages.error(request, 'Все поля обязательны для заполнения')
        elif new_password != confirm_password:
            messages.error(request, 'Новые пароли не совпадают')
        elif len(new_password) < 6:
            messages.error(request, 'Пароль должен содержать минимум 6 символов')
        elif not request.user.check_password(current_password):
            messages.error(request, 'Неверный текущий пароль')
        else:
            request.user.set_password(new_password)
            request.user.is_password_changed = True
            request.user.save()
            messages.success(request, 'Пароль успешно изменен')
            return redirect('dashboard')
    
    return render(request, 'users/change_password.html')

@login_required
def edit_user(request, user_id):
    """Редактирование пользователя (только для администраторов)"""
    if request.user.role != 'admin':
        messages.error(request, 'У вас нет прав для редактирования пользователей')
        return redirect('user_list')
    
    user_to_edit = get_object_or_404(User, id=user_id)
    
    # Администратор может редактировать всех пользователей
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        username = request.POST.get('username', '').strip()
        role = request.POST.get('role', '').strip()
        
        if first_name and last_name and username and role:
            # Проверяем уникальность логина
            if username != user_to_edit.username and User.objects.filter(username=username).exists():
                messages.error(request, 'Пользователь с таким логином уже существует')
            else:
                user_to_edit.first_name = first_name
                user_to_edit.last_name = last_name
                user_to_edit.username = username
                user_to_edit.role = role
                user_to_edit.save()
                messages.success(request, f'Пользователь {user_to_edit.get_full_name()} успешно обновлен')
                return redirect('user_list')
        else:
            messages.error(request, 'Все поля обязательны для заполнения')
    
    return render(request, 'users/edit_user.html', {'user_to_edit': user_to_edit})

@login_required
def reset_password(request, user_id):
    """Сброс пароля пользователя (только для администраторов)"""
    if request.user.role != 'admin':
        messages.error(request, 'У вас нет прав для сброса паролей')
        return redirect('user_list')
    
    user_to_reset = get_object_or_404(User, id=user_id)
    
    # Администратор может сбрасывать пароль всем пользователям
    
    if request.method == 'POST':
        # Устанавливаем пароль по умолчанию в зависимости от роли
        if user_to_reset.role == 'admin':
            default_password = 'admin_psw'
        elif user_to_reset.role == 'teacher':
            default_password = 'teacher_psw'
        else:
            default_password = 'student_psw'
        
        user_to_reset.set_password(default_password)
        user_to_reset.is_password_changed = False
        user_to_reset.save()
        
        messages.success(request, f'Пароль для {user_to_reset.get_full_name()} сброшен на стандартный')
        return redirect('user_list')
    
    return render(request, 'users/reset_password.html', {'user_to_reset': user_to_reset})


@login_required
def set_selected_group(request):
    """Установка выбранной группы в сессии"""
    if request.user.role not in ['admin', 'teacher']:
        return JsonResponse({'success': False, 'message': 'Нет прав доступа'})
    
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        group_id = data.get('group_id')
        
        if group_id:
            try:
                group = Group.objects.get(id=group_id)
                # Проверяем, что группа принадлежит пользователю
                if group.created_by == request.user:
                    request.session['selected_group_id'] = group_id
                    return JsonResponse({
                        'success': True,
                        'group_name': group.name
                    })
                else:
                    return JsonResponse({'success': False, 'message': 'Нет доступа к этой группе'})
            except Group.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Группа не найдена'})
        else:
            return JsonResponse({'success': False, 'message': 'ID группы не указан'})
    
    return JsonResponse({'success': False, 'message': 'Неверный метод запроса'})


@login_required
def clear_selected_group(request):
    """Очистка выбранной группы из сессии"""
    if request.user.role not in ['admin', 'teacher']:
        return JsonResponse({'success': False, 'message': 'Нет прав доступа'})
    
    if request.method == 'POST':
        if 'selected_group_id' in request.session:
            del request.session['selected_group_id']
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'message': 'Неверный метод запроса'})


def get_user_groups(user):
    """Получение групп пользователя"""
    if user.role == 'admin':
        # Администраторы видят только группы, которые они создали
        return Group.objects.prefetch_related('students').filter(created_by=user)
    elif user.role == 'teacher':
        # Учителя видят только группы, которые они создали
        return Group.objects.prefetch_related('students').filter(created_by=user)
    return Group.objects.none()


def get_selected_group(user, session):
    """Получение выбранной группы из сессии"""
    selected_group_id = session.get('selected_group_id')
    if selected_group_id:
        try:
            group = Group.objects.prefetch_related('students').get(id=selected_group_id)
            # Проверяем, что группа принадлежит пользователю
            if group.created_by == user:
                return group
        except Group.DoesNotExist:
            pass
    return None

@login_required
def edit_group(request, group_id):
    """Редактирование группы с интуитивным интерфейсом"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для редактирования групп')
        return redirect('group_list')
    
    group = get_object_or_404(Group, id=group_id, created_by=request.user)
    
    if request.method == 'POST':
        form = SimpleGroupEditForm(request.POST)
        if form.is_valid():
            # Обновляем название группы
            group.name = form.cleaned_data['name']
            group.save()
            messages.success(request, 'Название группы обновлено')
            return redirect('edit_group', group_id=group.id)
    else:
        form = SimpleGroupEditForm(initial={'name': group.name})
    
    # Получаем учеников в группе
    students_in_group = group.students.all().order_by('last_name', 'first_name')
    
    # Получаем всех доступных учеников (не в группе)
    available_students = User.objects.filter(
        role='student',
        created_by=request.user
    ).exclude(id__in=group.students.values_list('id', flat=True)).order_by('last_name', 'first_name')
    
    return render(request, 'users/edit_group.html', {
        'form': form,
        'group': group,
        'students_in_group': students_in_group,
        'available_students': available_students
    })

@login_required
def group_detail(request, group_id):
    """Детальная информация о группе с возможностью удаления учеников"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для просмотра групп')
        return redirect('group_list')
    
    group = get_object_or_404(Group, id=group_id, created_by=request.user)
    
    if request.method == 'POST':
        form = RemoveStudentsFromGroupForm(request.POST, group=group)
        if form.is_valid():
            students = form.cleaned_data['students']
            for student in students:
                UserGroup.objects.filter(user=student, group=group).delete()
            messages.success(request, f'Из группы "{group.name}" удалено {len(students)} учеников')
            return redirect('group_detail', group_id=group.id)
    else:
        form = RemoveStudentsFromGroupForm(group=group)
    
    return render(request, 'users/group_detail.html', {
        'form': form,
        'group': group
    })

@login_required
def delete_group(request, group_id):
    """Удаление группы"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для удаления групп')
        return redirect('group_list')
    
    group = get_object_or_404(Group, id=group_id, created_by=request.user)
    
    if request.method == 'POST':
        group_name = group.name
        group.delete()
        messages.success(request, f'Группа "{group_name}" удалена')
        return redirect('group_list')
    
    return render(request, 'users/delete_group.html', {'group': group})

def logout_view(request):
    """Выход из системы"""
    logout(request)
    messages.success(request, 'Вы успешно вышли из системы')
    return redirect('login')

@login_required
def add_student_to_group(request, group_id, student_id):
    """Добавить ученика в группу через AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не разрешен'})
    
    if request.user.role not in ['admin', 'teacher']:
        return JsonResponse({'success': False, 'error': 'Нет прав для редактирования групп'})
    
    try:
        group = Group.objects.get(id=group_id, created_by=request.user)
        student = User.objects.get(id=student_id, role='student', created_by=request.user)
        
        # Проверяем, что ученик не в группе
        if not UserGroup.objects.filter(group=group, user=student).exists():
            UserGroup.objects.create(group=group, user=student)
            return JsonResponse({
                'success': True, 
                'message': f'{student.get_full_name()} добавлен в группу',
                'student_name': student.get_full_name(),
                'student_id': student.id
            })
        else:
            return JsonResponse({'success': False, 'error': 'Ученик уже в группе'})
            
    except Group.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Группа не найдена'})
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Ученик не найден'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def remove_student_from_group(request, group_id, student_id):
    """Удалить ученика из группы через AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не разрешен'})
    
    if request.user.role not in ['admin', 'teacher']:
        return JsonResponse({'success': False, 'error': 'Нет прав для редактирования групп'})
    
    try:
        group = Group.objects.get(id=group_id, created_by=request.user)
        student = User.objects.get(id=student_id, role='student', created_by=request.user)
        
        # Удаляем связь
        user_group = UserGroup.objects.filter(group=group, user=student).first()
        if user_group:
            user_group.delete()
            return JsonResponse({
                'success': True, 
                'message': f'{student.get_full_name()} удален из группы',
                'student_name': student.get_full_name(),
                'student_id': student.id
            })
        else:
            return JsonResponse({'success': False, 'error': 'Ученик не в группе'})
            
    except Group.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Группа не найдена'})
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Ученик не найден'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
