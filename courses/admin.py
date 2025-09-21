from django.contrib import admin
from .models import Course, CourseBlock, Lesson, LessonTask, LessonAssignment


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'course_type', 'created_by', 'created_at', 'is_active', 'lessons_count']
    list_filter = ['course_type', 'is_active', 'created_at']
    search_fields = ['title', 'description', 'created_by__username', 'created_by__first_name', 'created_by__last_name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def lessons_count(self, obj):
        return obj.get_lessons_count()
    lessons_count.short_description = 'Количество уроков'


@admin.register(CourseBlock)
class CourseBlockAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'order', 'created_at']
    list_filter = ['course', 'created_at']
    search_fields = ['title', 'description', 'course__title']
    readonly_fields = ['created_at']
    ordering = ['course', 'order']


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ['get_full_title', 'course', 'block', 'lesson_type', 'order', 'created_at', 'is_active']
    list_filter = ['lesson_type', 'is_active', 'created_at', 'course', 'block']
    search_fields = ['title', 'description', 'course__title', 'block__title']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['course', 'block', 'order', 'created_at']
    
    def get_full_title(self, obj):
        return obj.get_full_title()
    get_full_title.short_description = 'Полное название'


@admin.register(LessonTask)
class LessonTaskAdmin(admin.ModelAdmin):
    list_display = ['lesson', 'task', 'order', 'added_by', 'created_at', 'is_active']
    list_filter = ['is_active', 'created_at', 'lesson__course']
    search_fields = ['lesson__title', 'task__id', 'added_by__username']
    readonly_fields = ['created_at']
    ordering = ['lesson', 'order', 'created_at']


@admin.register(LessonAssignment)
class LessonAssignmentAdmin(admin.ModelAdmin):
    list_display = ['lesson', 'group', 'assigned_by', 'assigned_at', 'due_date', 'is_active']
    list_filter = ['is_active', 'assigned_at', 'due_date', 'lesson__course', 'lesson__lesson_type']
    search_fields = ['lesson__title', 'group__name', 'assigned_by__username']
    readonly_fields = ['assigned_at']
    ordering = ['-assigned_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('lesson', 'lesson__course', 'group', 'assigned_by')