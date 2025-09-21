from django.db import models
from django.conf import settings
from django.utils import timezone


class Course(models.Model):
    """Модель курса"""
    
    COURSE_TYPE_CHOICES = [
        ('general', 'Общий курс'),
        ('personal', 'Личный курс'),
    ]
    
    title = models.CharField(max_length=200, verbose_name='Название курса')
    course_type = models.CharField(
        max_length=10, 
        choices=COURSE_TYPE_CHOICES, 
        verbose_name='Тип курса'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='created_courses',
        verbose_name='Создатель'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    description = models.TextField(blank=True, null=True, verbose_name='Описание курса')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    
    class Meta:
        verbose_name = 'Курс'
        verbose_name_plural = 'Курсы'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_course_type_display()} - {self.title}"
    
    def get_lessons_count(self):
        """Возвращает количество уроков в курсе"""
        return self.lessons.count()
    
    def get_lessons_by_type(self, lesson_type):
        """Возвращает уроки определенного типа"""
        return self.lessons.filter(lesson_type=lesson_type)


class CourseBlock(models.Model):
    """Модель блока курса"""
    
    course = models.ForeignKey(
        Course, 
        on_delete=models.CASCADE, 
        related_name='blocks',
        verbose_name='Курс'
    )
    title = models.CharField(max_length=200, verbose_name='Название блока')
    description = models.TextField(blank=True, null=True, verbose_name='Описание блока')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок в курсе')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    
    class Meta:
        verbose_name = 'Блок курса'
        verbose_name_plural = 'Блоки курса'
        ordering = ['order', 'created_at']
        unique_together = ['course', 'order']
    
    def __str__(self):
        return f"{self.course.title} - {self.title}"
    
    def save(self, *args, **kwargs):
        """Переопределяем save для автоматического обновления order"""
        if not self.order:
            # Если order не задан, устанавливаем следующий номер
            max_order = CourseBlock.objects.filter(course=self.course).aggregate(
                models.Max('order')
            )['order__max'] or 0
            self.order = max_order + 1
        super().save(*args, **kwargs)


class Lesson(models.Model):
    """Модель урока"""
    
    LESSON_TYPE_CHOICES = [
        ('classwork', 'Классная работа'),
        ('homework', 'Домашняя работа'),
        ('control', 'Контроль'),
    ]
    
    course = models.ForeignKey(
        Course, 
        on_delete=models.CASCADE, 
        related_name='lessons',
        verbose_name='Курс'
    )
    block = models.ForeignKey(
        CourseBlock, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='lessons',
        verbose_name='Блок курса'
    )
    title = models.CharField(max_length=200, verbose_name='Название урока')
    lesson_type = models.CharField(
        max_length=10, 
        choices=LESSON_TYPE_CHOICES, 
        verbose_name='Тип урока'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    description = models.TextField(blank=True, null=True, verbose_name='Описание урока')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок в курсе')
    
    # Поля для контрольных работ с вариантами
    variants_count = models.PositiveIntegerField(default=0, verbose_name='Количество вариантов')
    tasks_per_variant = models.PositiveIntegerField(default=0, verbose_name='Заданий в варианте')
    task_pool = models.ManyToManyField(
        'tasks.Task', 
        blank=True,
        related_name='control_lessons',
        verbose_name='Пул заданий для вариантов'
    )
    
    class Meta:
        verbose_name = 'Урок'
        verbose_name_plural = 'Уроки'
        ordering = ['order', 'created_at']
    
    def __str__(self):
        return f"{self.get_lesson_type_display()} - {self.title}"
    
    def get_full_title(self):
        """Возвращает полное название урока в формате 'Тип - Название'"""
        return f"{self.get_lesson_type_display()} - {self.title}"
    
    def get_active_tasks_count(self):
        """Возвращает количество активных заданий в уроке"""
        return self.lesson_tasks.filter(is_active=True).count()
    
    def is_control_lesson(self):
        """Проверяет, является ли урок контрольной работой с вариантами"""
        return self.lesson_type == 'control' and self.variants_count > 0
    
    def can_generate_variants(self):
        """Проверяет, можно ли сгенерировать варианты"""
        if not self.is_control_lesson():
            return False
        
        pool_size = self.task_pool.count()
        min_required_tasks = self.tasks_per_variant  # Минимум = заданий в одном варианте
        
        return pool_size >= min_required_tasks
    
    def generate_variants(self):
        """Генерирует варианты контрольной работы"""
        if not self.can_generate_variants():
            raise ValueError("Недостаточно заданий в пуле для генерации вариантов")
        
        # Удаляем существующие варианты
        self.control_variants.all().delete()
        
        # Получаем все задания из пула
        available_tasks = list(self.task_pool.all())
        
        # Перемешиваем задания
        import random
        random.shuffle(available_tasks)
        
        # Создаем варианты
        for variant_num in range(1, self.variants_count + 1):
            variant = ControlVariant.objects.create(
                lesson=self,
                variant_number=variant_num
            )
            
            # Назначаем задания варианту
            # Если заданий достаточно - берем разные, если нет - повторяем
            for order in range(1, self.tasks_per_variant + 1):
                # Вычисляем индекс задания с учетом номера варианта
                task_index = ((variant_num - 1) * self.tasks_per_variant + (order - 1)) % len(available_tasks)
                task = available_tasks[task_index]
                
                ControlVariantTask.objects.create(
                    variant=variant,
                    task=task,
                    order=order
                )
        
        return self.control_variants.all()
    
    def get_variant_for_student(self, student):
        """Получает вариант для конкретного ученика"""
        from .models import ControlVariantAssignment
        
        # Ищем активное назначение варианта
        assignment = ControlVariantAssignment.objects.filter(
            student=student,
            lesson_assignment__lesson=self,
            is_active=True
        ).first()
        
        return assignment.variant if assignment else None
    
    def save(self, *args, **kwargs):
        """Переопределяем save для автоматического обновления order"""
        if not self.order:
            # Если order не задан, устанавливаем следующий номер
            if self.block:
                # Если урок в блоке, считаем порядок внутри блока
                max_order = Lesson.objects.filter(course=self.course, block=self.block).aggregate(
                    models.Max('order')
                )['order__max'] or 0
            else:
                # Если урок без блока, считаем порядок среди уроков без блока
                max_order = Lesson.objects.filter(course=self.course, block__isnull=True).aggregate(
                    models.Max('order')
                )['order__max'] or 0
            self.order = max_order + 1
        super().save(*args, **kwargs)


class LessonTask(models.Model):
    """Модель связи урока и задания"""
    
    lesson = models.ForeignKey(
        Lesson, 
        on_delete=models.CASCADE, 
        related_name='lesson_tasks',
        verbose_name='Урок'
    )
    task = models.ForeignKey(
        'tasks.Task', 
        on_delete=models.CASCADE, 
        related_name='lesson_tasks',
        verbose_name='Задание'
    )
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок в уроке')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='added_lesson_tasks',
        verbose_name='Добавлено'
    )
    is_active = models.BooleanField(default=True, verbose_name='Активно')
    
    class Meta:
        verbose_name = 'Задание в уроке'
        verbose_name_plural = 'Задания в уроках'
        ordering = ['lesson', 'order', 'created_at']
        unique_together = ['lesson', 'task']  # Одно задание не может быть дважды в одном уроке
    
    def __str__(self):
        return f"{self.lesson.title} - {self.task.id}"
    
    def save(self, *args, **kwargs):
        """Переопределяем save для автоматического обновления order"""
        if not self.order:
            # Если order не задан, устанавливаем следующий номер
            max_order = LessonTask.objects.filter(lesson=self.lesson).aggregate(
                models.Max('order')
            )['order__max'] or 0
            self.order = max_order + 1
        super().save(*args, **kwargs)


class LessonAssignment(models.Model):
    """Модель назначения урока группе"""
    
    lesson = models.ForeignKey(
        Lesson, 
        on_delete=models.CASCADE, 
        related_name='assignments',
        verbose_name='Урок'
    )
    group = models.ForeignKey(
        'users.Group', 
        on_delete=models.CASCADE, 
        related_name='lesson_assignments',
        verbose_name='Группа'
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='assigned_lessons',
        verbose_name='Назначил'
    )
    assigned_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата назначения')
    due_date = models.DateTimeField(null=True, blank=True, verbose_name='Срок выполнения')
    is_active = models.BooleanField(default=True, verbose_name='Активно')
    description = models.TextField(blank=True, null=True, verbose_name='Дополнительные инструкции')
    
    class Meta:
        verbose_name = 'Назначение урока'
        verbose_name_plural = 'Назначения уроков'
        ordering = ['-assigned_at']
    
    def __str__(self):
        return f"{self.lesson.get_full_title()} → {self.group.name}"
    
    def get_students_count(self):
        """Возвращает количество учеников в группе"""
        return self.group.students.count()


class LessonExecution(models.Model):
    """Модель выполнения урока учеником"""
    
    STATUS_CHOICES = [
        ('assigned', 'Задан'),
        ('in_progress', 'Выполняется'),
        ('completed', 'Завершен'),
        ('cancelled', 'Отменен'),
    ]
    
    lesson = models.ForeignKey(
        Lesson, 
        on_delete=models.CASCADE, 
        related_name='executions',
        verbose_name='Урок'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='lesson_executions',
        verbose_name='Ученик'
    )
    assignment = models.ForeignKey(
        LessonAssignment,
        on_delete=models.CASCADE,
        related_name='executions',
        verbose_name='Назначение'
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='assigned',
        verbose_name='Статус'
    )
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Начал выполнение')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Завершил выполнение')
    current_task_index = models.IntegerField(default=0, verbose_name='Текущее задание')
    is_active = models.BooleanField(default=True, verbose_name='Активно')
    
    class Meta:
        verbose_name = 'Выполнение урока'
        verbose_name_plural = 'Выполнения уроков'
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.lesson.get_full_title()}"
    
    def get_current_task(self):
        """Возвращает текущее задание"""
        if self.lesson.lesson_type == 'control':
            # Для контрольных работ получаем задания из варианта
            from courses.models import ControlVariantAssignment
            variant_assignment = ControlVariantAssignment.objects.filter(
                lesson_assignment=self.assignment,
                student=self.student
            ).first()
            
            if not variant_assignment:
                return None
            
            variant_tasks = variant_assignment.variant.variant_tasks.filter(is_active=True).order_by('order')
            tasks = [vt.task for vt in variant_tasks]
        else:
            # Для обычных уроков получаем задания из урока
            tasks = self.lesson.lesson_tasks.filter(is_active=True).order_by('order', 'created_at')
        
        if 0 <= self.current_task_index < len(tasks):
            return tasks[self.current_task_index]
        return None
    
    def get_total_tasks(self):
        """Возвращает общее количество заданий в уроке"""
        if self.lesson.lesson_type == 'control':
            # Для контрольных работ получаем задания из варианта
            from courses.models import ControlVariantAssignment
            variant_assignment = ControlVariantAssignment.objects.filter(
                lesson_assignment=self.assignment,
                student=self.student
            ).first()
            
            if not variant_assignment:
                return 0
            
            return variant_assignment.variant.variant_tasks.filter(is_active=True).count()
        else:
            # Для обычных уроков получаем задания из урока
            return self.lesson.lesson_tasks.filter(is_active=True).count()
    
    def get_correct_answers_count(self):
        """Возвращает количество правильных ответов"""
        correct_count = 0
        for answer in self.answers.all():
            try:
                if answer.task.correct_answer and answer.answer:
                    # Простое сравнение строк (можно улучшить)
                    if answer.answer.strip().lower() == answer.task.correct_answer.strip().lower():
                        correct_count += 1
            except AttributeError:
                # Если task не существует, пропускаем этот ответ
                continue
        return correct_count


class TaskAnswer(models.Model):
    """Модель ответа ученика на задание"""
    
    execution = models.ForeignKey(
        LessonExecution,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='Выполнение урока'
    )
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='student_answers',
        verbose_name='Задание'
    )
    answer = models.TextField(verbose_name='Ответ ученика')
    answered_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата ответа')
    
    class Meta:
        verbose_name = 'Ответ на задание'
        verbose_name_plural = 'Ответы на задания'
        ordering = ['-answered_at']
        unique_together = ['execution', 'task']  # Один ответ на задание в рамках выполнения урока
    
    def __str__(self):
        return f"{self.execution.student.get_full_name()} - {self.task.id}"


class ControlVariant(models.Model):
    """Модель варианта контрольной работы"""
    
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='control_variants',
        verbose_name='Урок'
    )
    variant_number = models.PositiveIntegerField(verbose_name='Номер варианта')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    
    class Meta:
        verbose_name = 'Вариант контрольной работы'
        verbose_name_plural = 'Варианты контрольных работ'
        ordering = ['variant_number']
        unique_together = ['lesson', 'variant_number']
    
    def __str__(self):
        return f"Вариант {self.variant_number} - {self.lesson.title}"
    
    def get_tasks_count(self):
        """Возвращает количество заданий в варианте"""
        return self.variant_tasks.filter(is_active=True).count()


class ControlVariantTask(models.Model):
    """Модель связи варианта с заданием"""
    
    variant = models.ForeignKey(
        ControlVariant,
        on_delete=models.CASCADE,
        related_name='variant_tasks',
        verbose_name='Вариант'
    )
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='variant_assignments',
        verbose_name='Задание'
    )
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок в варианте')
    is_active = models.BooleanField(default=True, verbose_name='Активно')
    
    class Meta:
        verbose_name = 'Задание варианта'
        verbose_name_plural = 'Задания вариантов'
        ordering = ['order']
        unique_together = ['variant', 'task']
    
    def __str__(self):
        return f"{self.variant} - Задание {self.order}"


class ControlVariantAssignment(models.Model):
    """Модель назначения варианта ученику"""
    
    lesson_assignment = models.ForeignKey(
        LessonAssignment,
        on_delete=models.CASCADE,
        related_name='variant_assignments',
        verbose_name='Назначение урока'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='control_variant_assignments',
        verbose_name='Ученик'
    )
    variant = models.ForeignKey(
        ControlVariant,
        on_delete=models.CASCADE,
        related_name='student_assignments',
        verbose_name='Вариант'
    )
    assigned_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата назначения')
    is_active = models.BooleanField(default=True, verbose_name='Активно')
    
    class Meta:
        verbose_name = 'Назначение варианта'
        verbose_name_plural = 'Назначения вариантов'
        ordering = ['-assigned_at']
        unique_together = ['lesson_assignment', 'student']
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.variant}"