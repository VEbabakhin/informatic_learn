from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils import timezone
from .models import Course, CourseBlock, Lesson, LessonTask, LessonExecution, TaskAnswer, ControlVariant, ControlVariantTask, ControlVariantAssignment, LessonAssignment
from .forms import CourseCreateForm, CourseEditForm, LessonCreateForm, LessonEditForm, CourseFilterForm, CourseBlockCreateForm, CourseBlockEditForm
from tasks.models import Task
from tasks.forms import TaskFilterForm


@login_required
def course_list(request):
    """Список курсов"""
    # Получаем фильтры
    filter_form = CourseFilterForm(request.GET)
    course_type = request.GET.get('course_type', '')
    search = request.GET.get('search', '')
    
    # Базовый запрос курсов
    courses = Course.objects.filter(is_active=True)
    
    # Фильтрация по типу курса
    if course_type:
        courses = courses.filter(course_type=course_type)
    
    # Фильтрация по поиску
    if search:
        courses = courses.filter(title__icontains=search)
    
    # Фильтрация по правам доступа
    if request.user.is_superuser:
        # Администратор видит все курсы
        pass
    else:
        # Учитель видит только общие курсы и свои личные
        courses = courses.filter(
            Q(course_type='general') | 
            Q(course_type='personal', created_by=request.user)
        )
    
    # Сортировка
    courses = courses.order_by('-created_at')
    
    # Пагинация
    paginator = Paginator(courses, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'filter_form': filter_form,
        'current_user': request.user,
    }
    
    return render(request, 'courses/course_list.html', context)


@login_required
def course_detail(request, course_id):
    """Детальный просмотр курса"""
    course = get_object_or_404(Course, id=course_id, is_active=True)
    
    # Проверка прав доступа
    can_view = (
        request.user.is_superuser or 
        course.created_by == request.user or 
        (course.course_type == 'general' and request.user.role in ['admin', 'teacher'])
    )
    
    if not can_view:
        messages.error(request, 'У вас нет доступа к этому курсу.')
        return redirect('courses:course_list')
    
    # Получаем уроки курса
    lessons = course.lessons.filter(is_active=True).order_by('order', 'created_at')
    
    # Получаем блоки курса
    blocks = course.blocks.all().order_by('order')
    
    context = {
        'course': course,
        'lessons': lessons,
        'blocks': blocks,
        'current_user': request.user,
    }
    
    return render(request, 'courses/course_detail.html', context)


@login_required
def course_create(request):
    """Создание курса"""
    if request.method == 'POST':
        form = CourseCreateForm(request.POST, user=request.user)
        if form.is_valid():
            course = form.save(commit=False)
            course.created_by = request.user
            course.save()
            messages.success(request, f'Курс "{course.title}" успешно создан!')
            return redirect('courses:course_detail', course_id=course.id)
    else:
        form = CourseCreateForm(user=request.user)
    
    context = {
        'form': form,
        'current_user': request.user,
    }
    
    return render(request, 'courses/course_create.html', context)


@login_required
def course_edit(request, course_id):
    """Редактирование курса"""
    course = get_object_or_404(Course, id=course_id, is_active=True)
    
    # Проверка прав доступа
    if not request.user.is_superuser and course.created_by != request.user:
        messages.error(request, 'У вас нет прав для редактирования этого курса.')
        return redirect('courses:course_list')
    
    if request.method == 'POST':
        form = CourseEditForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, f'Курс "{course.title}" успешно обновлен!')
            return redirect('courses:course_detail', course_id=course.id)
    else:
        form = CourseEditForm(instance=course)
    
    context = {
        'form': form,
        'course': course,
        'current_user': request.user,
    }
    
    return render(request, 'courses/course_edit.html', context)


@login_required
def course_delete(request, course_id):
    """Удаление курса"""
    course = get_object_or_404(Course, id=course_id, is_active=True)
    
    # Проверка прав доступа
    if not request.user.is_superuser and course.created_by != request.user:
        messages.error(request, 'У вас нет прав для удаления этого курса.')
        return redirect('courses:course_list')
    
    if request.method == 'POST':
        course.is_active = False
        course.save()
        messages.success(request, f'Курс "{course.title}" успешно удален!')
        return redirect('courses:course_list')
    
    context = {
        'course': course,
        'current_user': request.user,
    }
    
    return render(request, 'courses/course_delete.html', context)


@login_required
def lesson_create(request, course_id):
    """Создание урока"""
    course = get_object_or_404(Course, id=course_id, is_active=True)
    
    # Проверка прав доступа
    if not request.user.is_superuser and course.created_by != request.user:
        messages.error(request, 'У вас нет прав для добавления уроков в этот курс.')
        return redirect('courses:course_list')
    
    if request.method == 'POST':
        form = LessonCreateForm(request.POST, course=course)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.course = course
            lesson.save()
            messages.success(request, f'Урок "{lesson.get_full_title()}" успешно добавлен!')
            return redirect('courses:course_detail', course_id=course.id)
    else:
        form = LessonCreateForm(course=course)
    
    context = {
        'form': form,
        'course': course,
        'current_user': request.user,
    }
    
    return render(request, 'courses/lesson_create.html', context)


@login_required
def lesson_edit(request, course_id, lesson_id):
    """Редактирование урока"""
    course = get_object_or_404(Course, id=course_id, is_active=True)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course, is_active=True)
    
    # Проверка прав доступа
    if not request.user.is_superuser and course.created_by != request.user:
        messages.error(request, 'У вас нет прав для редактирования этого урока.')
        return redirect('courses:course_list')
    
    if request.method == 'POST':
        form = LessonEditForm(request.POST, instance=lesson, course=course)
        if form.is_valid():
            form.save()
            messages.success(request, f'Урок "{lesson.get_full_title()}" успешно обновлен!')
            return redirect('courses:course_detail', course_id=course.id)
    else:
        form = LessonEditForm(instance=lesson, course=course)
    
    context = {
        'form': form,
        'course': course,
        'lesson': lesson,
        'current_user': request.user,
    }
    
    return render(request, 'courses/lesson_edit.html', context)


@login_required
def lesson_delete(request, course_id, lesson_id):
    """Удаление урока"""
    course = get_object_or_404(Course, id=course_id, is_active=True)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course)
    
    # Проверка прав доступа
    if not request.user.is_superuser and course.created_by != request.user:
        messages.error(request, 'У вас нет прав для удаления этого урока.')
        return redirect('courses:course_list')
    
    if request.method == 'POST':
        lesson_title = lesson.get_full_title()
        lesson.delete()
        messages.success(request, f'Урок "{lesson_title}" успешно удален!')
        return redirect('courses:course_detail', course_id=course.id)
    
    context = {
        'course': course,
        'lesson': lesson,
        'current_user': request.user,
    }
    
    return render(request, 'courses/lesson_delete.html', context)


@login_required
def lesson_tasks(request, course_id, lesson_id):
    """Задания в уроке"""
    course = get_object_or_404(Course, id=course_id, is_active=True)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course, is_active=True)
    
    # Проверка прав доступа на просмотр
    # Все авторизованные пользователи могут просматривать задания уроков
    can_view = (
        request.user.is_superuser or 
        course.created_by == request.user or 
        (course.course_type == 'general' and request.user.role in ['admin', 'teacher'])
    )
    
    if not can_view:
        messages.error(request, 'У вас нет прав для просмотра заданий этого урока.')
        return redirect('courses:course_list')
    
    # Определяем источник перехода для правильной навигации
    source = request.GET.get('source', 'course')  # по умолчанию из курса
    
    # Проверка прав доступа на редактирование
    if source == 'assignments':
        # Из занятий - ТОЛЬКО просмотр, никакого редактирования
        # Редактирование заданий происходит только в разделе "Курсы"
        can_edit = False
    else:
        # Из курса - создатели курса и админы могут редактировать
        can_edit = (
            request.user.is_superuser or 
            course.created_by == request.user
        )
    
    # Получаем задания урока
    lesson_tasks = LessonTask.objects.filter(lesson=lesson, is_active=True).order_by('order', 'created_at')
    
    context = {
        'course': course,
        'lesson': lesson,
        'lesson_tasks': lesson_tasks,
        'current_user': request.user,
        'source': source,
        'can_edit': can_edit,
    }
    
    return render(request, 'courses/lesson_tasks.html', context)


@login_required
def add_tasks_to_lesson(request, course_id, lesson_id):
    """Добавление заданий в урок"""
    course = get_object_or_404(Course, id=course_id, is_active=True)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course, is_active=True)
    
    # Проверка прав доступа
    can_edit = (
        request.user.is_superuser or 
        course.created_by == request.user
    )
    
    if not can_edit:
        messages.error(request, 'У вас нет прав для добавления заданий в этот урок.')
        return redirect('courses:course_list')
    
    # Получаем фильтры
    filter_form = TaskFilterForm(request.GET)
    task_type = request.GET.get('task_type', '')
    subtype = request.GET.get('subtype', '')
    difficulty = request.GET.get('difficulty', '')
    search = request.GET.get('search', '')
    task_id = request.GET.get('task_id', '')
    
    # Базовый запрос заданий
    tasks = Task.objects.all()
    
    # Фильтрация по типу задания
    if task_type:
        tasks = tasks.filter(task_type=task_type)
    
    # Фильтрация по подтипу
    if subtype:
        tasks = tasks.filter(subtype=subtype)
    
    # Фильтрация по сложности
    if difficulty:
        tasks = tasks.filter(difficulty=difficulty)
    
    # Фильтрация по поиску
    if search:
        search_lower = search.lower()
        search_query = Q(text__iregex=search_lower) | Q(correct_answer__iregex=search_lower)
        for choice_code, choice_display in Task.TASK_TYPE_CHOICES:
            if search_lower in choice_display.lower() or search_lower in choice_code.lower():
                search_query |= Q(task_type=choice_code)
        tasks = tasks.filter(search_query)
    
    # Фильтрация по ID задания
    if task_id:
        tasks = tasks.filter(id=task_id)
    
    # Исключаем уже добавленные задания (только активные)
    existing_task_ids = LessonTask.objects.filter(lesson=lesson, is_active=True).values_list('task_id', flat=True)
    tasks = tasks.exclude(id__in=existing_task_ids)
    
    # Сортировка (используем сортировку по умолчанию из модели Task)
    # tasks = tasks.order_by('-created_at')  # Удалено, используем ordering из модели
    
    # Пагинация
    paginator = Paginator(tasks, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Получаем ID уже добавленных заданий для отображения статуса
    added_task_ids = set(LessonTask.objects.filter(lesson=lesson, is_active=True).values_list('task_id', flat=True))
    
    # Проверяем, это AJAX запрос для загрузки дополнительных заданий
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Возвращаем только HTML с заданиями
        return render(request, 'courses/task_list_partial.html', {
            'page_obj': page_obj,
            'added_task_ids': added_task_ids,
        })
    
    context = {
        'course': course,
        'lesson': lesson,
        'page_obj': page_obj,
        'filter_form': filter_form,
        'current_user': request.user,
        'added_task_ids': added_task_ids,
    }
    
    return render(request, 'courses/add_tasks_to_lesson.html', context)


@login_required
def add_task_to_lesson(request, course_id, lesson_id, task_id):
    """Добавление конкретного задания в урок"""
    course = get_object_or_404(Course, id=course_id, is_active=True)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course, is_active=True)
    task = get_object_or_404(Task, id=task_id)
    
    # Проверка прав доступа
    can_edit = (
        request.user.is_superuser or 
        course.created_by == request.user
    )
    
    if not can_edit:
        if request.headers.get('Content-Type') == 'application/json':
            return JsonResponse({'success': False, 'message': 'У вас нет прав для добавления заданий в этот урок.'})
        messages.error(request, 'У вас нет прав для добавления заданий в этот урок.')
        return redirect('courses:course_list')
    
    # Проверяем, не добавлено ли уже это задание
    lesson_task = LessonTask.objects.filter(lesson=lesson, task=task).first()
    
    if lesson_task:
        if lesson_task.is_active:
            message = f'Задание {task.id} уже добавлено в этот урок.'
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({'success': False, 'message': message})
            messages.warning(request, message)
        else:
            # Активируем ранее удаленное задание
            lesson_task.is_active = True
            lesson_task.added_by = request.user
            lesson_task.save()
            message = f'Задание {task.id} успешно добавлено в урок!'
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({'success': True, 'message': message})
            messages.success(request, message)
    else:
        # Добавляем новое задание в урок
        LessonTask.objects.create(
            lesson=lesson,
            task=task,
            added_by=request.user
        )
        message = f'Задание {task.id} успешно добавлено в урок!'
        if request.headers.get('Content-Type') == 'application/json':
            return JsonResponse({'success': True, 'message': message})
        messages.success(request, message)
    
    return redirect('courses:add_tasks_to_lesson', course_id=course_id, lesson_id=lesson_id)


@login_required
def remove_task_from_lesson(request, course_id, lesson_id, task_id):
    """Удаление задания из урока"""
    course = get_object_or_404(Course, id=course_id, is_active=True)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course, is_active=True)
    task = get_object_or_404(Task, id=task_id)
    
    # Проверка прав доступа
    can_edit = (
        request.user.is_superuser or 
        course.created_by == request.user
    )
    
    if not can_edit:
        messages.error(request, 'У вас нет прав для удаления заданий из этого урока.')
        return redirect('courses:course_list')
    
    # Находим связь задания с уроком
    lesson_task = LessonTask.objects.filter(lesson=lesson, task=task, is_active=True).first()
    
    if lesson_task:
        lesson_task.is_active = False
        lesson_task.save()
        messages.success(request, f'Задание {task.id} удалено из урока!')
    else:
        messages.warning(request, f'Задание {task.id} не найдено в этом уроке.')
    
    return redirect('courses:lesson_tasks', course_id=course_id, lesson_id=lesson_id)


@login_required
def lesson_assignments(request):
    """Главная страница назначения уроков"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для назначения уроков.')
        return redirect('dashboard')
    
    # Получаем выбранную группу
    selected_group_id = request.session.get('selected_group_id')
    if not selected_group_id:
        messages.warning(request, 'Сначала выберите группу для работы.')
        return redirect('group_list')
    
    from users.models import Group
    selected_group = get_object_or_404(Group, id=selected_group_id)
    
    # Получаем курсы, доступные пользователю
    if request.user.role == 'admin':
        courses = Course.objects.filter(is_active=True)
    else:
        # Учители видят общие курсы и свои личные
        courses = Course.objects.filter(
            is_active=True
        ).filter(
            Q(course_type='general') | Q(created_by=request.user)
        )
    
    context = {
        'selected_group': selected_group,
        'courses': courses,
        'current_user': request.user,
    }
    
    return render(request, 'courses/lesson_assignments.html', context)


@login_required
def course_lessons_for_assignment(request, course_id):
    """Список уроков курса для назначения"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для назначения уроков.')
        return redirect('dashboard')
    
    # Получаем выбранную группу
    selected_group_id = request.session.get('selected_group_id')
    if not selected_group_id:
        messages.warning(request, 'Сначала выберите группу для работы.')
        return redirect('group_list')
    
    from users.models import Group
    selected_group = get_object_or_404(Group, id=selected_group_id)
    
    course = get_object_or_404(Course, id=course_id, is_active=True)
    
    # Проверка прав доступа к курсу
    can_view = (
        request.user.is_superuser or 
        course.created_by == request.user or 
        (course.course_type == 'general' and request.user.role in ['admin', 'teacher'])
    )
    
    if not can_view:
        messages.error(request, 'У вас нет доступа к этому курсу.')
        return redirect('courses:lesson_assignments')
    
    # Получаем уроки курса
    lessons = course.lessons.filter(is_active=True).order_by('order', 'created_at')
    
    # Получаем блоки курса
    blocks = course.blocks.all().order_by('order')
    
    # Получаем уже назначенные уроки для этой группы
    from .models import LessonAssignment
    assigned_lesson_ids = LessonAssignment.objects.filter(
        group=selected_group, 
        is_active=True
    ).values_list('lesson_id', flat=True)
    
    # Получаем количество назначений для каждого урока
    assignment_counts = {}
    for lesson in lessons:
        count = LessonAssignment.objects.filter(
            lesson=lesson,
            group=selected_group,
            is_active=True
        ).count()
        assignment_counts[lesson.id] = count
    
    # Добавляем информацию о количестве назначений к каждому уроку
    for lesson in lessons:
        lesson.assignment_count = assignment_counts.get(lesson.id, 0)
    
    # То же самое для уроков в блоках
    for block in blocks:
        for lesson in block.lessons.all():
            lesson.assignment_count = assignment_counts.get(lesson.id, 0)
    
    context = {
        'course': course,
        'lessons': lessons,
        'blocks': blocks,
        'selected_group': selected_group,
        'assigned_lesson_ids': set(assigned_lesson_ids),
        'current_user': request.user,
    }
    
    return render(request, 'courses/course_lessons_for_assignment.html', context)


@login_required
def assign_lesson(request, course_id, lesson_id):
    """Назначение урока группе"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для назначения уроков.')
        return redirect('dashboard')
    
    # Получаем выбранную группу
    selected_group_id = request.session.get('selected_group_id')
    if not selected_group_id:
        messages.warning(request, 'Сначала выберите группу для работы.')
        return redirect('group_list')
    
    from users.models import Group
    from .models import LessonAssignment
    from django.utils import timezone
    
    selected_group = get_object_or_404(Group, id=selected_group_id)
    
    course = get_object_or_404(Course, id=course_id, is_active=True)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course, is_active=True)
    
    # Проверка прав доступа к курсу
    can_assign = (
        request.user.is_superuser or 
        course.created_by == request.user or 
        (course.course_type == 'general' and request.user.role in ['admin', 'teacher'])
    )
    
    if not can_assign:
        messages.error(request, 'У вас нет прав для назначения уроков из этого курса.')
        return redirect('courses:lesson_assignments')
    
    if request.method == 'POST':
        # Проверяем, есть ли активные назначения этого урока группе
        active_assignments = LessonAssignment.objects.filter(
            lesson=lesson, 
            group=selected_group,
            is_active=True
        ).count()
        
        # Создаем новое назначение (разрешаем повторные назначения)
        assignment = LessonAssignment.objects.create(
            lesson=lesson,
            group=selected_group,
            assigned_by=request.user,
            due_date=None,
            description=''
        )
        
        if active_assignments > 0:
            messages.success(request, f'Урок "{lesson.get_full_title()}" повторно назначен группе "{selected_group.name}"! (Всего назначений: {active_assignments + 1})')
        else:
            messages.success(request, f'Урок "{lesson.get_full_title()}" назначен группе "{selected_group.name}"!')
        
        return redirect('courses:course_lessons_for_assignment', course_id=course_id)
    
    # Подсчитываем существующие назначения этого урока группе
    existing_assignments_count = LessonAssignment.objects.filter(
        lesson=lesson,
        group=selected_group,
        is_active=True
    ).count()
    
    context = {
        'course': course,
        'lesson': lesson,
        'selected_group': selected_group,
        'current_user': request.user,
        'existing_assignments_count': existing_assignments_count,
    }
    
    return render(request, 'courses/assign_lesson.html', context)


@login_required
def lesson_assignments_list(request, course_id, lesson_id):
    """Список назначений урока для выбора отмены"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для отмены назначения уроков.')
        return redirect('dashboard')
    
    # Получаем выбранную группу
    selected_group_id = request.session.get('selected_group_id')
    if not selected_group_id:
        messages.warning(request, 'Сначала выберите группу для работы.')
        return redirect('group_list')
    
    from users.models import Group
    selected_group = get_object_or_404(Group, id=selected_group_id)
    
    course = get_object_or_404(Course, id=course_id, is_active=True)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course, is_active=True)
    
    # Проверка прав доступа к курсу
    can_unassign = (
        request.user.is_superuser or 
        course.created_by == request.user or 
        (course.course_type == 'general' and request.user.role in ['admin', 'teacher'])
    )
    
    if not can_unassign:
        messages.error(request, 'У вас нет прав для отмены назначения уроков из этого курса.')
        return redirect('courses:lesson_assignments')
    
    from .models import LessonAssignment
    
    # Получаем все активные назначения
    assignments = LessonAssignment.objects.filter(
        lesson=lesson, 
        group=selected_group, 
        is_active=True
    ).order_by('-assigned_at').select_related('assigned_by')
    
    context = {
        'course': course,
        'lesson': lesson,
        'selected_group': selected_group,
        'assignments': assignments,
        'current_user': request.user,
    }
    
    return render(request, 'courses/lesson_assignments_list.html', context)


@login_required
def lesson_statistics(request, course_id, lesson_id):
    """Статистика по уроку - какие ученики выполнили, какие задания правильные"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для просмотра статистики уроков.')
        return redirect('dashboard')
    
    course = get_object_or_404(Course, id=course_id, is_active=True)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course, is_active=True)
    
    # Проверка прав доступа
    can_view_stats = (
        request.user.is_superuser or 
        course.created_by == request.user or 
        (course.course_type == 'general' and request.user.role in ['admin', 'teacher'])
    )
    
    if not can_view_stats:
        messages.error(request, 'У вас нет прав для просмотра статистики этого урока.')
        return redirect('courses:course_lessons_for_assignment', course_id=course_id)
    
    # Получаем все активные выполнения этого урока
    executions = LessonExecution.objects.filter(
        lesson=lesson,
        status='completed',
        is_active=True
    ).select_related('student', 'assignment__group').order_by('-completed_at')
    
    # Получаем все задания урока
    tasks = lesson.lesson_tasks.filter(is_active=True).order_by('order', 'created_at')
    
    # Создаем матрицу результатов
    statistics_data = []
    for execution in executions:
        student_data = {
            'student': execution.student,
            'group': execution.assignment.group,
            'completed_at': execution.completed_at,
            'task_results': [],
            'correct_count': 0
        }
        
        for task in tasks:
            # Получаем ответ ученика на это задание
            try:
                answer = execution.answers.get(task=task.task)
                is_correct = answer.answer.lower().strip() == task.task.correct_answer.lower().strip()
                if is_correct:
                    student_data['correct_count'] += 1
                student_data['task_results'].append({
                    'task': task.task,
                    'answer': answer.answer,
                    'is_correct': is_correct,
                    'answered_at': answer.answered_at,
                    'has_answer': True
                })
            except:
                # Если ответа нет
                student_data['task_results'].append({
                    'task': task.task,
                    'answer': None,
                    'is_correct': False,
                    'answered_at': None,
                    'has_answer': False
                })
        
        statistics_data.append(student_data)
    
    context = {
        'course': course,
        'lesson': lesson,
        'statistics_data': statistics_data,
        'tasks': tasks,
        'current_user': request.user,
    }
    
    return render(request, 'courses/lesson_statistics.html', context)


@login_required
def unassign_lesson(request, course_id, lesson_id, assignment_id):
    """Отмена конкретного назначения урока группе"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для отмены назначения уроков.')
        return redirect('dashboard')
    
    # Получаем выбранную группу
    selected_group_id = request.session.get('selected_group_id')
    if not selected_group_id:
        messages.warning(request, 'Сначала выберите группу для работы.')
        return redirect('group_list')
    
    from users.models import Group
    selected_group = get_object_or_404(Group, id=selected_group_id)
    
    course = get_object_or_404(Course, id=course_id, is_active=True)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course, is_active=True)
    
    # Проверка прав доступа к курсу
    can_unassign = (
        request.user.is_superuser or 
        course.created_by == request.user or 
        (course.course_type == 'general' and request.user.role in ['admin', 'teacher'])
    )
    
    if not can_unassign:
        messages.error(request, 'У вас нет прав для отмены назначения уроков из этого курса.')
        return redirect('courses:lesson_assignments')
    
    from .models import LessonAssignment
    
    # Находим конкретное назначение
    assignment = get_object_or_404(
        LessonAssignment, 
        id=assignment_id,
        lesson=lesson, 
        group=selected_group, 
        is_active=True
    )
    
    # Отменяем назначение
    assignment.is_active = False
    assignment.save()
    
    # Деактивируем все выполнения этого урока, связанные с отмененным назначением
    from .models import LessonExecution
    executions = LessonExecution.objects.filter(
        lesson=lesson,
        assignment=assignment,
        student__in=selected_group.students.all()
    )
    
    deactivated_executions_count = 0
    for execution in executions:
        # Если выполнение завершено, деактивируем его
        if execution.status == 'completed':
            execution.is_active = False
            execution.save()
            deactivated_executions_count += 1
        # Если выполнение в процессе, отменяем его
        elif execution.status == 'in_progress':
            execution.status = 'cancelled'
            execution.save()
    
    # Дополнительно деактивируем все выполнения этого урока с отмененными назначениями
    # (на случай, если есть выполнения с другими отмененными назначениями)
    additional_executions = LessonExecution.objects.filter(
        lesson=lesson,
        assignment__is_active=False,
        student__in=selected_group.students.all(),
        is_active=True
    )
    
    for execution in additional_executions:
        execution.is_active = False
        execution.save()
        deactivated_executions_count += 1
    
    # Подсчитываем оставшиеся активные назначения
    remaining_count = LessonAssignment.objects.filter(
        lesson=lesson, 
        group=selected_group, 
        is_active=True
    ).count()
    
    if remaining_count > 0:
        if deactivated_executions_count > 0:
            messages.success(request, f'Назначение отменено. Деактивировано выполнений: {deactivated_executions_count}. Осталось активных назначений: {remaining_count}.')
        else:
            messages.success(request, f'Назначение отменено. Осталось активных назначений: {remaining_count}.')
    else:
        if deactivated_executions_count > 0:
            messages.success(request, f'Назначение урока "{lesson.get_full_title()}" группе "{selected_group.name}" отменено. Деактивировано выполнений: {deactivated_executions_count}.')
        else:
            messages.success(request, f'Назначение урока "{lesson.get_full_title()}" группе "{selected_group.name}" отменено.')
    
    return redirect('courses:course_lessons_for_assignment', course_id=course_id)


# Блоки курса
@login_required
def course_blocks(request, course_id):
    """Список блоков курса"""
    course = get_object_or_404(Course, id=course_id)
    
    # Проверка прав доступа
    if not (request.user.is_superuser or course.created_by == request.user):
        messages.error(request, 'У вас нет прав для просмотра этого курса.')
        return redirect('courses:course_list')
    
    blocks = course.blocks.all().order_by('order')
    
    return render(request, 'courses/course_blocks.html', {
        'course': course,
        'blocks': blocks
    })


@login_required
def create_block(request, course_id):
    """Создание блока курса"""
    course = get_object_or_404(Course, id=course_id)
    
    # Проверка прав доступа
    if not (request.user.is_superuser or course.created_by == request.user):
        messages.error(request, 'У вас нет прав для редактирования этого курса.')
        return redirect('courses:course_list')
    
    if request.method == 'POST':
        form = CourseBlockCreateForm(request.POST)
        if form.is_valid():
            block = form.save(commit=False)
            block.course = course
            block.save()
            messages.success(request, f'Блок "{block.title}" успешно создан.')
            return redirect('courses:course_blocks', course_id=course.id)
    else:
        form = CourseBlockCreateForm()
    
    return render(request, 'courses/create_block.html', {
        'course': course,
        'form': form
    })


@login_required
def edit_block(request, course_id, block_id):
    """Редактирование блока курса"""
    course = get_object_or_404(Course, id=course_id)
    block = get_object_or_404(CourseBlock, id=block_id, course=course)
    
    # Проверка прав доступа
    if not (request.user.is_superuser or course.created_by == request.user):
        messages.error(request, 'У вас нет прав для редактирования этого курса.')
        return redirect('courses:course_list')
    
    if request.method == 'POST':
        form = CourseBlockEditForm(request.POST, instance=block)
        if form.is_valid():
            form.save()
            messages.success(request, f'Блок "{block.title}" успешно обновлен.')
            return redirect('courses:course_blocks', course_id=course.id)
    else:
        form = CourseBlockEditForm(instance=block)
    
    return render(request, 'courses/edit_block.html', {
        'course': course,
        'block': block,
        'form': form
    })


@login_required
def delete_block(request, course_id, block_id):
    """Удаление блока курса"""
    course = get_object_or_404(Course, id=course_id)
    block = get_object_or_404(CourseBlock, id=block_id, course=course)
    
    # Проверка прав доступа
    if not (request.user.is_superuser or course.created_by == request.user):
        messages.error(request, 'У вас нет прав для редактирования этого курса.')
        return redirect('courses:course_list')
    
    if request.method == 'POST':
        block_title = block.title
        # Перемещаем уроки из блока в "без блока"
        block.lessons.update(block=None)
        block.delete()
        messages.success(request, f'Блок "{block_title}" и все его уроки перемещены в "Без блока".')
        return redirect('courses:course_blocks', course_id=course.id)
    
    return render(request, 'courses/delete_block.html', {
        'course': course,
        'block': block
    })


@login_required
def start_lesson(request, execution_id):
    """Начало выполнения урока учеником"""
    if request.user.role != 'student':
        messages.error(request, 'У вас нет прав для выполнения уроков.')
        return redirect('dashboard')
    
    execution = get_object_or_404(LessonExecution, id=execution_id, student=request.user)
    
    # Проверяем, что урок еще не завершен
    if execution.status == 'completed':
        messages.warning(request, 'Этот урок уже завершен.')
        return redirect('dashboard')
    
    # Если урок еще не начат, начинаем его
    if execution.status == 'assigned':
        execution.status = 'in_progress'
        execution.started_at = timezone.now()
        execution.save()
    
    # Получаем задания урока
    if execution.lesson.lesson_type == 'control':
        # Для контрольных работ получаем задания из варианта
        variant_assignment = ControlVariantAssignment.objects.filter(
            lesson_assignment=execution.assignment,
            student=request.user
        ).first()
        
        if not variant_assignment:
            messages.error(request, 'Вам не назначен вариант для этой контрольной работы.')
            return redirect('dashboard')
        
        variant_tasks = variant_assignment.variant.variant_tasks.filter(is_active=True).order_by('order')
        tasks = [vt.task for vt in variant_tasks]
    else:
        # Для обычных уроков получаем задания из урока
        tasks = execution.lesson.lesson_tasks.filter(is_active=True).order_by('order', 'created_at')
    
    if not tasks:
        messages.warning(request, 'В этом уроке нет заданий.')
        return redirect('dashboard')
    
    # Получаем индекс задания из параметров или используем текущий
    task_index = request.GET.get('task_index')
    if task_index is not None:
        try:
            task_index = int(task_index)
            if 0 <= task_index < execution.get_total_tasks():
                execution.current_task_index = task_index
                execution.save()
        except (ValueError, TypeError):
            pass  # Используем текущий индекс
    
    # Получаем текущее задание
    current_task = execution.get_current_task()
    if not current_task:
        execution.current_task_index = 0
        execution.save()
        current_task = execution.get_current_task()
    
    # Получаем ответы ученика
    answers = {answer.task_id: answer.answer for answer in execution.answers.all()}
    answered_task_ids = set(answers.keys())
    
    context = {
        'execution': execution,
        'tasks': tasks,
        'current_task': current_task,
        'answers': answers,
        'answered_task_ids': answered_task_ids,
        'total_tasks': len(tasks),
    }
    
    return render(request, 'courses/execute_lesson.html', context)


@login_required
def save_task_answer(request, execution_id, task_id):
    """Сохранение ответа ученика на задание"""
    if request.user.role != 'student':
        return JsonResponse({'success': False, 'message': 'У вас нет прав для выполнения уроков.'})
    
    execution = get_object_or_404(LessonExecution, id=execution_id, student=request.user)
    
    if execution.status != 'in_progress':
        return JsonResponse({'success': False, 'message': 'Урок не выполняется.'})
    
    if request.method == 'POST':
        answer_text = request.POST.get('answer', '').strip()
        
        if not answer_text:
            return JsonResponse({'success': False, 'message': 'Ответ не может быть пустым.'})
        
        # Создаем или обновляем ответ
        task_answer, created = TaskAnswer.objects.get_or_create(
            execution=execution,
            task_id=task_id,
            defaults={'answer': answer_text}
        )
        
        if not created:
            task_answer.answer = answer_text
            task_answer.save()
        
        return JsonResponse({'success': True, 'message': 'Ответ сохранен.'})
    
    return JsonResponse({'success': False, 'message': 'Неверный метод запроса.'})


@login_required
def next_task(request, execution_id):
    """Переход к следующему заданию"""
    if request.user.role != 'student':
        return JsonResponse({'success': False, 'message': 'У вас нет прав для выполнения уроков.'})
    
    execution = get_object_or_404(LessonExecution, id=execution_id, student=request.user)
    
    if execution.status != 'in_progress':
        return JsonResponse({'success': False, 'message': 'Урок не выполняется.'})
    
    total_tasks = execution.get_total_tasks()
    
    if execution.current_task_index < total_tasks - 1:
        execution.current_task_index += 1
        execution.save()
        
        current_task = execution.get_current_task()
        answers = {answer.task_id: answer for answer in execution.answers.all()}
        
        return JsonResponse({
            'success': True,
            'current_task_index': execution.current_task_index,
            'total_tasks': total_tasks,
            'task_html': render(request, 'courses/task_partial.html', {
                'current_task': current_task,
                'answers': answers,
                'execution': execution,
            }).content.decode('utf-8')
        })
    
    return JsonResponse({'success': False, 'message': 'Это последнее задание.'})


@login_required
def prev_task(request, execution_id):
    """Переход к предыдущему заданию"""
    if request.user.role != 'student':
        return JsonResponse({'success': False, 'message': 'У вас нет прав для выполнения уроков.'})
    
    execution = get_object_or_404(LessonExecution, id=execution_id, student=request.user)
    
    if execution.status != 'in_progress':
        return JsonResponse({'success': False, 'message': 'Урок не выполняется.'})
    
    if execution.current_task_index > 0:
        execution.current_task_index -= 1
        execution.save()
        
        current_task = execution.get_current_task()
        answers = {answer.task_id: answer for answer in execution.answers.all()}
        
        return JsonResponse({
            'success': True,
            'current_task_index': execution.current_task_index,
            'total_tasks': execution.get_total_tasks(),
            'task_html': render(request, 'courses/task_partial.html', {
                'current_task': current_task,
                'answers': answers,
                'execution': execution,
            }).content.decode('utf-8')
        })
    
    return JsonResponse({'success': False, 'message': 'Это первое задание.'})


@login_required
def complete_lesson(request, execution_id):
    """Завершение урока"""
    if request.user.role != 'student':
        return JsonResponse({'success': False, 'message': 'У вас нет прав для выполнения уроков.'})
    
    execution = get_object_or_404(LessonExecution, id=execution_id, student=request.user)
    
    if execution.status != 'in_progress':
        return JsonResponse({'success': False, 'message': 'Урок не выполняется.'})
    
    execution.status = 'completed'
    execution.completed_at = timezone.now()
    execution.save()
    
    return JsonResponse({'success': True, 'message': 'Урок успешно завершен!'})


@login_required
def view_completed_lesson(request, execution_id):
    """Просмотр завершенного урока"""
    if request.user.role != 'student':
        messages.error(request, 'У вас нет прав для просмотра уроков.')
        return redirect('dashboard')
    
    execution = get_object_or_404(LessonExecution, id=execution_id, student=request.user, status='completed')
    
    
    # Получаем все задания и ответы
    tasks = execution.lesson.lesson_tasks.filter(is_active=True).order_by('order', 'created_at')
    answers = {answer.task_id: answer.answer for answer in execution.answers.all()}
    
    context = {
        'execution': execution,
        'tasks': tasks,
        'answers': answers,
    }
    
    return render(request, 'courses/completed_lesson.html', context)


@login_required
def generate_control_variants(request, course_id, lesson_id):
    """Генерация вариантов для контрольной работы"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для генерации вариантов.')
        return redirect('dashboard')
    
    course = get_object_or_404(Course, id=course_id, is_active=True)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course, is_active=True)
    
    # Проверка прав доступа к курсу
    can_manage = (
        request.user.is_superuser or 
        course.created_by == request.user or 
        (course.course_type == 'general' and request.user.role in ['admin', 'teacher'])
    )
    
    if not can_manage:
        messages.error(request, 'У вас нет прав для управления этим курсом.')
        return redirect('courses:course_list')
    
    if not lesson.is_control_lesson():
        messages.error(request, 'Этот урок не является контрольной работой с вариантами.')
        return redirect('courses:course_lessons_for_assignment', course_id=course_id)
    
    if request.method == 'POST':
        try:
            variants = lesson.generate_variants()
            messages.success(request, f'Успешно сгенерировано {len(variants)} вариантов.')
            return redirect('courses:control_variants', course_id=course_id, lesson_id=lesson_id)
        except ValueError as e:
            messages.error(request, str(e))
    
    context = {
        'course': course,
        'lesson': lesson,
        'can_generate': lesson.can_generate_variants(),
        'pool_size': lesson.task_pool.count(),
        'min_required_tasks': lesson.tasks_per_variant,
    }
    
    return render(request, 'courses/generate_variants.html', context)


@login_required
def control_variants(request, course_id, lesson_id):
    """Просмотр вариантов контрольной работы"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для просмотра вариантов.')
        return redirect('dashboard')
    
    course = get_object_or_404(Course, id=course_id, is_active=True)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course, is_active=True)
    
    # Проверка прав доступа к курсу
    can_manage = (
        request.user.is_superuser or 
        course.created_by == request.user or 
        (course.course_type == 'general' and request.user.role in ['admin', 'teacher'])
    )
    
    if not can_manage:
        messages.error(request, 'У вас нет прав для управления этим курсом.')
        return redirect('courses:course_list')
    
    variants = lesson.control_variants.filter(is_active=True).order_by('variant_number')
    
    context = {
        'course': course,
        'lesson': lesson,
        'variants': variants,
    }
    
    return render(request, 'courses/control_variants.html', context)


@login_required
def assign_variants(request, course_id, lesson_id):
    """Назначение вариантов ученикам"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для назначения вариантов.')
        return redirect('dashboard')
    
    # Получаем выбранную группу
    selected_group_id = request.session.get('selected_group_id')
    if not selected_group_id:
        messages.warning(request, 'Сначала выберите группу для работы.')
        return redirect('group_list')
    
    from users.models import Group
    selected_group = get_object_or_404(Group, id=selected_group_id)
    
    course = get_object_or_404(Course, id=course_id, is_active=True)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course, is_active=True)
    
    # Проверка прав доступа к курсу
    can_assign = (
        request.user.is_superuser or 
        course.created_by == request.user or 
        (course.course_type == 'general' and request.user.role in ['admin', 'teacher'])
    )
    
    if not can_assign:
        messages.error(request, 'У вас нет прав для назначения вариантов из этого курса.')
        return redirect('courses:course_lessons_for_assignment', course_id=course_id)
    
    if not lesson.is_control_lesson():
        messages.error(request, 'Этот урок не является контрольной работой с вариантами.')
        return redirect('courses:course_lessons_for_assignment', course_id=course_id)
    
    # Для контрольных работ с вариантами не проверяем назначение урока группе
    # так как назначение вариантов и есть назначение урока
    
    # Получаем варианты
    variants = lesson.control_variants.filter(is_active=True).order_by('variant_number')
    
    # Получаем всех учеников группы
    students = selected_group.students.all()
    
    # Получаем существующее назначение или создаем новое
    lesson_assignment = LessonAssignment.objects.filter(
        lesson=lesson,
        group=selected_group,
        is_active=True
    ).first()
    
    if not lesson_assignment:
        # Создаем новое назначение
        lesson_assignment = LessonAssignment.objects.create(
            lesson=lesson,
            group=selected_group,
            assigned_by=request.user,
            assigned_at=timezone.now(),
            is_active=True
        )
        print(f"DEBUG: Создано новое назначение ID {lesson_assignment.id}")
    else:
        print(f"DEBUG: Используем существующее назначение ID {lesson_assignment.id}")
    
    # Получаем существующие назначения вариантов
    existing_assignments = ControlVariantAssignment.objects.filter(
        lesson_assignment=lesson_assignment
    ).select_related('student', 'variant')
    
    if request.method == 'POST':
        if 'assign_lessons' in request.POST:
            # Назначение уроков с вариантами
            selected_student_ids = request.POST.getlist('selected_students')
            assignments_created = 0
            
            for student_id in selected_student_ids:
                try:
                    student = selected_group.students.get(id=student_id)
                    variant_id = request.POST.get(f'variant_{student_id}')
                    
                    if variant_id:
                        variant = ControlVariant.objects.get(id=variant_id, lesson=lesson)
                        
                        # Удаляем существующие назначения (полное удаление)
                        ControlVariantAssignment.objects.filter(
                            lesson_assignment=lesson_assignment,
                            student=student
                        ).delete()
                        
                        # Создаем новое назначение варианта
                        ControlVariantAssignment.objects.create(
                            lesson_assignment=lesson_assignment,
                            student=student,
                            variant=variant
                        )
                        
                        assignments_created += 1
                        
                except (selected_group.students.model.DoesNotExist, ControlVariant.DoesNotExist):
                    continue
            
            if assignments_created > 0:
                messages.success(request, f'Урок назначен {assignments_created} ученикам с выбранными вариантами. LessonAssignment ID: {lesson_assignment.id}, активен: {lesson_assignment.is_active}')
            else:
                messages.warning(request, 'Не выбрано ни одного ученика или варианта для назначения.')
            
            return redirect('courses:assign_variants', course_id=course_id, lesson_id=lesson_id)
    
    # Создаем словарь существующих назначений
    assignments_dict = {assignment.student.id: assignment for assignment in existing_assignments}
    
    context = {
        'course': course,
        'lesson': lesson,
        'selected_group': selected_group,
        'variants': variants,
        'students': students,
        'assignments': assignments_dict,
    }
    
    return render(request, 'courses/assign_variants.html', context)


# Многоэтапное создание контрольных работ

@login_required
def control_lesson_wizard(request, course_id, step=1):
    """Многоэтапное создание контрольной работы"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для создания контрольных работ.')
        return redirect('dashboard')
    
    course = get_object_or_404(Course, id=course_id, is_active=True)
    
    # Проверка прав доступа к курсу
    can_create = (
        request.user.is_superuser or 
        course.created_by == request.user or 
        (course.course_type == 'general' and request.user.role in ['admin', 'teacher'])
    )
    
    if not can_create:
        messages.error(request, 'У вас нет прав для создания уроков в этом курсе.')
        return redirect('courses:course_list')
    
    # Импортируем формы
    from .control_forms import (
        ControlLessonStep1Form, ControlLessonStep2Form, 
        ControlLessonStep3Form, ControlLessonStep4Form
    )
    
    # Инициализируем данные из сессии
    wizard_data = request.session.get('control_lesson_wizard', {})
    
    # Проверяем, есть ли данные из формы создания урока
    if step == 1 and request.GET.get('title'):
        # Пропускаем первый этап, если данные уже переданы
        wizard_data['step1'] = {
            'title': request.GET.get('title'),
            'block': request.GET.get('block'),
            'description': request.GET.get('description', '')
        }
        request.session['control_lesson_wizard'] = wizard_data
        return redirect('courses:control_lesson_wizard', course_id=course_id, step=2)
    
    if step == 1:
        return _handle_step1(request, course, wizard_data)
    elif step == 2:
        return _handle_step2(request, course, wizard_data)
    elif step == 3:
        return _handle_step3(request, course, wizard_data)
    elif step == 4:
        return _handle_step4(request, course, wizard_data)
    else:
        return redirect('courses:control_lesson_wizard', course_id=course_id, step=1)


def _handle_step1(request, course, wizard_data):
    """Этап 1: Название урока и тип"""
    from .control_forms import ControlLessonStep1Form
    
    if request.method == 'POST':
        form = ControlLessonStep1Form(request.POST, course=course)
        if form.is_valid():
            # Сохраняем данные в сессии
            wizard_data['step1'] = form.cleaned_data
            request.session['control_lesson_wizard'] = wizard_data
            return redirect('courses:control_lesson_wizard', course_id=course.id, step=2)
    else:
        # Заполняем форму данными из сессии
        initial_data = wizard_data.get('step1', {})
        form = ControlLessonStep1Form(initial=initial_data, course=course)
    
    context = {
        'course': course,
        'form': form,
        'step': 1,
        'total_steps': 4,
        'step_title': 'Основная информация'
    }
    
    return render(request, 'courses/control_wizard_step1.html', context)


def _handle_step2(request, course, wizard_data):
    """Этап 2: Выбор пула заданий"""
    from .control_forms import ControlLessonStep2Form
    from tasks.forms import TaskFilterForm
    from tasks.models import Task
    
    # Проверяем, что есть данные из первого шага
    if 'step1' not in wizard_data:
        return redirect('courses:control_lesson_wizard', course_id=course.id, step=1)
    
    # Получаем фильтры из GET-параметров
    task_filter = TaskFilterForm(request.GET)
    tasks = Task.objects.all()
    
    # Применяем фильтры
    if task_filter.is_valid():
        task_type = task_filter.cleaned_data.get('task_type')
        difficulty = task_filter.cleaned_data.get('difficulty')
        search = task_filter.cleaned_data.get('search')
        
        if task_type:
            tasks = tasks.filter(task_type=task_type)
        if difficulty:
            tasks = tasks.filter(difficulty=difficulty)
        if search:
            tasks = tasks.filter(text__icontains=search)
    
    # Пагинация
    from django.core.paginator import Paginator
    paginator = Paginator(tasks, 20)  # Увеличиваем количество заданий на странице
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    if request.method == 'POST':
        form = ControlLessonStep2Form(request.POST)
        if form.is_valid():
            # Сохраняем выбранные задания
            selected_tasks = form.cleaned_data.get('selected_tasks', '')
            if selected_tasks:
                try:
                    task_ids = [int(id) for id in selected_tasks.split(',') if id]
                    wizard_data['step2'] = {
                        'selected_tasks': task_ids,
                        'selected_tasks_count': len(task_ids)
                    }
                    request.session['control_lesson_wizard'] = wizard_data
                    return redirect('courses:control_lesson_wizard', course_id=course.id, step=3)
                except ValueError:
                    form.add_error('selected_tasks', 'Неверный формат выбранных заданий')
    else:
        # Заполняем форму данными из сессии
        initial_data = wizard_data.get('step2', {})
        form = ControlLessonStep2Form(initial=initial_data)
    
    context = {
        'course': course,
        'form': form,
        'task_filter': task_filter,
        'page_obj': page_obj,
        'step': 2,
        'total_steps': 4,
        'step_title': 'Выбор заданий',
        'selected_tasks_count': wizard_data.get('step2', {}).get('selected_tasks_count', 0),
        'wizard_data': wizard_data
    }
    
    return render(request, 'courses/control_wizard_step2.html', context)


@login_required
def load_tasks_ajax(request, course_id):
    """AJAX-загрузка заданий для бесконечного скролла"""
    if request.user.role not in ['admin', 'teacher']:
        return JsonResponse({'error': 'Нет прав доступа'}, status=403)
    
    from tasks.forms import TaskFilterForm
    from tasks.models import Task
    from django.core.paginator import Paginator
    from django.template.loader import render_to_string
    import json
    
    # Получаем фильтры из GET-параметров
    task_filter = TaskFilterForm(request.GET)
    tasks = Task.objects.all()
    
    # Применяем фильтры
    if task_filter.is_valid():
        task_type = task_filter.cleaned_data.get('task_type')
        difficulty = task_filter.cleaned_data.get('difficulty')
        search = task_filter.cleaned_data.get('search')
        
        if task_type:
            tasks = tasks.filter(task_type=task_type)
        if difficulty:
            tasks = tasks.filter(difficulty=difficulty)
        if search:
            tasks = tasks.filter(text__icontains=search)
    
    # Пагинация
    page = int(request.GET.get('page', 1))
    paginator = Paginator(tasks, 20)
    page_obj = paginator.get_page(page)
    
    # Получаем выбранные задания
    selected_tasks = []
    if request.GET.get('selected_tasks'):
        try:
            selected_tasks = [int(id) for id in request.GET.get('selected_tasks').split(',') if id]
        except ValueError:
            selected_tasks = []
    
    # Рендерим HTML для заданий
    tasks_html = render_to_string('courses/partials/task_card.html', {
        'tasks': page_obj,
        'selected_tasks': selected_tasks
    })
    
    return JsonResponse({
        'html': tasks_html,
        'has_next': page_obj.has_next(),
        'next_page': page + 1 if page_obj.has_next() else None,
        'current_page': page,
        'total_pages': paginator.num_pages
    })


def _handle_step3(request, course, wizard_data):
    """Этап 3: Настройка времени выполнения и вариантов"""
    from .control_forms import ControlLessonStep3Form
    
    # Проверяем, что есть данные из предыдущих шагов
    if 'step1' not in wizard_data or 'step2' not in wizard_data:
        return redirect('courses:control_lesson_wizard', course_id=course.id, step=1)
    
    selected_tasks_count = wizard_data['step2'].get('selected_tasks_count', 0)
    
    if request.method == 'POST':
        form = ControlLessonStep3Form(request.POST, initial={'selected_tasks_count': selected_tasks_count})
        if form.is_valid():
            # Сохраняем данные в сессии
            wizard_data['step3'] = form.cleaned_data
            request.session['control_lesson_wizard'] = wizard_data
            return redirect('courses:control_lesson_wizard', course_id=course.id, step=4)
    else:
        # Заполняем форму данными из сессии
        initial_data = wizard_data.get('step3', {})
        initial_data['selected_tasks_count'] = selected_tasks_count
        form = ControlLessonStep3Form(initial=initial_data)
    
    context = {
        'course': course,
        'form': form,
        'step': 3,
        'total_steps': 4,
        'step_title': 'Настройка вариантов',
        'selected_tasks_count': selected_tasks_count,
        'wizard_data': wizard_data
    }
    
    return render(request, 'courses/control_wizard_step3.html', context)


def _handle_step4(request, course, wizard_data):
    """Этап 4: Подтверждение и генерация"""
    from .control_forms import ControlLessonStep4Form
    
    # Проверяем, что есть данные из всех предыдущих шагов
    if not all(key in wizard_data for key in ['step1', 'step2', 'step3']):
        return redirect('courses:control_lesson_wizard', course_id=course.id, step=1)
    
    if request.method == 'POST':
        form = ControlLessonStep4Form(request.POST)
        if form.is_valid():
            # Создаем урок
            try:
                lesson = _create_control_lesson(course, wizard_data)
                
                # Очищаем данные из сессии
                if 'control_lesson_wizard' in request.session:
                    del request.session['control_lesson_wizard']
                
                messages.success(request, f'Контрольная работа "{lesson.title}" успешно создана!')
                return redirect('courses:course_detail', course_id=course.id)
                
            except Exception as e:
                messages.error(request, f'Ошибка при создании контрольной работы: {str(e)}')
    else:
        form = ControlLessonStep4Form()
    
    # Подготавливаем данные для отображения
    step1_data = wizard_data['step1']
    step2_data = wizard_data['step2']
    step3_data = wizard_data['step3']
    
    # Получаем информацию о выбранных заданиях
    from tasks.models import Task
    selected_tasks = Task.objects.filter(id__in=step2_data['selected_tasks'])
    
    context = {
        'course': course,
        'form': form,
        'step': 4,
        'total_steps': 4,
        'step_title': 'Подтверждение',
        'step1_data': step1_data,
        'step2_data': step2_data,
        'step3_data': step3_data,
        'selected_tasks': selected_tasks
    }
    
    return render(request, 'courses/control_wizard_step4.html', context)


def _create_control_lesson(course, wizard_data):
    """Создает контрольную работу на основе данных из сессии"""
    from .models import Lesson
    
    step1_data = wizard_data['step1']
    step2_data = wizard_data['step2']
    step3_data = wizard_data['step3']
    
    # Создаем урок
    lesson = Lesson.objects.create(
        course=course,
        title=step1_data['title'],
        lesson_type='control',
        block=step1_data.get('block'),
        description=step1_data.get('description', ''),
        variants_count=step3_data['variants_count'],
        tasks_per_variant=step3_data['tasks_per_variant'],
        is_active=True
    )
    
    # Добавляем задания в пул
    task_ids = step2_data['selected_tasks']
    lesson.task_pool.set(task_ids)
    
    # Генерируем варианты
    lesson.generate_variants()
    
    return lesson


@login_required
def control_lesson_wizard_reset(request, course_id):
    """Сброс данных мастера создания контрольной работы"""
    if 'control_lesson_wizard' in request.session:
        del request.session['control_lesson_wizard']
    
    messages.info(request, 'Данные мастера создания контрольной работы сброшены.')
    return redirect('courses:control_lesson_wizard', course_id=course_id, step=1)