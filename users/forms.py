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
        super().__init__(*args, **kwargs)
        if user:
            self.fields['students'].queryset = User.objects.filter(
                role='student',
                created_by=user
            )
