from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Group, UserGroup

User = get_user_model()

class UserModelTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            first_name='Администратор',
            last_name='Системы',
            role='admin',
            password='admin_psw'
        )
        
        self.teacher = User.objects.create_user(
            username='teacher',
            first_name='Учитель',
            last_name='Тестовый',
            role='teacher',
            password='teacher_psw',
            created_by=self.admin
        )
        
        self.student = User.objects.create_user(
            username='student',
            first_name='Ученик',
            last_name='Тестовый',
            role='student',
            password='student_psw',
            created_by=self.teacher
        )

    def test_user_creation(self):
        self.assertEqual(self.admin.role, 'admin')
        self.assertEqual(self.teacher.role, 'teacher')
        self.assertEqual(self.student.role, 'student')

    def test_user_full_name(self):
        self.assertEqual(self.admin.get_full_name(), 'Системы Администратор')
        self.assertEqual(self.teacher.get_full_name(), 'Тестовый Учитель')
        self.assertEqual(self.student.get_full_name(), 'Тестовый Ученик')

    def test_can_manage_user(self):
        # Администратор может управлять учителем и учеником
        self.assertTrue(self.admin.can_manage_user(self.teacher))
        self.assertTrue(self.admin.can_manage_user(self.student))
        
        # Администратор не может управлять другим администратором
        admin2 = User.objects.create_user(
            username='admin2',
            first_name='Администратор2',
            last_name='Системы2',
            role='admin',
            password='admin_psw'
        )
        self.assertFalse(self.admin.can_manage_user(admin2))
        
        # Учитель может управлять только своими учениками
        self.assertTrue(self.teacher.can_manage_user(self.student))
        self.assertFalse(self.teacher.can_manage_user(self.admin))
        
        # Ученик не может управлять никем
        self.assertFalse(self.student.can_manage_user(self.teacher))

class GroupModelTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            first_name='Администратор',
            last_name='Системы',
            role='admin',
            password='admin_psw'
        )
        
        self.student = User.objects.create_user(
            username='student',
            first_name='Ученик',
            last_name='Тестовый',
            role='student',
            password='student_psw',
            created_by=self.admin
        )

    def test_group_creation(self):
        group = Group.objects.create(
            name='Тестовая группа',
            created_by=self.admin
        )
        self.assertEqual(group.name, 'Тестовая группа')
        self.assertEqual(group.created_by, self.admin)

    def test_user_group_relationship(self):
        group = Group.objects.create(
            name='Тестовая группа',
            created_by=self.admin
        )
        
        user_group = UserGroup.objects.create(
            user=self.student,
            group=group
        )
        
        self.assertEqual(user_group.user, self.student)
        self.assertEqual(user_group.group, group)
