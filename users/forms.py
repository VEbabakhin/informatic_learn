from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Group, UserGroup

class AddTeacherForm(forms.Form):
    first_name = forms.CharField(max_length=30, label='Имя', widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, label='Фамилия', widget=forms.TextInput(attrs={'class': 'form-control'}))

class AddStudentForm(forms.Form):
    students_data = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5, 'cols': 25, 'class': 'form-control'}),
        label='Данные учеников',
        help_text='Введите данные учеников в формате: Фамилия И. (каждый ученик с новой строки)'
    )

class CreateGroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name']
        labels = {
            'name': 'Название группы'
        }

class AddStudentsToGroupForm(forms.Form):
    students = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label='Выберите учеников для добавления в группу'
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        group = kwargs.pop('group', None)
        super().__init__(*args, **kwargs)
        if user:
            # Исключаем уже добавленных в группу учеников
            if group:
                existing_students = group.students.all()
                self.fields['students'].queryset = User.objects.filter(
                    role='student',
                    created_by=user
                ).exclude(id__in=existing_students)
            else:
                self.fields['students'].queryset = User.objects.filter(
                    role='student',
                    created_by=user
                )

class EditGroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name']
        labels = {
            'name': 'Название группы'
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'})
        }

class RemoveStudentsFromGroupForm(forms.Form):
    students = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label='Выберите учеников для удаления из группы'
    )
    
    def __init__(self, *args, **kwargs):
        group = kwargs.pop('group', None)
        super().__init__(*args, **kwargs)
        if group:
            self.fields['students'].queryset = group.students.all()

class SimpleGroupEditForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        label='Название группы',
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg'})
    )
