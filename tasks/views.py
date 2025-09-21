from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django import forms
from django.http import JsonResponse
from .models import Task, ImportSession
from .forms import TaskForm, TaskFilterForm, BulkImportForm
import json

@login_required
def task_list(request):
    """Список заданий с фильтрацией и поиском"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для просмотра банка заданий')
        return redirect('dashboard')
    
    # Получаем все задания
    tasks = Task.objects.all()
    
    # Применяем фильтры
    filter_form = TaskFilterForm(request.GET)
    if filter_form.is_valid():
        task_type = filter_form.cleaned_data.get('task_type')
        subtype = filter_form.cleaned_data.get('subtype')
        difficulty = filter_form.cleaned_data.get('difficulty')
        task_id = filter_form.cleaned_data.get('task_id')
        search = filter_form.cleaned_data.get('search')
        
        if task_id:
            tasks = tasks.filter(id=task_id)
        
        # Фильтр по сессии импорта (из URL параметра)
        import_session_id = request.GET.get('import_session')
        if import_session_id:
            tasks = tasks.filter(import_session_id=import_session_id)
        
        if task_type:
            tasks = tasks.filter(task_type=task_type)
        
        if subtype:
            tasks = tasks.filter(subtype=subtype)
        
        if difficulty:
            tasks = tasks.filter(difficulty=difficulty)
        
        if search:
            # Поиск без учета регистра по тексту задания, правильному ответу и типу задания
            # Используем iregex для более надежной работы с кириллицей
            search_lower = search.lower()
            search_query = Q(text__iregex=search_lower) | Q(correct_answer__iregex=search_lower)
            
            # Поиск по типу задания (как по коду, так и по отображаемому названию)
            for choice_code, choice_display in Task.TASK_TYPE_CHOICES:
                if search_lower in choice_display.lower() or search_lower in choice_code.lower():
                    search_query |= Q(task_type=choice_code)
            
            tasks = tasks.filter(search_query)
    
    # Пагинация
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
        if per_page not in [5, 10, 20, 50]:
            per_page = 10
    except (ValueError, TypeError):
        per_page = 10
    
    paginator = Paginator(tasks, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'filter_form': filter_form,
        'current_user': request.user,
        'per_page_options': [5, 10, 20, 50],
        'selected_per_page': per_page,
    }
    
    # Если это AJAX запрос, возвращаем только HTML контент
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'tasks/task_list.html', context)
    
    return render(request, 'tasks/task_list.html', context)

@login_required
def add_task(request):
    """Добавление нового задания"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для добавления заданий')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = TaskForm(request.POST, request.FILES)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            task.save()
            messages.success(request, 'Задание успешно добавлено')
            return redirect('task_list')
    else:
        form = TaskForm()
    
    return render(request, 'tasks/add_task.html', {'form': form})

@login_required
def edit_task(request, task_id):
    """Редактирование задания"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для редактирования заданий')
        return redirect('dashboard')
    
    task = get_object_or_404(Task, id=task_id)
    
    # Проверяем права на редактирование
    if request.user.role == 'teacher' and task.created_by != request.user:
        messages.error(request, 'Вы можете редактировать только свои задания')
        return redirect('task_list')
    
    if request.method == 'POST':
        form = TaskForm(request.POST, request.FILES, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, 'Задание успешно обновлено')
            return redirect('task_list')
    else:
        form = TaskForm(instance=task)
    
    return render(request, 'tasks/edit_task.html', {'form': form, 'task': task})

@login_required
def delete_task(request, task_id):
    """Удаление задания"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для удаления заданий')
        return redirect('dashboard')
    
    task = get_object_or_404(Task, id=task_id)
    
    # Проверяем права на удаление
    if request.user.role == 'teacher' and task.created_by != request.user:
        messages.error(request, 'Вы можете удалять только свои задания')
        return redirect('task_list')
    
    if request.method == 'POST':
        task.delete()
        messages.success(request, 'Задание успешно удалено')
        return redirect('task_list')
    
    return render(request, 'tasks/delete_task.html', {'task': task})

@login_required
def task_detail(request, task_id):
    """Детальный просмотр задания"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для просмотра заданий')
        return redirect('dashboard')
    
    task = get_object_or_404(Task, id=task_id)
    
    # Получаем URL для возврата (по умолчанию - список заданий)
    return_url = request.GET.get('return_url', reverse('task_list'))
    
    return render(request, 'tasks/task_detail.html', {
        'task': task,
        'return_url': return_url
    })


@login_required
def bulk_import(request):
    """Массовый импорт заданий из JSON файла"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для импорта заданий')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = BulkImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # Читаем JSON файл
                json_file = form.cleaned_data['json_file']
                
                # Сбрасываем указатель файла в начало
                json_file.seek(0)
                content = json_file.read().decode('utf-8')
                
                # Проверяем, что файл не пустой
                if not content.strip():
                    messages.error(request, 'JSON файл пустой')
                    return render(request, 'tasks/bulk_import.html', {'form': form})
                
                # Отладочная информация
                print(f"Размер файла: {len(content)} символов")
                print(f"Первые 100 символов: {content[:100]}")
                
                data = json.loads(content)
                
                task_type = form.cleaned_data['task_type']
                subtype = form.cleaned_data.get('subtype', '')
                
                # Создаем сессию импорта
                import_session = ImportSession.objects.create(
                    name=f"Импорт {task_type}",
                    description=f"Импорт заданий типа {task_type}",
                    created_by=request.user,
                    task_type=task_type,
                    subtype=subtype if subtype else None
                )
                
                # Создаем задания
                created_count = 0
                errors = []
                
                for i, task_data in enumerate(data):
                    try:
                        # Определяем сложность
                        difficulty_map = {0: 'easy', 1: 'medium', 2: 'hard'}
                        difficulty = difficulty_map.get(task_data.get('difficulty', 0), 'easy')
                        
                        # Исправляем неправильные символы отрицания в тексте
                        task_text = task_data['text']
                        negation_fixes = {
                            '\\eg': '\\lnot',
                            '\\neg': '\\lnot',
                            'eg ': '\\lnot ',
                            'neg ': '\\lnot ',
                        }
                        for old_symbol, new_symbol in negation_fixes.items():
                            task_text = task_text.replace(old_symbol, new_symbol)
                        
                        # Создаем задание, используя только нужные поля
                        task = Task.objects.create(
                            text=task_text,
                            task_type=task_type,
                            subtype=subtype if subtype else None,
                            difficulty=difficulty,
                            correct_answer=task_data['key'],
                            is_html=True,  # Все импортируемые задания с HTML
                            created_by=request.user,
                            import_session=import_session
                        )
                        created_count += 1
                        
                    except Exception as e:
                        errors.append(f'Задание {i+1}: {str(e)}')
                
                if created_count > 0:
                    # Обновляем количество заданий в сессии
                    import_session.tasks_count = created_count
                    import_session.save()
                    messages.success(request, f'Успешно импортировано {created_count} заданий в сессию "{import_session.name}"')
                
                if errors:
                    for error in errors:
                        messages.warning(request, error)
                
                return redirect('task_list')
                
            except Exception as e:
                messages.error(request, f'Ошибка при импорте: {str(e)}')
    else:
        form = BulkImportForm()
    
    # Получаем все сессии импорта для отображения
    sessions = ImportSession.objects.all().order_by('-created_at')
    
    return render(request, 'tasks/bulk_import.html', {'form': form, 'sessions': sessions})


@login_required
def delete_session_tasks(request, session_id):
    """Удаление всех заданий из сессии импорта"""
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'У вас нет прав для удаления заданий')
        return redirect('dashboard')
    
    session = get_object_or_404(ImportSession, id=session_id)
    
    if request.method == 'POST':
        deleted_count = session.delete_tasks()
        # Удаляем саму сессию после удаления всех заданий
        session.delete()
        messages.success(request, f'Удалено {deleted_count} заданий и сессия "{session.name}"')
        return redirect('bulk_import')
    
    return render(request, 'tasks/delete_session_tasks.html', {'session': session})