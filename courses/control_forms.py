from django import forms
from .models import CourseBlock
from tasks.forms import TaskFilterForm


class ControlLessonStep1Form(forms.Form):
    """Этап 1: Название урока и тип"""
    
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите название контрольной работы'
        }),
        label='Название контрольной работы'
    )
    
    block = forms.ModelChoiceField(
        queryset=CourseBlock.objects.none(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Блок курса',
        empty_label="Без блока"
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Описание контрольной работы (необязательно)'
        }),
        label='Описание'
    )
    
    def __init__(self, *args, **kwargs):
        course = kwargs.pop('course', None)
        super().__init__(*args, **kwargs)
        if course:
            self.fields['block'].queryset = CourseBlock.objects.filter(course=course).order_by('order')


class ControlLessonStep2Form(forms.Form):
    """Этап 2: Выбор пула заданий"""
    
    # Скрытое поле для хранения выбранных заданий
    selected_tasks = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )


class ControlLessonStep3Form(forms.Form):
    """Этап 3: Настройка времени выполнения и вариантов"""
    
    variants_count = forms.IntegerField(
        min_value=1,
        max_value=20,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Количество вариантов'
        }),
        label='Количество вариантов'
    )
    
    tasks_per_variant = forms.IntegerField(
        min_value=1,
        max_value=50,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Заданий в варианте'
        }),
        label='Заданий в варианте'
    )
    
    time_limit = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=480,  # 8 часов максимум
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Время выполнения в минутах'
        }),
        label='Время выполнения (минуты)',
        help_text='Оставьте пустым для неограниченного времени'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        variants_count = cleaned_data.get('variants_count')
        tasks_per_variant = cleaned_data.get('tasks_per_variant')
        
        # Получаем количество выбранных заданий из сессии
        selected_tasks_count = self.initial.get('selected_tasks_count', 0)
        min_required_tasks = tasks_per_variant  # Минимум = заданий в одном варианте
        
        if selected_tasks_count < min_required_tasks:
            raise forms.ValidationError(
                f'Недостаточно заданий в пуле. Минимум требуется: {min_required_tasks}, '
                f'доступно: {selected_tasks_count}. Вернитесь к предыдущему шагу '
                f'и выберите больше заданий.'
            )
        
        return cleaned_data


class ControlLessonStep4Form(forms.Form):
    """Этап 4: Подтверждение и генерация"""
    
    confirm_generation = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='Подтверждаю создание контрольной работы с вариантами'
    )
