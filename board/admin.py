from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Column, Task

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'role', 'telegram_username', 'supervisor']
    fieldsets = UserAdmin.fieldsets + (
        ('Доп. информация', {'fields': ('role', 'telegram_username', 'supervisor')}),
    )

@admin.register(Column)
class ColumnAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'order']

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'time', 'column', 'created_by']