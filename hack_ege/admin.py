from django.contrib import admin
from django.contrib.admin import AdminSite
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.http import HttpResponseRedirect

User = get_user_model()

class CustomAdminSite(AdminSite):
    site_header = 'Система управления пользователями'
    site_title = 'Администрирование'
    index_title = 'Панель управления'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('statistics/', self.admin_view(self.statistics_view), name='statistics'),
            path('bulk-create/', self.admin_view(self.bulk_create_view), name='bulk_create'),
        ]
        return custom_urls + urls
    
    def statistics_view(self, request):
        context = {
            'title': 'Статистика пользователей',
            'total_users': User.objects.count(),
            'admin_count': User.objects.filter(role='admin').count(),
            'teacher_count': User.objects.filter(role='teacher').count(),
            'student_count': User.objects.filter(role='student').count(),
        }
        return render(request, 'admin/statistics.html', context)
    
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

admin_site = CustomAdminSite(name='custom_admin')
