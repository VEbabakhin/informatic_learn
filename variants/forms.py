from django import forms
from .models import Variant, VariantAssignment
from tasks.models import Task
from users.models import Group


class VariantForm(forms.ModelForm):
    """Форма для создания варианта"""
    class Meta:
        model = Variant
        fields = ['name', 'task_type', 'variant_type', 'time_limit_minutes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'task_type': forms.Select(attrs={'class': 'form-select'}),
            'variant_type': forms.Select(attrs={'class': 'form-select'}),
            'time_limit_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }
        labels = {
            'name': 'Название варианта',
            'task_type': 'Тип задания',
            'variant_type': 'Тип варианта',
            'time_limit_minutes': 'Ограничение по времени (минуты)',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем task_type необязательным
        self.fields['task_type'].required = False
        self.fields['task_type'].choices = [('', '---------')] + list(Variant.TASK_TYPE_CHOICES)
        self.fields['time_limit_minutes'].required = False


class VariantFromTemplateForm(forms.Form):
    """Форма для создания варианта по шаблону"""
    name = forms.CharField(
        label='Название варианта',
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='К названию будет добавлен номер варианта (например, "Вариант 1", "Вариант 2")'
    )
    task_type = forms.ChoiceField(
        label='Тип задания',
        choices=[('', '---------')] + list(Variant.TASK_TYPE_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    variant_type = forms.ChoiceField(
        label='Тип варианта',
        choices=Variant.VARIANT_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='normal'
    )
    time_limit_minutes = forms.IntegerField(
        label='Ограничение по времени (минуты)',
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        help_text='Оставьте пустым, если ограничение по времени не требуется'
    )
    tasks_per_variant = forms.IntegerField(
        label='Количество заданий в варианте',
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1})
    )
    variants_count = forms.IntegerField(
        label='Количество вариантов',
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1})
    )
    task_pool = forms.ModelMultipleChoiceField(
        label='Пул заданий',
        queryset=Task.objects.all(),
        widget=forms.CheckboxSelectMultiple(),
        help_text='Выберите задания для пула. Задания будут распределены между вариантами максимально разнообразно.'
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            # Показываем все задания, доступные пользователю
            self.fields['task_pool'].queryset = Task.objects.all()
        # Фильтруем по выбранному типу задания, если он указан
        self.fields['task_pool'].widget.attrs['class'] = 'form-check-input'


class VariantFromSpecificTasksForm(forms.ModelForm):
    """Форма для создания варианта из конкретных заданий"""
    tasks = forms.ModelMultipleChoiceField(
        label='Задания',
        queryset=Task.objects.all(),
        widget=forms.CheckboxSelectMultiple(),
        help_text='Выберите конкретные задания для варианта'
    )
    
    class Meta:
        model = Variant
        fields = ['name', 'task_type', 'variant_type', 'time_limit_minutes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'task_type': forms.Select(attrs={'class': 'form-select'}),
            'variant_type': forms.Select(attrs={'class': 'form-select'}),
            'time_limit_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }
        labels = {
            'name': 'Название варианта',
            'task_type': 'Тип задания',
            'variant_type': 'Тип варианта',
            'time_limit_minutes': 'Ограничение по времени (минуты)',
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['task_type'].required = False
        self.fields['task_type'].choices = [('', '---------')] + list(Variant.TASK_TYPE_CHOICES)
        self.fields['time_limit_minutes'].required = False
        self.fields['tasks'].widget.attrs['class'] = 'form-check-input'


class AssignVariantToStudentForm(forms.Form):
    """Форма для назначения варианта конкретному ученику"""
    variant = forms.ModelChoiceField(
        label='Вариант',
        queryset=Variant.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True
    )
    student = forms.ModelChoiceField(
        label='Ученик',
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True
    )
    deadline = forms.DateTimeField(
        label='Срок выполнения',
        required=False,
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        help_text='Оставьте пустым, если срок не установлен'
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            # Показываем только варианты, созданные текущим пользователем
            self.fields['variant'].queryset = Variant.objects.filter(created_by=user)
            # Показываем только учеников текущего пользователя
            if user.role == 'admin':
                self.fields['student'].queryset = user.__class__.objects.filter(role='student')
            else:
                self.fields['student'].queryset = user.__class__.objects.filter(role='student', created_by=user)


class AssignVariantsToGroupForm(forms.Form):
    """Форма для назначения вариантов группе"""
    group = forms.ModelChoiceField(
        label='Группа',
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True
    )
    variants = forms.ModelMultipleChoiceField(
        label='Варианты',
        queryset=Variant.objects.none(),
        widget=forms.CheckboxSelectMultiple(),
        required=True,
        help_text='Выберите варианты для распределения между учениками группы'
    )
    deadline = forms.DateTimeField(
        label='Срок выполнения',
        required=False,
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        help_text='Оставьте пустым, если срок не установлен'
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            # Показываем только группы, созданные текущим пользователем
            self.fields['group'].queryset = Group.objects.filter(created_by=user)
            # Показываем только варианты, созданные текущим пользователем
            self.fields['variants'].queryset = Variant.objects.filter(created_by=user)
        self.fields['variants'].widget.attrs['class'] = 'form-check-input'


class VariantByNumberForm(forms.Form):
    """Форма для выполнения варианта по номеру"""
    variant_id = forms.IntegerField(
        label='Номер варианта',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Введите номер варианта'}),
        required=True,
        help_text='Введите ID варианта для начала выполнения'
    )
