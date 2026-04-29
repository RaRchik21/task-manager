from rest_framework import serializers
from .models import User, Column, Task, BoardSettings

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name', 
          'role', 'telegram_username', 'supervisor', 'is_hidden']
        read_only_fields = ['id']

    def get_full_name(self, obj):
        return obj.get_full_name_display()


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'first_name', 'last_name', 'role', 'telegram_username', 'supervisor']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class ColumnSerializer(serializers.ModelSerializer):
    class Meta:
        model = Column
        fields = ['id', 'name', 'order', 'color', 'is_collapsed']


class TaskSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = ['id', 'title', 'comment', 'priority', 'deadline',
                  'is_archived', 'is_chief_goal', 'column', 'created_by',
                  'created_by_name', 'created_at']
        read_only_fields = ['id', 'created_by', 'created_at']

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name_display()
    

class BoardSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BoardSettings
        fields = ['system_name', 'bg_gradient', 'bg_color1', 'bg_color2', 'bg_angle', 
                  'header_color', 'card_color', 'bg_opacity_header', 
                  'bg_opacity_column', 'bg_opacity_card']