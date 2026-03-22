from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import BasePermission, IsAuthenticated
from .models import User, Column, Task, BoardSettings
from .serializers import (UserSerializer, UserCreateSerializer,
                          ColumnSerializer, TaskSerializer, BoardSettingsSerializer)


# ═══════════════════════════════
#         ПЕРМИШЕНЫ
# ═══════════════════════════════

class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'admin'

class CanCreateColumn(BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['admin', 'chief']

class CanSeeAllTasks(BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['admin', 'chief', 'lead']

class CanManageUsers(BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['admin', 'chief', 'lead']


# ═══════════════════════════════
#         ПОЛЬЗОВАТЕЛИ
# ═══════════════════════════════

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), IsAdmin()]
        if self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), CanManageUsers()]
        if self.action == 'destroy':
            return [IsAuthenticated(), IsAdmin()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        user = self.request.user
        tg = self.request.query_params.get('tg', None)
        
        if user.role in ['admin', 'chief', 'lead']:
            qs = User.objects.all()
        else:
            qs = User.objects.filter(id=user.id)
        
        if tg:
            qs = qs.filter(telegram_username=tg)
        
        return qs


# ═══════════════════════════════
#           КОЛОНКИ
# ═══════════════════════════════

class ColumnViewSet(viewsets.ModelViewSet):
    queryset = Column.objects.all()
    serializer_class = ColumnSerializer

    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            return [IsAuthenticated(), CanCreateColumn()]
        if self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), CanManageUsers()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, CanCreateColumn])
    def reorder(self, request):
        """Изменить порядок колонок"""
        orders = request.data.get('orders', [])
        for item in orders:
            Column.objects.filter(id=item['id']).update(order=item['order'])
        return Response({'status': 'ok'})


# ═══════════════════════════════
#            ЗАДАЧИ
# ═══════════════════════════════

class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer

    def get_queryset(self):
        user = self.request.user
        show_archived = self.request.query_params.get('archived', 'false') == 'true'

        if user.role in ['admin', 'chief', 'lead']:
            qs = Task.objects.all().select_related('created_by', 'column')
        elif user.role == 'specialist':
            junior_ids = user.juniors.values_list('id', flat=True)
            qs = Task.objects.filter(
                created_by__in=[user.id, *junior_ids]
            ).select_related('created_by', 'column')
        else:
            qs = Task.objects.filter(created_by=user).select_related('created_by', 'column')

        if not show_archived:
            qs = qs.filter(is_archived=False)

        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        task = self.get_object()
        task.is_archived = True
        task.save()
        return Response({'status': 'archived'})

    @action(detail=True, methods=['post'])
    def unarchive(self, request, pk=None):
        task = self.get_object()
        task.is_archived = False
        task.save()
        return Response({'status': 'unarchived'})

    @action(detail=False, methods=['post'])
    def create_for_user(self, request):
        """Создать задачу от имени пользователя по telegram_username"""
        tg = request.data.get('telegram_username')
        try:
            target_user = User.objects.get(telegram_username=tg)
        except User.DoesNotExist:
            return Response({'error': f'Пользователь с TG @{tg} не найден'}, status=404)

        serializer = TaskSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=target_user)
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


# ═══════════════════════════════
#       НАСТРОЙКИ ДОСКИ
# ═══════════════════════════════

class BoardSettingsViewSet(viewsets.ModelViewSet):
    serializer_class = BoardSettingsSerializer

    def get_permissions(self):
        if self.request.method in ['POST', 'PUT', 'PATCH']:
            return [IsAuthenticated(), CanManageUsers()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return BoardSettings.objects.all()

    def get_object(self):
        obj, _ = BoardSettings.objects.get_or_create(id=1)
        return obj

    @action(detail=False, methods=['get'])
    def current(self, request):
        obj, _ = BoardSettings.objects.get_or_create(id=1)
        return Response(BoardSettingsSerializer(obj).data)

    @action(detail=False, methods=['patch'], permission_classes=[IsAuthenticated, CanManageUsers])
    def update_settings(self, request):
        obj, _ = BoardSettings.objects.get_or_create(id=1)
        serializer = BoardSettingsSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)