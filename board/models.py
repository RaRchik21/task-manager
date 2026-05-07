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


class Board(models.Model):
    PRIVACY_CHOICES = [
        ('public', 'Публичная'),
        ('private', 'Приватная'),
    ]
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_boards')
    created_at = models.DateTimeField(auto_now_add=True)
    privacy = models.CharField(max_length=20, choices=PRIVACY_CHOICES, default='public')
    allow_anyone_view = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class BoardMembership(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Администратор доски'),
        ('editor', 'Редактор'),
        ('viewer', 'Зритель'),
    ]
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='board_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer')
    joined_at = models.DateTimeField(auto_now_add=True)
    # Права доступа
    view_all_tasks = models.BooleanField(default=False, help_text='Может просматривать все задачи на доске')
    edit_columns = models.BooleanField(default=False, help_text='Может редактировать колонки')
    reorder_columns = models.BooleanField(default=False, help_text='Может менять порядок колонок')

    class Meta:
        unique_together = ('board', 'user')

    def __str__(self):
        return f'{self.user.get_full_name_display()} — {self.board.name} ({self.get_role_display()})'


class BoardChatMessage(models.Model):
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='chat_messages')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='board_messages')
    reply_to = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='replies')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.author.username}: {self.text[:40]}'


class Column(models.Model):
    name = models.CharField(max_length=100)
    order = models.IntegerField(default=0)
    color = models.CharField(max_length=20, default='#E8E2D8')
    is_collapsed = models.BooleanField(default=False)
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='columns', null=True, blank=True)

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
    assigned_to = models.ManyToManyField(User, related_name='assigned_tasks', blank=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='delegated_tasks')

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.title} → {self.column.name}"
    

class TaskComment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    mentioned_users = models.ManyToManyField(User, related_name='mentioned_in', blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')  # ← добавить

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.author.username} → {self.task.title}"


class Notification(models.Model):
    TYPES = [
        ('assigned', 'Назначен исполнителем'),
        ('mentioned', 'Упомянут в комментарии'),
        ('suggested', 'Предложена задача'),
        ('delegated', 'Делегирована задача'),
    ]
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications', null=True, blank=True)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    type = models.CharField(max_length=20, choices=TYPES)
    text = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    board = models.ForeignKey(Board, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.type} → {self.recipient.username}"