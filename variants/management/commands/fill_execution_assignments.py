from django.core.management.base import BaseCommand
from variants.models import VariantExecution, VariantAssignment


class Command(BaseCommand):
    help = 'Заполняет поле assignment для существующих выполнений'

    def handle(self, *args, **options):
        # Находим все выполнения без назначения
        executions_without_assignment = VariantExecution.objects.filter(assignment__isnull=True)
        
        updated_count = 0
        skipped_count = 0
        
        for execution in executions_without_assignment:
            # Ищем самое подходящее назначение (самое новое активное)
            assignment = VariantAssignment.objects.filter(
                variant=execution.variant,
                student=execution.student,
                is_active=True
            ).order_by('-assigned_at').first()
            
            if assignment:
                # Проверяем, нет ли уже выполнения для этого назначения
                existing_execution = VariantExecution.objects.filter(assignment=assignment).first()
                if not existing_execution:
                    execution.assignment = assignment
                    execution.save()
                    updated_count += 1
                else:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'Пропущено выполнение {execution.id}: для назначения {assignment.id} уже есть выполнение'
                        )
                    )
            else:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'Пропущено выполнение {execution.id}: не найдено активное назначение'
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Обновлено выполнений: {updated_count}, пропущено: {skipped_count}'
            )
        )

