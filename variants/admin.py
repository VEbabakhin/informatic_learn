from django.contrib import admin
from .models import Variant, VariantTask, VariantExecution, VariantAssignment


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    list_display = ['name', 'task_type', 'variant_type', 'get_tasks_count', 'time_limit_minutes', 'created_by', 'created_at']
    list_filter = ['variant_type', 'task_type', 'created_at']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(VariantTask)
class VariantTaskAdmin(admin.ModelAdmin):
    list_display = ['variant', 'task', 'order']
    list_filter = ['variant']


@admin.register(VariantExecution)
class VariantExecutionAdmin(admin.ModelAdmin):
    list_display = ['variant', 'student', 'status', 'started_at', 'completed_at']
    list_filter = ['status', 'started_at']
    search_fields = ['variant__name', 'student__username', 'student__first_name', 'student__last_name']
    readonly_fields = ['started_at', 'completed_at']


@admin.register(VariantAssignment)
class VariantAssignmentAdmin(admin.ModelAdmin):
    list_display = ['variant', 'student', 'assigned_by', 'assigned_at', 'deadline', 'is_active']
    list_filter = ['is_active', 'assigned_at', 'deadline']
    search_fields = ['variant__name', 'student__username', 'student__first_name', 'student__last_name']
    readonly_fields = ['assigned_at']
