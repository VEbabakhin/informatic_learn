from django.core.management.base import BaseCommand
from courses.models import LessonExecution


class Command(BaseCommand):
    help = 'Деактивирует выполнения уроков с отмененными назначениями'

    def handle(self, *args, **options):
        # Находим выполнения с отмененными назначениями
        executions_with_cancelled_assignments = LessonExecution.objects.filter(
            assignment__is_active=False,
            is_active=True
        )
        
        count = executions_with_cancelled_assignments.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('Нет выполнений с отмененными назначениями для очистки.')
            )
            return
        
        # Деактивируем их
        deactivated_count = 0
        for execution in executions_with_cancelled_assignments:
            execution.is_active = False
            execution.save()
            deactivated_count += 1
            self.stdout.write(f'Деактивировано: {execution.student.get_full_name()} - {execution.lesson.title}')
        
        self.stdout.write(
            self.style.SUCCESS(f'Успешно деактивировано {deactivated_count} выполнений.')
        )
