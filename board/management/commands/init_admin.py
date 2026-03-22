from django.core.management.base import BaseCommand
from board.models import User

class Command(BaseCommand):
    help = 'Назначает роль admin суперпользователю'

    def handle(self, *args, **kwargs):
        try:
            user = User.objects.get(username='admin')
            user.role = 'admin'
            user.save()
            self.stdout.write(self.style.SUCCESS('✅ Роль admin назначена пользователю admin'))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR('❌ Пользователь admin не найден'))