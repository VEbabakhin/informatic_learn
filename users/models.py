from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator

class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Администратор'),
        ('teacher', 'Учитель'),
        ('student', 'Ученик'),
    ]
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='admin')
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    created_by = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='created_users')
    is_password_changed = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.last_name} {self.first_name} ({self.get_role_display()})"
    
    def get_full_name(self):
        return f"{self.last_name} {self.first_name}".strip()
    
    def can_manage_user(self, user):
        """Проверяет, может ли текущий пользователь управлять указанным пользователем"""
        if self.role == 'admin':
            return True  # Администратор может управлять всеми пользователями
        elif self.role == 'teacher':
            return user.role == 'student' and user.created_by == self  # Учитель может управлять только своими учениками
        return False

class Group(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_groups')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class UserGroup(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_groups')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='group_users')
    
    class Meta:
        unique_together = ('user', 'group')
    
    def __str__(self):
        return f"{self.user} в группе {self.group}"
