from django import forms
from .models import Task, ImportSession
import json

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['text', 'task_type', 'subtype', 'difficulty', 'correct_answer', 'is_html', 'image', 'file']
        widgets = {
            'text': forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
            'task_type': forms.Select(attrs={'class': 'form-select', 'onchange': 'updateSubtypes()'}),
            'subtype': forms.Select(attrs={'class': 'form-select'}),
            'difficulty': forms.Select(attrs={'class': 'form-select'}),
            'correct_answer': forms.TextInput(attrs={'class': 'form-control'}),
            'is_html': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'text': 'Текст задания',
            'task_type': 'Тип задания',
            'subtype': 'Подтип задания',
            'difficulty': 'Сложность',
            'correct_answer': 'Правильный ответ',
            'is_html': 'HTML разметка',
            'image': 'Изображение',
            'file': 'Файл',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Устанавливаем подтипы на основе выбранного типа
        if 'task_type' in self.data:
            task_type = self.data.get('task_type')
            if task_type in Task.SUBTYPE_CHOICES:
                self.fields['subtype'].choices = Task.SUBTYPE_CHOICES[task_type]
        elif self.instance.pk:
            self.fields['subtype'].choices = self.instance.get_subtype_choices()

class TaskFilterForm(forms.Form):
    task_type = forms.ChoiceField(
        choices=[('', 'Все типы')] + Task.TASK_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'onchange': 'updateSubtypes()'})
    )
    subtype = forms.ChoiceField(
        choices=[('', 'Все подтипы')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    difficulty = forms.ChoiceField(
        choices=[('', 'Все сложности')] + Task.DIFFICULTY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    task_id = forms.IntegerField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ID задания',
            'style': 'width: 100%; min-width: 120px;',
            'inputmode': 'numeric',
            'pattern': '[0-9]*'
        })
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Поиск по тексту, ответу, типу задания...'
        })
    )


class BulkImportForm(forms.Form):
    json_file = forms.FileField(
        label='JSON файл с заданиями',
        help_text='Загрузите JSON файл с массивом заданий',
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.json'})
    )
    task_type = forms.ChoiceField(
        choices=Task.TASK_TYPE_CHOICES,
        label='Тип заданий',
        help_text='Выберите тип для всех импортируемых заданий',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    subtype = forms.ChoiceField(
        choices=[('', 'Выберите подтип')],
        label='Подтип заданий',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Устанавливаем подтипы на основе выбранного типа
        if 'task_type' in self.data:
            task_type = self.data.get('task_type')
            if task_type in Task.SUBTYPE_CHOICES:
                self.fields['subtype'].choices = [('', 'Выберите подтип')] + Task.SUBTYPE_CHOICES[task_type]

    def clean_json_file(self):
        file = self.cleaned_data.get('json_file')
        if file:
            try:
                # Сохраняем текущую позицию
                current_position = file.tell()
                
                # Читаем содержимое файла
                content = file.read().decode('utf-8')
                
                # Возвращаем указатель в исходную позицию
                file.seek(current_position)
                
                data = json.loads(content)
                
                # Проверяем, что это массив
                if not isinstance(data, list):
                    raise forms.ValidationError('JSON файл должен содержать массив заданий')
                
                # Проверяем структуру каждого задания
                for i, task in enumerate(data):
                    if not isinstance(task, dict):
                        raise forms.ValidationError(f'Задание {i+1} должно быть объектом')
                    
                    required_fields = ['text', 'key']
                    for field in required_fields:
                        if field not in task:
                            raise forms.ValidationError(f'Задание {i+1} не содержит обязательное поле "{field}"')
                    
                    # Проверяем, что есть поле difficulty (не обязательно)
                    if 'difficulty' not in task:
                        # Если нет поля difficulty, добавляем значение по умолчанию
                        task['difficulty'] = 0
                
                return file
                
            except json.JSONDecodeError:
                raise forms.ValidationError('Неверный формат JSON файла')
            except UnicodeDecodeError:
                raise forms.ValidationError('Файл должен быть в кодировке UTF-8')
        
        return file
