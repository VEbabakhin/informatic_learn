from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import User, Group, UserGroup
from .forms import AddTeacherForm, AddStudentForm, CreateGroupForm, AddStudentsToGroupForm

@login_required
def dashboard(request):
    """Главная страница платформы"""
    context = {
        'user': request.user,
    }
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
    
    groups = Group.objects.filter(created_by=request.user)
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
        form = AddStudentsToGroupForm(request.POST, user=request.user)
        if form.is_valid():
            students = form.cleaned_data['students']
            for student in students:
                UserGroup.objects.get_or_create(user=student, group=group)
            messages.success(request, f'В группу "{group.name}" добавлено {len(students)} учеников')
            return redirect('group_list')
    else:
        form = AddStudentsToGroupForm(user=request.user)
    
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
