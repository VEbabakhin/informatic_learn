from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from tasks.models import Task
import random

User = get_user_model()


class Variant(models.Model):
    """Вариант задания"""
    VARIANT_TYPE_CHOICES = [
        ('normal', 'Обычный'),
        ('control', 'Контроль'),
    ]
    
    # Используем типы заданий из Task
    TASK_TYPE_CHOICES = Task.TASK_TYPE_CHOICES
    
    name = models.CharField(max_length=255, verbose_name='Название варианта')
    task_type = models.CharField(
        max_length=10, 
        choices=TASK_TYPE_CHOICES, 
        blank=True, 
        null=True,
        verbose_name='Тип задания'
    )
    variant_type = models.CharField(
        max_length=10,
        choices=VARIANT_TYPE_CHOICES,
        default='normal',
        verbose_name='Тип варианта'
    )
    time_limit_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Ограничение по времени (в минутах)'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_variants',
        verbose_name='Создано'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    tasks = models.ManyToManyField(
        Task,
        through='VariantTask',
        related_name='variants',
        verbose_name='Задания'
    )
    
    class Meta:
        verbose_name = 'Вариант'
        verbose_name_plural = 'Варианты'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    def get_task_type_display(self):
        """Возвращает отображаемое название типа задания"""
        if self.task_type:
            for choice_value, choice_display in self.TASK_TYPE_CHOICES:
                if choice_value == self.task_type:
                    return choice_display
        return None
    
    def get_tasks_count(self):
        """Возвращает количество заданий в варианте"""
        return self.variant_tasks.count()
    
    def get_variant_type_display_short(self):
        """Короткое название типа варианта"""
        # Поддержка старых значений для обратной совместимости
        # closed (старый) = Контроль (показывает правильность, но не ответ)
        # open (старый) = Обычный (показывает ответ после завершения)
        if self.variant_type == 'normal' or self.variant_type == 'open':
            return 'Обычный'
        elif self.variant_type == 'control' or self.variant_type == 'closed':
            return 'Контроль'
        return 'Обычный'  # По умолчанию


class VariantTask(models.Model):
    """Связь между вариантом и заданием с порядком"""
    variant = models.ForeignKey(
        Variant,
        on_delete=models.CASCADE,
        related_name='variant_tasks',
        verbose_name='Вариант'
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='variant_tasks',
        verbose_name='Задание'
    )
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок')
    
    class Meta:
        verbose_name = 'Задание варианта'
        verbose_name_plural = 'Задания вариантов'
        ordering = ['order']
        unique_together = ['variant', 'task']
    
    def __str__(self):
        return f"{self.variant.name} - {self.task.id}"


class VariantExecution(models.Model):
    """Выполнение варианта пользователем"""
    STATUS_CHOICES = [
        ('not_started', 'Не начато'),
        ('in_progress', 'В процессе'),
        ('completed', 'Завершено'),
        ('timeout', 'Завершено по времени'),
    ]
    
    variant = models.ForeignKey(
        Variant,
        on_delete=models.CASCADE,
        related_name='executions',
        verbose_name='Вариант'
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='variant_executions',
        verbose_name='Ученик'
    )
    assignment = models.ForeignKey(
        'VariantAssignment',
        on_delete=models.CASCADE,
        related_name='executions',
        null=True,
        blank=True,
        verbose_name='Назначение'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='not_started',
        verbose_name='Статус'
    )
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Начато')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Завершено')
    answers = models.JSONField(default=dict, verbose_name='Ответы')  # {task_id: answer}
    current_task_order = models.PositiveIntegerField(null=True, blank=True, verbose_name='Текущее задание')
    
    class Meta:
        verbose_name = 'Выполнение варианта'
        verbose_name_plural = 'Выполнения вариантов'
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.variant.name} - {self.student.get_full_name()}"
    
    def start(self):
        """Начать выполнение варианта"""
        self.status = 'in_progress'
        self.started_at = timezone.now()
        self.save()
    
    def complete(self):
        """Завершить выполнение варианта"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
    
    def timeout(self):
        """Завершить по истечении времени"""
        self.status = 'timeout'
        self.completed_at = timezone.now()
        self.save()
    
    def get_elapsed_time(self):
        """Получить прошедшее время"""
        if not self.started_at:
            return None
        end_time = self.completed_at or timezone.now()
        return end_time - self.started_at
    
    def get_remaining_time(self):
        """Получить оставшееся время в секундах"""
        if not self.variant.time_limit_minutes:
            return None
        if not self.started_at:
            # Если выполнение еще не начато, возвращаем полное время
            return self.variant.time_limit_minutes * 60
        elapsed = self.get_elapsed_time()
        if elapsed:
            total_seconds = self.variant.time_limit_minutes * 60
            remaining = total_seconds - elapsed.total_seconds()
            return max(0, int(remaining))
        return None
    
    def is_timeout(self):
        """Проверить, истекло ли время"""
        remaining = self.get_remaining_time()
        return remaining is not None and remaining <= 0
    
    def get_correct_answers_count(self):
        """Получить количество правильных ответов"""
        if not self.completed_at:
            return 0
        correct = 0
        for variant_task in self.variant.variant_tasks.all():
            task = variant_task.task
            user_answer = self.answers.get(str(task.id), '')
            if user_answer.strip() == task.correct_answer.strip():
                correct += 1
        return correct
    
    def get_total_tasks_count(self):
        """Получить общее количество заданий"""
        return self.variant.get_tasks_count()
    
    def get_task_answer(self, task_id):
        """Получить ответ пользователя на задание"""
        return self.answers.get(str(task_id), '')
    
    def is_answer_correct(self, task_id):
        """Проверить, правильный ли ответ на задание"""
        task = Task.objects.get(id=task_id)
        user_answer = self.get_task_answer(task_id)
        return user_answer.strip() == task.correct_answer.strip()
    
    def get_current_task(self):
        """Получить текущее задание, которое выполняет ученик"""
        if self.current_task_order:
            try:
                return self.variant.variant_tasks.get(order=self.current_task_order)
            except VariantTask.DoesNotExist:
                return None
        return None


class VariantAssignment(models.Model):
    """Назначение варианта ученику"""
    variant = models.ForeignKey(
        Variant,
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name='Вариант'
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='variant_assignments',
        verbose_name='Ученик'
    )
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='assigned_variants',
        verbose_name='Назначено'
    )
    assigned_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата назначения')
    deadline = models.DateTimeField(null=True, blank=True, verbose_name='Срок выполнения')
    is_active = models.BooleanField(default=True, verbose_name='Активно')
    
    class Meta:
        verbose_name = 'Назначение варианта'
        verbose_name_plural = 'Назначения вариантов'
        ordering = ['-assigned_at']
    
    def __str__(self):
        return f"{self.variant.name} - {self.student.get_full_name()}"
    
    def get_execution(self):
        """Получить выполнение варианта для этого назначения"""
        # Используем filter().first() вместо get(), так как может быть несколько выполнений
        return VariantExecution.objects.filter(assignment=self).order_by('-started_at').first()
    
    def is_completed(self):
        """Проверить, выполнен ли вариант"""
        execution = self.get_execution()
        return execution and execution.status in ['completed', 'timeout']
    
    def is_overdue(self):
        """Проверить, просрочен ли вариант"""
        if self.deadline:
            return timezone.now() > self.deadline and not self.is_completed()
        return False
