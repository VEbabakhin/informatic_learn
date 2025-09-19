from django.core.management.base import BaseCommand
from users.models import User

class Command(BaseCommand):
    help = 'Создает первого администратора с паролем по умолчанию'

    def handle(self, *args, **options):
        if User.objects.filter(role='admin').exists():
            self.stdout.write(
                self.style.WARNING('Администратор уже существует')
            )
            return

        admin = User.objects.create_user(
            username='admin',
            first_name='Администратор',
            last_name='Системы',
            role='admin',
            password='admin_psw'
        )

        self.stdout.write(
            self.style.SUCCESS(f'Администратор {admin.get_full_name()} создан с паролем admin_psw')
        )
