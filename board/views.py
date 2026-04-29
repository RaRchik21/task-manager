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


from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

User = get_user_model()

@csrf_exempt
def create_test_users(request):
    users_data = [
        {'username': 'TestMS', 'password': 'TestMS1234@weq', 'role': 'junior'},
        {'username': 'TestSpec', 'password': 'TestSpec1234@weq', 'role': 'specialist'},
        {'username': 'TestVS', 'password': 'TestVS1234@weq', 'role': 'lead'},
        {'username': 'TestGS', 'password': 'TestGS1234@weq', 'role': 'chief'},
        {'username': 'TestSS', 'password': 'TestSS1234@weq', 'role': 'senior'},
    ]
    
    results = []
    for user_data in users_data:
        username = user_data['username']
        password = user_data['password']
        role = user_data['role']
        
        try:
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    role=role,
                    email=f"{username}@example.com"
                )
                results.append({'username': username, 'status': 'created', 'role': role})
            else:
                results.append({'username': username, 'status': 'already exists'})
        except Exception as e:
            results.append({'username': username, 'status': 'error', 'error': str(e)})
    
    return JsonResponse({'users': results, 'message': 'Готово! Теперь можно входить'})



from django.http import JsonResponse
from django.core.management import call_command
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def migrate_db(request):
    try:
        call_command('migrate', interactive=False)
        return JsonResponse({'status': 'success', 'message': 'Миграции выполнены'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})
    
    
class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'admin'

class CanCreateColumn(BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['admin', 'chief']

class CanSeeAllTasks(BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['admin', 'chief', 'lead']
ROLE_HIERARCHY = {
    'admin': 6,
    'chief': 5,
    'lead': 4,
    'specialist': 3,
    'senior': 2,
    'junior': 1,
}

class CanManageUsers(BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['admin', 'chief', 'lead']
    
    def has_object_permission(self, request, view, obj):
        # Нельзя менять роль пользователя с более высокой или равной ролью
        requester_level = ROLE_HIERARCHY.get(request.user.role, 0)
        target_level = ROLE_HIERARCHY.get(obj.role, 0)
        return requester_level > target_level

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
            qs = User.objects.exclude(role='admin')
        else:
            qs = User.objects.filter(id=user.id)
        
        if tg:
            qs = qs.filter(telegram_username=tg)
        
        return qs

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        requester_level = ROLE_HIERARCHY.get(request.user.role, 0)
        target_level = ROLE_HIERARCHY.get(instance.role, 0)
        if requester_level <= target_level:
            return Response({'error': 'Нельзя изменить роль пользователя с более высокой или равной ролью'}, status=403)
        return super().partial_update(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'])
    def subordinates(self, request):
        """Получить всех подчинённых текущего пользователя"""
        user = request.user
        result = []

        if user.role == 'specialist':
            # Только свои младшие
            juniors = User.objects.filter(supervisor=user)
            result = list(juniors)

        elif user.role == 'lead':
            # Свои специалисты + их младшие
            specialists = User.objects.filter(supervisor=user)
            result = list(specialists)
            for s in specialists:
                juniors = User.objects.filter(supervisor=s)
                result.extend(juniors)

        elif user.role in ['chief', 'admin']:
            # Все подчинённые рекурсивно
            result = list(User.objects.exclude(id=user.id))

        serializer = UserSerializer(result, many=True)
        return Response(serializer.data)


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
        serializer.save(created_by=self.request.user, is_archived=False)

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        try:
            task = Task.objects.get(pk=pk)
        except Task.DoesNotExist:
            return Response({'error': 'Задача не найдена'}, status=404)
        task.is_archived = True
        task.save()
        return Response({'status': 'archived'})

    @action(detail=True, methods=['post'])
    def unarchive(self, request, pk=None):
        try:
            task = Task.objects.get(pk=pk)
        except Task.DoesNotExist:
            return Response({'error': 'Задача не найдена'}, status=404)
        task.is_archived = False
        task.save()
        return Response({'status': 'unarchived'})
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta

        user = request.user
        
        # Все задачи доступные пользователю
        if user.role in ['admin', 'chief', 'lead']:
            tasks = Task.objects.all()
        elif user.role == 'specialist':
            junior_ids = user.juniors.values_list('id', flat=True)
            tasks = Task.objects.filter(created_by__in=[user.id, *junior_ids])
        else:
            tasks = Task.objects.filter(created_by=user)

        # Статистика по колонкам
        by_column = tasks.filter(is_archived=False).values(
            'column__name', 'column__id'
        ).annotate(count=Count('id'))

        # Статистика по приоритетам
        by_priority = tasks.filter(is_archived=False).values('priority').annotate(count=Count('id'))

        # Статистика по пользователям (только для ГС/ВС)
        by_user = []
        if user.role in ['admin', 'chief', 'lead']:
            by_user = list(tasks.filter(is_archived=False).values(
                'created_by__id',
                'created_by__first_name',
                'created_by__last_name',
                'created_by__username'
            ).annotate(count=Count('id')).order_by('-count')[:10])

        # График активности за 7 дней
        today = timezone.now().date()
        activity = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            count = tasks.filter(created_at__date=day).count()
            activity.append({ 'date': str(day), 'count': count })

        # Просроченные
        overdue = tasks.filter(
            is_archived=False,
            deadline__lt=timezone.now().date()
        ).count()

        return Response({
            'total': tasks.filter(is_archived=False).count(),
            'archived': tasks.filter(is_archived=True).count(),
            'overdue': overdue,
            'chief_goals': tasks.filter(is_archived=False, is_chief_goal=True).count(),
            'by_column': list(by_column),
            'by_priority': list(by_priority),
            'by_user': by_user,
            'activity': activity,
        })

    def destroy(self, request, *args, **kwargs):
        try:
            task = Task.objects.get(pk=kwargs['pk'])
        except Task.DoesNotExist:
            return Response({'error': 'Задача не найдена'}, status=404)
        task.delete()
        return Response(status=204)

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