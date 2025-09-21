from django import forms
from .models import Course, Lesson, CourseBlock
from tasks.models import Task
from tasks.forms import TaskFilterForm


class CourseCreateForm(forms.ModelForm):
    """Форма для создания курса"""
    
    class Meta:
        model = Course
        fields = ['title', 'course_type', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите название курса'
            }),
            'course_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Описание курса (необязательно)'
            })
        }
        labels = {
            'title': 'Название курса',
            'course_type': 'Тип курса',
            'description': 'Описание курса'
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Если пользователь не администратор, показываем только личные курсы
        if self.user and not self.user.is_superuser:
            self.fields['course_type'].choices = [('personal', 'Личный курс')]
            self.fields['course_type'].initial = 'personal'
            self.fields['course_type'].widget.attrs['readonly'] = True


class CourseEditForm(forms.ModelForm):
    """Форма для редактирования курса"""
    
    class Meta:
        model = Course
        fields = ['title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите название курса'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Описание курса (необязательно)'
            })
        }
        labels = {
            'title': 'Название курса',
            'description': 'Описание курса'
        }


class LessonCreateForm(forms.ModelForm):
    """Форма для создания урока"""
    
    # Поля для контрольных работ
    variants_count = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=20,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Количество вариантов'
        }),
        label='Количество вариантов'
    )
    tasks_per_variant = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=50,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Заданий в варианте'
        }),
        label='Заданий в варианте'
    )
    task_pool = forms.ModelMultipleChoiceField(
        queryset=Task.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        label='Пул заданий для вариантов'
    )
    
    class Meta:
        model = Lesson
        fields = ['title', 'lesson_type', 'block', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите название урока'
            }),
            'lesson_type': forms.Select(attrs={
                'class': 'form-select',
                'onchange': 'toggleControlFields()'
            }),
            'block': forms.Select(attrs={
                'class': 'form-select'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Описание урока (необязательно)'
            })
        }
        labels = {
            'title': 'Название урока',
            'lesson_type': 'Тип урока',
            'block': 'Блок курса',
            'description': 'Описание урока'
        }
    
    def __init__(self, *args, **kwargs):
        course = kwargs.pop('course', None)
        super().__init__(*args, **kwargs)
        if course:
            self.fields['block'].queryset = CourseBlock.objects.filter(course=course).order_by('order')
            self.fields['block'].empty_label = "Без блока"
            
            # Устанавливаем queryset для пула заданий
            self.fields['task_pool'].queryset = Task.objects.all().order_by('id')
    
    def clean(self):
        cleaned_data = super().clean()
        lesson_type = cleaned_data.get('lesson_type')
        variants_count = cleaned_data.get('variants_count')
        tasks_per_variant = cleaned_data.get('tasks_per_variant')
        task_pool = cleaned_data.get('task_pool')
        
        if lesson_type == 'control':
            if not variants_count or variants_count <= 0:
                raise forms.ValidationError('Для контрольной работы необходимо указать количество вариантов.')
            
            if not tasks_per_variant or tasks_per_variant <= 0:
                raise forms.ValidationError('Для контрольной работы необходимо указать количество заданий в варианте.')
            
            if not task_pool:
                raise forms.ValidationError('Для контрольной работы необходимо выбрать пул заданий.')
            
            # Проверяем, достаточно ли заданий в пуле
            pool_size = len(task_pool)
            required_tasks = variants_count * tasks_per_variant
            
            if pool_size < required_tasks:
                raise forms.ValidationError(
                    f'Недостаточно заданий в пуле. Требуется: {required_tasks}, '
                    f'доступно: {pool_size}. Добавьте больше заданий в пул или уменьшите '
                    f'количество вариантов/заданий в варианте.'
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        lesson = super().save(commit=False)
        
        if commit:
            lesson.save()
            
            # Если это контрольная работа, сохраняем дополнительные поля
            if lesson.lesson_type == 'control':
                lesson.variants_count = self.cleaned_data.get('variants_count', 0)
                lesson.tasks_per_variant = self.cleaned_data.get('tasks_per_variant', 0)
                lesson.save()
                
                # Сохраняем пул заданий
                task_pool = self.cleaned_data.get('task_pool')
                if task_pool:
                    lesson.task_pool.set(task_pool)
        
        return lesson


class LessonEditForm(forms.ModelForm):
    """Форма для редактирования урока"""
    
    class Meta:
        model = Lesson
        fields = ['title', 'lesson_type', 'block', 'description', 'order']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите название урока'
            }),
            'lesson_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'block': forms.Select(attrs={
                'class': 'form-select'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Описание урока (необязательно)'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1
            })
        }
        labels = {
            'title': 'Название урока',
            'lesson_type': 'Тип урока',
            'block': 'Блок курса',
            'description': 'Описание урока',
            'order': 'Порядок в курсе'
        }
    
    def __init__(self, *args, **kwargs):
        course = kwargs.pop('course', None)
        super().__init__(*args, **kwargs)
        if course:
            self.fields['block'].queryset = CourseBlock.objects.filter(course=course).order_by('order')
            self.fields['block'].empty_label = "Без блока"


class CourseFilterForm(forms.Form):
    """Форма для фильтрации курсов"""
    
    COURSE_TYPE_CHOICES = [
        ('', 'Все курсы'),
        ('general', 'Общие курсы'),
        ('personal', 'Личные курсы'),
    ]
    
    course_type = forms.ChoiceField(
        choices=COURSE_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Тип курса'
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Поиск по названию курса...'
        }),
        label='Поиск'
    )


class CourseBlockCreateForm(forms.ModelForm):
    """Форма для создания блока курса"""
    
    class Meta:
        model = CourseBlock
        fields = ['title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите название блока'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Описание блока (необязательно)'
            })
        }
        labels = {
            'title': 'Название блока',
            'description': 'Описание блока'
        }


class CourseBlockEditForm(forms.ModelForm):
    """Форма для редактирования блока курса"""
    
    class Meta:
        model = CourseBlock
        fields = ['title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите название блока'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Описание блока (необязательно)'
            })
        }
        labels = {
            'title': 'Название блока',
            'description': 'Описание блока'
        }
