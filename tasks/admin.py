from django.contrib import admin
from .models import Task

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_task_type_display', 'get_subtype_display', 'get_difficulty_display', 'created_by', 'created_at']
    list_filter = ['task_type', 'difficulty', 'created_at']
    search_fields = ['text', 'correct_answer']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Основная информация', {
            'fields': ('text', 'task_type', 'subtype', 'difficulty', 'correct_answer')
        }),
        ('Файлы', {
            'fields': ('image', 'file')
        }),
        ('Метаданные', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Если это создание нового объекта
            obj.created_by = request.user
        super().save_model(request, obj, form, change)