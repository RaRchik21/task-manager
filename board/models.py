from django.contrib.auth.models import AbstractUser
from django.db import models

ROLE_CHOICES = [
    ('admin', 'Admin'),
    ('chief', 'Главный специалист'),
    ('lead', 'Ведущий специалист'),
    ('specialist', 'Специалист'),
    ('senior', 'Старший специалист'),
    ('junior', 'Младший специалист'),
]

PRIORITY_CHOICES = [
    ('low', 'Низкий'),
    ('medium', 'Средний'),
    ('high', 'Высокий'),
]

class User(AbstractUser):
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='junior')
    telegram_username = models.CharField(max_length=100, blank=True, null=True)
    is_hidden = models.BooleanField(default=False)
    supervisor = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='juniors'
    )

    def get_full_name_display(self):
        if self.first_name and self.last_name:
            return f"{self.last_name} {self.first_name}"
        return self.username

    def __str__(self):
        return f"{self.get_full_name_display()} ({self.get_role_display()})"


class BoardSettings(models.Model):
    system_name = models.CharField(max_length=100, default='Task Manager')
    
    # Новые поля для фона
    bg_gradient = models.TextField(blank=True, null=True)
    bg_color1 = models.CharField(max_length=20, blank=True, null=True)
    bg_color2 = models.CharField(max_length=20, blank=True, null=True)
    bg_angle = models.IntegerField(default=135)
    header_color = models.CharField(max_length=20, default='#EDE8DF')
    card_color = models.CharField(max_length=20, default='#FFFFFF')
    bg_opacity_header = models.IntegerField(default=85)
    bg_opacity_column = models.IntegerField(default=70)
    bg_opacity_card = models.IntegerField(default=85)
    
    class Meta:
        verbose_name = 'Настройки доски'

    def __str__(self):
        return 'Настройки доски'


class Column(models.Model):
    name = models.CharField(max_length=100)
    order = models.IntegerField(default=0)
    color = models.CharField(max_length=20, default='#E8E2D8')
    is_collapsed = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


class Task(models.Model):
    title = models.CharField(max_length=255)
    time = models.CharField(max_length=20, blank=True, null=True)
    comment = models.TextField(blank=True, null=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    deadline = models.DateField(blank=True, null=True)
    is_archived = models.BooleanField(default=False)
    is_chief_goal = models.BooleanField(default=False)
    column = models.ForeignKey(Column, on_delete=models.CASCADE, related_name='tasks')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.title} → {self.column.name}"