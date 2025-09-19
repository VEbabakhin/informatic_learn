from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render
from django.contrib import messages
from django.http import HttpResponseRedirect
from .models import User, Group, UserGroup

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'get_full_name', 'role', 'created_by', 'is_password_changed', 'is_active')
    list_filter = ('role', 'is_password_changed', 'is_active', 'created_by')
    search_fields = ('username', 'first_name', 'last_name')
    readonly_fields = ('created_by', 'date_joined', 'last_login')
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Персональная информация', {'fields': ('first_name', 'last_name', 'email')}),
        ('Права доступа', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Роль и создание', {'fields': ('role', 'created_by', 'is_password_changed')}),
        ('Важные даты', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'first_name', 'last_name', 'role', 'password1', 'password2'),
        }),
    )
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('bulk-create/', self.admin_view(self.bulk_create_view), name='bulk_create'),
        ]
        return custom_urls + urls
    
    def bulk_create_view(self, request):
        if request.method == 'POST':
            users_data = request.POST.get('users_data', '')
            role = request.POST.get('role', 'student')
            
            if users_data:
                users_list = [line.strip() for line in users_data.split('\n') if line.strip()]
                created_count = 0
                
                for user_data in users_list:
                    try:
                        last_name, first_name = user_data.split(' ', 1)
                        username = f"{last_name.lower()}_{first_name.lower().replace(' ', '_')}"
                        
                        # Проверяем уникальность логина
                        counter = 1
                        original_username = username
                        while User.objects.filter(username=username).exists():
                            username = f"{original_username}{counter}"
                            counter += 1
                        
                        User.objects.create_user(
                            username=username,
                            first_name=first_name,
                            last_name=last_name,
                            role=role,
                            created_by=request.user,
                            password=f"{role}_psw"
                        )
                        created_count += 1
                    except ValueError:
                        messages.error(request, f'Неверный формат данных: {user_data}')
                        continue
                
                if created_count > 0:
                    messages.success(request, f'Успешно создано {created_count} пользователей')
                    return HttpResponseRedirect('..')
        
        return render(request, 'admin/bulk_create.html')

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_by', 'created_at', 'student_count')
    list_filter = ('created_by', 'created_at')
    search_fields = ('name',)
    
    def student_count(self, obj):
        return obj.group_users.count()
    student_count.short_description = 'Количество учеников'

@admin.register(UserGroup)
class UserGroupAdmin(admin.ModelAdmin):
    list_display = ('user', 'group')
    list_filter = ('group',)
    search_fields = ('user__username', 'group__name')
