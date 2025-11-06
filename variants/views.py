from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
import random
import json

from .models import Variant, VariantTask, VariantExecution, VariantAssignment
from .forms import (
    VariantFromTemplateForm, VariantFromSpecificTasksForm,
    AssignVariantToStudentForm, AssignVariantsToGroupForm, VariantByNumberForm
)
from tasks.models import Task
from users.models import Group

User = get_user_model()


@login_required
def variant_list(request):
    """Список вариантов"""
    if request.user.role == 'student':
        # Для учеников показываем только назначенные варианты
        assignments = VariantAssignment.objects.filter(
            student=request.user,
            is_active=True
        ).select_related('variant', 'variant__created_by').order_by('-assigned_at')
        
        # Отладочная информация
        if not assignments.exists():
            # Проверяем, есть ли назначения вообще (даже неактивные)
            all_assignments = VariantAssignment.objects.filter(student=request.user)
            if all_assignments.exists():
                messages.warning(request, f'Найдено {all_assignments.count()} назначений, но они неактивны. Обратитесь к учителю.')
        
        variants_data = []
        for assignment in assignments:
            execution = assignment.get_execution()
            variants_data.append({
                'assignment': assignment,
                'variant': assignment.variant,
                'execution': execution,
                'is_completed': assignment.is_completed(),
                'is_overdue': assignment.is_overdue(),
            })
        
        context = {
            'variants_data': variants_data,
            'is_student': True,
        }
        return render(request, 'variants/variant_list_student.html', context)
    
    # Для учителей и администраторов
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для просмотра вариантов')
        return redirect('dashboard')
    
    variants = Variant.objects.filter(created_by=request.user).prefetch_related('variant_tasks__task')
    
    # Фильтр по типу варианта
    variant_type = request.GET.get('variant_type', '')
    if variant_type:
        variants = variants.filter(variant_type=variant_type)
    
    # Фильтр по типу задания
    task_type = request.GET.get('task_type', '')
    if task_type:
        variants = variants.filter(task_type=task_type)
    
    paginator = Paginator(variants, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Группируем варианты по типу заданий
    variants_by_task_type = {}
    for variant in page_obj:
        task_type_key = variant.task_type if variant.task_type else 'other'
        if task_type_key not in variants_by_task_type:
            variants_by_task_type[task_type_key] = []
        variants_by_task_type[task_type_key].append(variant)
    
    context = {
        'variants': page_obj,
        'variants_by_task_type': variants_by_task_type,
        'variant_type': variant_type,
        'task_type': task_type,
        'VARIANT_TYPE_CHOICES': Variant.VARIANT_TYPE_CHOICES,
        'TASK_TYPE_CHOICES': Variant.TASK_TYPE_CHOICES,
    }
    
    # Если это AJAX запрос, возвращаем только HTML контент
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'variants/variant_list.html', context)
    
    return render(request, 'variants/variant_list.html', context)


@login_required
def variant_create_choice(request):
    """Выбор способа создания варианта"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для создания вариантов')
        return redirect('variants:variant_list')
    
    return render(request, 'variants/variant_create_choice.html')


@login_required
def variant_create_from_template(request):
    """Создание варианта по шаблону"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для создания вариантов')
        return redirect('variants:variant_list')
    
    # Получаем задания с фильтрацией
    tasks_queryset = Task.objects.all()
    
    # Применяем фильтры из GET параметров
    task_type_filter = request.GET.get('task_type_filter', '') or request.GET.get('task_type', '')
    subtype_filter = request.GET.get('subtype', '')
    difficulty_filter = request.GET.get('difficulty', '')
    task_id_filter = request.GET.get('task_id', '')
    search_filter = request.GET.get('search', '')
    
    if task_id_filter:
        try:
            tasks_queryset = tasks_queryset.filter(id=int(task_id_filter))
        except ValueError:
            pass
    
    if task_type_filter:
        tasks_queryset = tasks_queryset.filter(task_type=task_type_filter)
    
    if subtype_filter:
        tasks_queryset = tasks_queryset.filter(subtype=subtype_filter)
    
    if difficulty_filter:
        tasks_queryset = tasks_queryset.filter(difficulty=difficulty_filter)
    
    if search_filter:
        search_lower = search_filter.lower()
        search_query = Q(text__iregex=search_lower) | Q(correct_answer__iregex=search_lower)
        
        for choice_code, choice_display in Task.TASK_TYPE_CHOICES:
            if search_lower in choice_display.lower() or search_lower in choice_code.lower():
                search_query |= Q(task_type=choice_code)
        
        tasks_queryset = tasks_queryset.filter(search_query)
    
    if request.method == 'POST':
        form = VariantFromTemplateForm(request.POST, user=request.user)
        form.fields['task_pool'].queryset = tasks_queryset
        
        if form.is_valid():
            task_pool = form.cleaned_data['task_pool']
            tasks_per_variant = form.cleaned_data['tasks_per_variant']
            variants_count = form.cleaned_data['variants_count']
            name_template = form.cleaned_data['name']
            
            pool_size = len(task_pool)
            
            if pool_size < tasks_per_variant:
                messages.error(
                    request,
                    f'Недостаточно заданий в пуле. Нужно минимум {tasks_per_variant} заданий, а в пуле только {pool_size}.'
                )
            else:
                created_variants = []
                task_list = list(task_pool)
                
                for i in range(variants_count):
                    variant_name = f"{name_template} - {i + 1}"
                    
                    if pool_size >= tasks_per_variant * variants_count:
                        start_idx = i * tasks_per_variant
                        end_idx = start_idx + tasks_per_variant
                        variant_tasks = task_list[start_idx:end_idx]
                    else:
                        shuffled_tasks = task_list.copy()
                        random.shuffle(shuffled_tasks)
                        variant_tasks = shuffled_tasks[:tasks_per_variant]
                    
                    variant = Variant.objects.create(
                        name=variant_name,
                        task_type=form.cleaned_data.get('task_type') or None,
                        variant_type=form.cleaned_data['variant_type'],
                        time_limit_minutes=form.cleaned_data.get('time_limit_minutes') or None,
                        created_by=request.user
                    )
                    
                    for order, task in enumerate(variant_tasks, start=1):
                        VariantTask.objects.create(
                            variant=variant,
                            task=task,
                            order=order
                        )
                    
                    created_variants.append(variant)
                
                messages.success(request, f'Успешно создано {len(created_variants)} вариантов')
                return redirect('variants:variant_list')
    else:
        form = VariantFromTemplateForm(user=request.user)
        form.fields['task_pool'].queryset = tasks_queryset
    
    subtype_choices = []
    if task_type_filter and task_type_filter in Task.SUBTYPE_CHOICES:
        subtype_choices = Task.SUBTYPE_CHOICES[task_type_filter]
    
    tasks_list = list(tasks_queryset.order_by('id'))
    
    context = {
        'form': form,
        'tasks_list': tasks_list,
        'task_type_filter': task_type_filter,
        'subtype_filter': subtype_filter,
        'difficulty_filter': difficulty_filter,
        'task_id_filter': task_id_filter,
        'search_filter': search_filter,
        'TASK_TYPE_CHOICES': Task.TASK_TYPE_CHOICES,
        'SUBTYPE_CHOICES': Task.SUBTYPE_CHOICES,
        'subtype_choices': subtype_choices,
        'DIFFICULTY_CHOICES': Task.DIFFICULTY_CHOICES,
    }
    
    return render(request, 'variants/variant_create_from_template.html', context)


@login_required
def variant_create_from_specific_tasks(request):
    """Создание варианта из конкретных заданий"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для создания вариантов')
        return redirect('variants:variant_list')
    
    tasks_queryset = Task.objects.all()
    
    task_type_filter = request.GET.get('task_type_filter', '') or request.GET.get('task_type', '')
    subtype_filter = request.GET.get('subtype', '')
    difficulty_filter = request.GET.get('difficulty', '')
    task_id_filter = request.GET.get('task_id', '')
    search_filter = request.GET.get('search', '')
    
    if task_id_filter:
        try:
            tasks_queryset = tasks_queryset.filter(id=int(task_id_filter))
        except ValueError:
            pass
    
    if task_type_filter:
        tasks_queryset = tasks_queryset.filter(task_type=task_type_filter)
    
    if subtype_filter:
        tasks_queryset = tasks_queryset.filter(subtype=subtype_filter)
    
    if difficulty_filter:
        tasks_queryset = tasks_queryset.filter(difficulty=difficulty_filter)
    
    if search_filter:
        search_lower = search_filter.lower()
        search_query = Q(text__iregex=search_lower) | Q(correct_answer__iregex=search_lower)
        
        for choice_code, choice_display in Task.TASK_TYPE_CHOICES:
            if search_lower in choice_display.lower() or search_lower in choice_code.lower():
                search_query |= Q(task_type=choice_code)
        
        tasks_queryset = tasks_queryset.filter(search_query)
    
    if request.method == 'POST':
        form = VariantFromSpecificTasksForm(request.POST, user=request.user)
        form.fields['tasks'].queryset = tasks_queryset
        
        if form.is_valid():
            tasks = form.cleaned_data['tasks']
            
            if not tasks:
                messages.error(request, 'Выберите хотя бы одно задание')
            else:
                variant = form.save(commit=False)
                variant.created_by = request.user
                variant.save()
                
                for order, task in enumerate(tasks, start=1):
                    VariantTask.objects.create(
                        variant=variant,
                        task=task,
                        order=order
                    )
                
                messages.success(request, f'Вариант "{variant.name}" успешно создан')
                return redirect('variants:variant_detail', variant_id=variant.id)
    else:
        form = VariantFromSpecificTasksForm(user=request.user)
        form.fields['tasks'].queryset = tasks_queryset.order_by('id')
    
    subtype_choices = []
    if task_type_filter and task_type_filter in Task.SUBTYPE_CHOICES:
        subtype_choices = Task.SUBTYPE_CHOICES[task_type_filter]
    
    tasks_list = list(tasks_queryset.order_by('id'))
    
    context = {
        'form': form,
        'tasks_list': tasks_list,
        'task_type_filter': task_type_filter,
        'subtype_filter': subtype_filter,
        'difficulty_filter': difficulty_filter,
        'task_id_filter': task_id_filter,
        'search_filter': search_filter,
        'TASK_TYPE_CHOICES': Task.TASK_TYPE_CHOICES,
        'SUBTYPE_CHOICES': Task.SUBTYPE_CHOICES,
        'subtype_choices': subtype_choices,
        'DIFFICULTY_CHOICES': Task.DIFFICULTY_CHOICES,
    }
    
    return render(request, 'variants/variant_create_from_specific_tasks.html', context)


@login_required
def variant_detail(request, variant_id):
    """Детальная информация о варианте"""
    variant = get_object_or_404(Variant, id=variant_id)
    
    if request.user.role == 'student':
        # Ученик может видеть только назначенные ему варианты
        assignment = VariantAssignment.objects.filter(
            variant=variant,
            student=request.user,
            is_active=True
        ).first()
        
        if not assignment:
            messages.error(request, 'У вас нет доступа к этому варианту')
            return redirect('variants:variant_list')
    else:
        # Учитель может видеть только свои варианты
        if variant.created_by != request.user:
            messages.error(request, 'У вас нет прав для просмотра этого варианта')
            return redirect('variants:variant_list')
    
    tasks = variant.variant_tasks.select_related('task').order_by('order')
    
    context = {
        'variant': variant,
        'tasks': tasks,
    }
    
    return render(request, 'variants/variant_detail.html', context)


@login_required
def variant_delete(request, variant_id):
    """Удаление варианта"""
    variant = get_object_or_404(Variant, id=variant_id, created_by=request.user)
    
    if request.method == 'POST':
        variant_name = variant.name
        variant.delete()
        messages.success(request, f'Вариант "{variant_name}" удален')
        return redirect('variants:variant_list')
    
    return render(request, 'variants/variant_delete.html', {'variant': variant})


@login_required
def variant_start(request, variant_id):
    """Начать выполнение варианта"""
    variant = get_object_or_404(Variant, id=variant_id)
    
    # Проверяем доступ для ученика
    if request.user.role == 'student':
        assignment = VariantAssignment.objects.filter(
            variant=variant,
            student=request.user,
            is_active=True
        ).order_by('-assigned_at').first()
        
        if not assignment:
            messages.error(request, 'У вас нет доступа к этому варианту')
            return redirect('variants:variant_list')
        
        # Получаем выполнение для этого назначения
        execution = VariantExecution.objects.filter(assignment=assignment).first()
        
        if execution:
            # Если выполнение уже существует
            if execution.status == 'completed' or execution.status == 'timeout':
                # Если выполнение завершено, проверяем, не является ли назначение новым
                # (создано после завершения выполнения)
                from django.utils import timezone
                is_new_assignment = False
                
                if execution.completed_at:
                    # Если есть дата завершения, проверяем, что назначение создано после завершения
                    if assignment.assigned_at > execution.completed_at:
                        is_new_assignment = True
                else:
                    # Если нет даты завершения, но выполнение завершено,
                    # проверяем, что назначение новое (создано недавно)
                    # Если назначение создано в последние 24 часа, считаем его новым
                    from datetime import timedelta
                    if assignment.assigned_at > timezone.now() - timedelta(days=1):
                        is_new_assignment = True
                
                if is_new_assignment:
                    # Создаем новое выполнение для нового назначения
                    execution = VariantExecution.objects.create(
                        assignment=assignment,
                        variant=variant,
                        student=request.user,
                        status='not_started'
                    )
                    execution.start()
                else:
                    # Если выполнение завершено и назначение не новое, показываем результаты
                    messages.info(request, 'Вы уже завершили этот вариант')
                    return redirect('variants:variant_result', execution_id=execution.id)
            # Если выполнение в процессе, продолжаем его
            elif execution.status == 'in_progress':
                return redirect('variants:variant_execute', execution_id=execution.id)
            # Если выполнение не начато, начинаем его
            elif execution.status == 'not_started':
                execution.start()
        else:
            # Если выполнения нет, создаем новое
            execution = VariantExecution.objects.create(
                assignment=assignment,
                variant=variant,
                student=request.user,
                status='not_started'
            )
            execution.start()
    
    return redirect('variants:variant_execute', execution_id=execution.id)


@login_required
def variant_execute(request, execution_id):
    """Выполнение варианта"""
    execution = get_object_or_404(VariantExecution, id=execution_id, student=request.user)
    
    if execution.status == 'completed' or execution.status == 'timeout':
        messages.info(request, 'Вариант уже завершен')
        return redirect('variants:variant_result', execution_id=execution.id)
    
    if execution.status == 'not_started':
        execution.start()
    
    variant = execution.variant
    tasks = variant.variant_tasks.select_related('task').order_by('order')
    
    # Получаем ответы для каждого задания
    task_answers = {}
    for variant_task in tasks:
        task_id = str(variant_task.task.id)
        task_answers[str(variant_task.task.id)] = execution.answers.get(task_id, '')
    
    # Проверяем время, если установлено ограничение
    remaining_time = None
    if variant.time_limit_minutes:
        remaining_time = execution.get_remaining_time()
        if remaining_time is not None and remaining_time <= 0:
            execution.timeout()
            messages.warning(request, 'Время выполнения варианта истекло')
            return redirect('variants:variant_result', execution_id=execution.id)
    
    # Сохраняем ответы
    if request.method == 'POST':
        task_id = request.POST.get('task_id')
        answer = request.POST.get('answer', '')
        current_task_order = request.POST.get('current_task_order')
        
        if task_id:
            answers = execution.answers.copy()
            answers[str(task_id)] = answer
            execution.answers = answers
            
            if current_task_order:
                try:
                    execution.current_task_order = int(current_task_order)
                except ValueError:
                    pass
            
            execution.save()
            return JsonResponse({'success': True})
        
        # Завершение варианта
        if 'complete' in request.POST:
            # Сохраняем все ответы из формы перед завершением
            answers = execution.answers.copy() if execution.answers else {}
            for variant_task in tasks:
                task_id = str(variant_task.task.id)
                answer_key = f'answer_{variant_task.task.id}'
                # Сохраняем ответ из формы, даже если он пустой
                if answer_key in request.POST:
                    answers[task_id] = request.POST.get(answer_key, '').strip()
                # Если ответа нет в форме, но есть в сохраненных ответах, оставляем его
                # Если ответа нет вообще, оставляем пустую строку
                elif task_id not in answers:
                    answers[task_id] = ''
            execution.answers = answers
            execution.save()  # Сохраняем перед завершением
            execution.complete()
            return redirect('variants:variant_result', execution_id=execution.id)
    
    context = {
        'execution': execution,
        'variant': variant,
        'tasks': tasks,
        'task_answers_json': json.dumps(task_answers),
        'task_answers': task_answers,
        'remaining_time': remaining_time,
    }
    
    return render(request, 'variants/variant_execute.html', context)


@login_required
def variant_result(request, execution_id):
    """Результаты выполнения варианта"""
    execution = get_object_or_404(VariantExecution, id=execution_id, student=request.user)
    
    variant = execution.variant
    tasks = variant.variant_tasks.select_related('task').order_by('order')
    
    # Если вариант не завершен, завершаем его
    if execution.status not in ['completed', 'timeout']:
        execution.complete()
    
    correct_count = execution.get_correct_answers_count()
    total_count = execution.get_total_tasks_count()
    
    # Вычисляем процент и определяем цвет карточки
    percentage = 0
    if total_count > 0:
        percentage = int((correct_count / total_count) * 100)
    
    # Определяем цвет карточки
    if correct_count == total_count:
        card_color = 'success'
    elif correct_count >= total_count / 2:
        card_color = 'warning'
    else:
        card_color = 'danger'
    
    # Получаем ответы и правильность для каждого задания
    task_results = []
    answered_count = 0
    for variant_task in tasks:
        task_id = str(variant_task.task.id)
        user_answer = execution.answers.get(task_id, '')
        if user_answer and user_answer.strip():
            answered_count += 1
        is_correct = user_answer.strip() == variant_task.task.correct_answer.strip()
        task_results.append({
            'variant_task': variant_task,
            'user_answer': user_answer,
            'is_correct': is_correct,
            'task_id': variant_task.task.id,
        })
    
    context = {
        'execution': execution,
        'variant': variant,
        'tasks': tasks,
        'task_results': task_results,
        'correct_count': correct_count,
        'total_count': total_count,
        'answered_count': answered_count,
        'percentage': percentage,
        'card_color': card_color,
    }
    
    return render(request, 'variants/variant_result.html', context)


@login_required
def variant_execution_list(request):
    """Список выполнений вариантов для текущего пользователя"""
    executions = VariantExecution.objects.filter(student=request.user).select_related('variant').order_by('-started_at')
    
    paginator = Paginator(executions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'executions': page_obj,
    }
    
    return render(request, 'variants/variant_execution_list.html', context)


@login_required
@require_POST
def save_answer(request, execution_id):
    """Сохранение ответа через AJAX"""
    try:
        execution = get_object_or_404(VariantExecution, id=execution_id, student=request.user)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Ошибка получения выполнения: {str(e)}'})
    
    if execution.status in ['completed', 'timeout']:
        return JsonResponse({'success': False, 'error': 'Вариант уже завершен'})
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        return JsonResponse({'success': False, 'error': f'Ошибка парсинга JSON: {str(e)}'})
    
    task_id = data.get('task_id')
    answer = data.get('answer', '')
    current_task_order = data.get('current_task_order')
    
    try:
        # Обновляем текущее задание, если указано
        if current_task_order:
            try:
                execution.current_task_order = int(current_task_order)
            except (ValueError, TypeError):
                pass
        
        if task_id:
            answers = execution.answers.copy() if execution.answers else {}
            answers[str(task_id)] = answer
            execution.answers = answers
            execution.save()
            return JsonResponse({'success': True})
        elif current_task_order:
            # Если только обновление текущего задания без ответа
            execution.save()
            return JsonResponse({'success': True})
        
        return JsonResponse({'success': False, 'error': 'Неверные данные'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Ошибка сохранения: {str(e)}'})


# Новые функции для назначений

@login_required
def assign_variant_to_student(request):
    """Назначение варианта конкретному ученику"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для назначения вариантов')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = AssignVariantToStudentForm(request.POST, user=request.user)
        if form.is_valid():
            variant = form.cleaned_data['variant']
            student = form.cleaned_data['student']
            deadline = form.cleaned_data.get('deadline')
            
            # Всегда создаем новое назначение, даже если оно уже существует
            from django.utils import timezone
            assignment = VariantAssignment.objects.create(
                variant=variant,
                student=student,
                assigned_by=request.user,
                deadline=deadline,
                is_active=True,
                assigned_at=timezone.now()
            )
            
            messages.success(request, f'Вариант "{variant.name}" успешно назначен ученику {student.get_full_name()}')
            
            return redirect('variants:variant_list')
    else:
        form = AssignVariantToStudentForm(user=request.user)
    
    return render(request, 'variants/assign_variant_to_student.html', {'form': form})


@login_required
def assign_variants_to_group(request):
    """Назначение вариантов группе"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для назначения вариантов')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = AssignVariantsToGroupForm(request.POST, user=request.user)
        if form.is_valid():
            group = form.cleaned_data['group']
            variants = form.cleaned_data['variants']
            deadline = form.cleaned_data.get('deadline')
            
            # Получаем всех учеников группы
            students = group.students.all()
            
            if not students:
                messages.error(request, 'В группе нет учеников')
                return render(request, 'variants/assign_variants_to_group.html', {'form': form})
            
            # Распределяем варианты между учениками
            variants_list = list(variants)
            students_list = list(students)
            
            created_count = 0
            
            from django.utils import timezone
            import random
            # Перемешиваем список вариантов для случайного распределения
            shuffled_variants = variants_list.copy()
            random.shuffle(shuffled_variants)
            
            for i, student in enumerate(students_list):
                # Выбираем вариант для ученика (распределение по кругу с перемешанными вариантами)
                variant = shuffled_variants[i % len(shuffled_variants)]
                
                # Всегда создаем новое назначение, даже если оно уже существует
                VariantAssignment.objects.create(
                    variant=variant,
                    student=student,
                    assigned_by=request.user,
                    deadline=deadline,
                    is_active=True,
                    assigned_at=timezone.now()
                )
                created_count += 1
            
            messages.success(
                request,
                f'Варианты успешно назначены группе "{group.name}". '
                f'Создано назначений: {created_count}'
            )
            
            return redirect('variants:variant_list')
    else:
        form = AssignVariantsToGroupForm(user=request.user)
    
    return render(request, 'variants/assign_variants_to_group.html', {'form': form})


@login_required
def variant_start_by_number(request):
    """Начать выполнение варианта по номеру"""
    if request.user.role != 'student':
        messages.error(request, 'Эта функция доступна только для учеников')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = VariantByNumberForm(request.POST)
        if form.is_valid():
            variant_id = form.cleaned_data['variant_id']
            
            try:
                variant = Variant.objects.get(id=variant_id)
            except Variant.DoesNotExist:
                messages.error(request, 'Вариант с таким номером не найден')
                return render(request, 'variants/variant_start_by_number.html', {'form': form})
            
            # Ищем активное назначение для этого варианта
            assignment = VariantAssignment.objects.filter(
                variant=variant,
                student=request.user,
                is_active=True
            ).order_by('-assigned_at').first()
            
            # Создаем или получаем выполнение
            if assignment:
                # Если есть назначение, создаем выполнение для него
                execution, created = VariantExecution.objects.get_or_create(
                    assignment=assignment,
                    defaults={
                        'variant': variant,
                        'student': request.user,
                        'status': 'not_started'
                    }
                )
            else:
                # Если нет назначения, создаем выполнение без назначения (для вариантов по номеру)
                # Проверяем, есть ли уже выполнение без назначения
                execution = VariantExecution.objects.filter(
                    variant=variant,
                    student=request.user,
                    assignment__isnull=True
                ).first()
                
                if not execution:
                    execution = VariantExecution.objects.create(
                        variant=variant,
                        student=request.user,
                        assignment=None,
                        status='not_started'
                    )
            
            if execution.status == 'completed' or execution.status == 'timeout':
                messages.info(request, 'Вы уже завершили этот вариант')
                return redirect('variants:variant_result', execution_id=execution.id)
            
            if execution.status == 'not_started':
                execution.start()
            
            return redirect('variants:variant_execute', execution_id=execution.id)
    else:
        form = VariantByNumberForm()
    
    return render(request, 'variants/variant_start_by_number.html', {'form': form})


@login_required
def variant_statistics(request, variant_id):
    """Статистика по варианту"""
    variant = get_object_or_404(Variant, id=variant_id)
    
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для просмотра статистики')
        return redirect('dashboard')
    
    # Проверяем, что вариант принадлежит текущему пользователю
    if variant.created_by != request.user:
        messages.error(request, 'У вас нет прав для просмотра статистики этого варианта')
        return redirect('variants:variant_list')
    
    # Получаем все группы пользователя
    groups = Group.objects.filter(created_by=request.user)
    
    # Выбранная группа
    selected_group_id = request.GET.get('group')
    selected_group = None
    students = []
    
    if selected_group_id:
        try:
            selected_group = groups.get(id=selected_group_id)
            # Если группа выбрана, показываем всех учеников группы
            students = selected_group.students.all().order_by('last_name', 'first_name')
        except Group.DoesNotExist:
            pass
    else:
        # Если группа не выбрана, показываем всех, кто выполнял или выполняет вариант
        executions = VariantExecution.objects.filter(variant=variant).select_related('student')
        student_ids = executions.values_list('student_id', flat=True).distinct()
        from users.models import User
        students = User.objects.filter(id__in=student_ids, role='student').order_by('last_name', 'first_name')
    
    # Получаем статистику для каждого ученика
    students_statistics = []
    tasks = variant.variant_tasks.select_related('task').order_by('order')
    
    for student in students:
        # Получаем последнее выполнение для ученика (если их несколько)
        execution = VariantExecution.objects.filter(
            variant=variant,
            student=student
        ).order_by('-started_at', '-id').first()
        
        # Получаем статус каждого задания
        task_statuses = []
        current_task = None
        remaining_time = None
        
        elapsed_time_formatted = None
        if execution:
            if execution.status == 'in_progress':
                current_task = execution.get_current_task()
            # Вычисляем оставшееся время для всех статусов, если есть ограничение по времени
            if variant.time_limit_minutes:
                remaining_time = execution.get_remaining_time()
            
            # Вычисляем время выполнения для завершенных вариантов типа "контроль"
            if variant.variant_type == 'control' and execution.status in ['completed', 'timeout']:
                elapsed = execution.get_elapsed_time()
                if elapsed:
                    total_seconds = int(elapsed.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    
                    time_parts = []
                    if hours > 0:
                        time_parts.append(f"{hours}ч")
                    if minutes > 0:
                        time_parts.append(f"{minutes}м")
                    time_parts.append(f"{seconds}с")
                    
                    elapsed_time_formatted = " ".join(time_parts)
            
            for variant_task in tasks:
                task_id = str(variant_task.task.id)
                user_answer = execution.answers.get(task_id, '')
                
                # Определяем статус задания
                if not user_answer or user_answer.strip() == '':
                    # Если вариант завершен, но ответ пустой - это не начато (ученик видел задание, но не ответил)
                    # Если вариант в процессе и ответ пустой - это тоже не начато
                    status = 'not_started'
                else:
                    # Есть ответ - проверяем правильность
                    is_correct = user_answer.strip() == variant_task.task.correct_answer.strip()
                    status = 'correct' if is_correct else 'incorrect'
                
                task_statuses.append({
                    'order': variant_task.order,
                    'status': status,
                })
        else:
            # Если выполнение не начато, все задания не начаты
            for variant_task in tasks:
                task_statuses.append({
                    'order': variant_task.order,
                    'status': 'not_started',
                })
        
        # Подсчитываем правильные ответы
        correct_count = sum(1 for ts in task_statuses if ts['status'] == 'correct')
        total_count = len(task_statuses)
        
        students_statistics.append({
            'student': student,
            'execution': execution,
            'task_statuses': task_statuses,
            'current_task': current_task,
            'remaining_time': remaining_time,
            'elapsed_time_formatted': elapsed_time_formatted,
            'correct_count': correct_count,
            'total_count': total_count,
        })
    
    context = {
        'variant': variant,
        'groups': groups,
        'selected_group': selected_group,
        'students_statistics': students_statistics,
        'tasks': tasks,
    }
    
    return render(request, 'variants/variant_statistics.html', context)
