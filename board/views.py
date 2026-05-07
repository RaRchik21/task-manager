from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.permissions import BasePermission, IsAuthenticated
from .models import User, Column, Task, BoardSettings, Board, BoardMembership, BoardChatMessage, Notification, TaskComment
from .serializers import (UserSerializer, UserCreateSerializer,
                          ColumnSerializer, TaskSerializer, BoardSettingsSerializer, BoardSerializer, BoardMembershipSerializer, BoardChatMessageSerializer,
                          NotificationSerializer, UserShortSerializer, TaskCommentSerializer)


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
                    username=username, password=password, role=role,
                    email=f"{username}@example.com"
                )
                results.append({'username': username, 'status': 'created', 'role': role})
            else:
                results.append({'username': username, 'status': 'already exists'})
        except Exception as e:
            results.append({'username': username, 'status': 'error', 'error': str(e)})
    
    return JsonResponse({'users': results, 'message': 'Готово! Теперь можно входить'})


@csrf_exempt
def create_admin(request):
    User = get_user_model()
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
        return JsonResponse({'status': 'created', 'username': 'admin', 'password': 'admin123'})
    return JsonResponse({'status': 'already exists'})


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
        if request.user.role in ['admin', 'chief']:
            return True
        # Проверяем права на доске
        board_id = request.data.get('board') or request.query_params.get('board')
        if board_id:
            try:
                membership = BoardMembership.objects.get(board_id=board_id, user=request.user)
                return membership.edit_columns
            except BoardMembership.DoesNotExist:
                pass
        return False

class CanEditColumn(BasePermission):
    def has_permission(self, request, view):
        if request.user.role in ['admin', 'chief', 'lead']:
            return True
        # Проверяем права на доске
        board_id = request.data.get('board') or request.query_params.get('board')
        if board_id:
            try:
                membership = BoardMembership.objects.get(board_id=board_id, user=request.user)
                return membership.edit_columns
            except BoardMembership.DoesNotExist:
                pass
        return False

class CanSeeAllTasks(BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['admin', 'chief', 'lead']

ROLE_HIERARCHY = {
    'admin': 6, 'chief': 5, 'lead': 4, 'specialist': 3, 'senior': 2, 'junior': 1,
}

class CanManageUsers(BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['admin', 'chief', 'lead']
    
    def has_object_permission(self, request, view, obj):
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
        user = request.user
        result = []

        if user.role == 'specialist':
            juniors = User.objects.filter(supervisor=user)
            result = list(juniors)
        elif user.role == 'lead':
            specialists = User.objects.filter(supervisor=user)
            result = list(specialists)
            for s in specialists:
                juniors = User.objects.filter(supervisor=s)
                result.extend(juniors)
        elif user.role in ['chief', 'admin']:
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
            return [IsAuthenticated(), CanEditColumn()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = Column.objects.all()
        board_id = self.request.query_params.get('board', None)
        if board_id:
            if self.request.user.role not in ['admin', 'chief', 'lead']:
                accessible = Board.objects.filter(id=board_id, is_archived=False).filter(
                    Q(privacy='public', allow_anyone_view=True) |
                    Q(memberships__user=self.request.user)
                ).exists()
                if not accessible:
                    return Column.objects.none()
            qs = qs.filter(board_id=board_id)
        return qs

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, CanCreateColumn])
    def reorder(self, request):
        orders = request.data.get('orders', [])
        for item in orders:
            Column.objects.filter(id=item['id']).update(order=item['order'])
        return Response({'status': 'ok'})


# ═══════════════════════════════
#           ДОСКИ И ЧАТ
# ═══════════════════════════════

class BoardViewSet(viewsets.ModelViewSet):
    queryset = Board.objects.filter(is_archived=False)
    serializer_class = BoardSerializer

    def get_permissions(self):
        if self.action in ['create', 'destroy', 'update', 'partial_update']:
            return [IsAuthenticated()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['admin', 'chief', 'lead']:
            return Board.objects.filter(is_archived=False)
        boards = Board.objects.filter(is_archived=False).filter(
            Q(privacy='public', allow_anyone_view=True) |
            Q(memberships__user=user) |
            Q(creator=user)
        ).distinct()
        return boards

    def perform_create(self, serializer):
        board = serializer.save(creator=self.request.user)
        BoardMembership.objects.create(board=board, user=self.request.user, role='admin')

    def destroy(self, request, *args, **kwargs):
        board = self.get_object()
        if request.user != board.creator and request.user.role != 'admin':
            return Response({'error': 'Недостаточно прав'}, status=403)
        return super().destroy(request, *args, **kwargs)


    @action(detail=True, methods=['patch'], url_path='update_membership')
    def update_membership(self, request, pk=None):
        board = self.get_object()
        user_id = request.data.get('user_id')
        role = request.data.get('role')
        view_all_tasks = request.data.get('view_all_tasks')
        edit_columns = request.data.get('edit_columns')
        reorder_columns = request.data.get('reorder_columns')
        if not user_id:
            return Response({'error': 'Не указан user_id'}, status=400)
        if role and role not in ['admin', 'editor', 'viewer']:
            return Response({'error': 'Недопустимая роль'}, status=400)
        # Проверка прав: только создатель доски или админ может менять роли и права
        if request.user != board.creator and request.user.role != 'admin':
            return Response({'error': 'Недостаточно прав'}, status=403)
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'Пользователь не найден'}, status=404)
        membership, created = BoardMembership.objects.get_or_create(board=board, user=user)
        if role is not None:
            membership.role = role
        if view_all_tasks is not None:
            membership.view_all_tasks = view_all_tasks
        if edit_columns is not None:
            membership.edit_columns = edit_columns
        if reorder_columns is not None:
            membership.reorder_columns = reorder_columns
        membership.save()
        return Response({'status': 'ok', 'role': membership.role, 'view_all_tasks': membership.view_all_tasks, 'edit_columns': membership.edit_columns, 'reorder_columns': membership.reorder_columns})


    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        board = self.get_object()
        user_id = request.data.get('user_id')
        role = request.data.get('role', 'viewer')
        if not user_id:
            return Response({'error': 'user_id required'}, status=400)
        if request.user != board.creator and request.user.role != 'admin':
            return Response({'error': 'Недостаточно прав'}, status=403)
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'Пользователь не найден'}, status=404)
        membership, _ = BoardMembership.objects.get_or_create(board=board, user=user)
        membership.role = role
        membership.save()
        return Response({'status': 'ok'})

    @action(detail=True, methods=['post'])
    def remove_member(self, request, pk=None):
        board = self.get_object()
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'user_id required'}, status=400)
        if request.user != board.creator and request.user.role != 'admin':
            return Response({'error': 'Недостаточно прав'}, status=403)
        BoardMembership.objects.filter(board=board, user_id=user_id).delete()
        return Response({'status': 'ok'})


class BoardChatViewSet(viewsets.ModelViewSet):
    queryset = BoardChatMessage.objects.all()
    serializer_class = BoardChatMessageSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get_queryset(self):
        board_id = self.request.query_params.get('board', None)
        if board_id:
            if self.request.user.role not in ['admin', 'chief', 'lead']:
                accessible = Board.objects.filter(id=board_id, is_archived=False).filter(
                    Q(privacy='public', allow_anyone_view=True) |
                    Q(memberships__user=self.request.user) |
                    Q(creator=self.request.user)
                ).exists()
                if not accessible:
                    return BoardChatMessage.objects.none()
            return BoardChatMessage.objects.filter(board_id=board_id).select_related(
                'author', 'reply_to', 'reply_to__author'
            )
        return BoardChatMessage.objects.none()

    def perform_create(self, serializer):
        board = serializer.validated_data.get('board')
        if not board:
            raise serializers.ValidationError({'board': 'Не указана доска'})
        if self.request.user.role not in ['admin', 'chief', 'lead']:
            allowed = Board.objects.filter(id=board.id, is_archived=False).filter(
                Q(privacy='public', allow_anyone_view=True) |
                Q(memberships__user=self.request.user) |
                Q(creator=self.request.user)
            ).exists()
            if not allowed:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied('У вас нет прав на отправку сообщений в этой доске')
        serializer.save(author=self.request.user)


# ═══════════════════════════════
#            ЗАДАЧИ
# ═══════════════════════════════

class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer

    def get_queryset(self):
        user = self.request.user
        show_archived = self.request.query_params.get('archived', 'false') == 'true'
        board_id = self.request.query_params.get('board', None)

        # Проверяем, имеет ли пользователь право видеть все задачи на доске
        can_view_all = False
        if board_id:
            try:
                membership = BoardMembership.objects.get(board_id=board_id, user=user)
                can_view_all = membership.view_all_tasks
            except BoardMembership.DoesNotExist:
                pass

        if user.role in ['admin', 'chief', 'lead'] or can_view_all:
            qs = Task.objects.all().select_related('created_by', 'column')
        elif user.role == 'specialist':
            junior_ids = user.juniors.values_list('id', flat=True)
            qs = Task.objects.filter(created_by__in=[user.id, *junior_ids]).select_related('created_by', 'column')
        else:
            qs = Task.objects.filter(created_by=user).select_related('created_by', 'column')

        if board_id:
            if user.role not in ['admin', 'chief', 'lead']:
                accessible = Board.objects.filter(id=board_id, is_archived=False).filter(
                    Q(privacy='public', allow_anyone_view=True) |
                    Q(memberships__user=user)
                ).exists()
                if not accessible:
                    return Task.objects.none()
            qs = qs.filter(column__board_id=board_id)

        if not show_archived:
            qs = qs.filter(is_archived=False)

        return qs

    def perform_create(self, serializer):
        task = serializer.save(created_by=self.request.user, is_archived=False)
        board = task.column.board  # получаем доску для уведомлений
        for user in task.assigned_to.all():
            if user != self.request.user:
                Notification.objects.create(
                    recipient=user,
                    sender=self.request.user,
                    task=task,
                    board=board,
                    type='assigned',
                    text=f'{self.request.user.get_full_name_display()} назначил вас исполнителем задачи "{task.title}"'
                )

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
        board_id = request.query_params.get('board', None)

        # Базовый queryset с учётом прав и доски
        if user.role in ['admin', 'chief', 'lead']:
            qs = Task.objects.all()
        elif user.role == 'specialist':
            junior_ids = user.juniors.values_list('id', flat=True)
            qs = Task.objects.filter(created_by__in=[user.id, *junior_ids])
        else:
            qs = Task.objects.filter(created_by=user)

        if board_id:
            qs = qs.filter(column__board_id=board_id)

        tasks = qs

        by_column = tasks.filter(is_archived=False).values('column__name', 'column__id').annotate(count=Count('id'))
        by_priority = tasks.filter(is_archived=False).values('priority').annotate(count=Count('id'))

        by_user = []
        if user.role in ['admin', 'chief', 'lead']:
            by_user = list(tasks.filter(is_archived=False).values(
                'created_by__id', 'created_by__first_name', 'created_by__last_name', 'created_by__username'
            ).annotate(count=Count('id')).order_by('-count')[:10])

        today = timezone.now().date()
        activity = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            count = tasks.filter(created_at__date=day).count()
            activity.append({'date': str(day), 'count': count})

        overdue = tasks.filter(is_archived=False, deadline__lt=timezone.now().date()).count()

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


# ═══════════════════════════════
#         КОММЕНТАРИИ
# ═══════════════════════════════

class TaskCommentViewSet(viewsets.ModelViewSet):
    serializer_class = TaskCommentSerializer

    def get_queryset(self):
        task_id = self.request.query_params.get('task', None)
        if task_id:
            # Подгружаем автора и родительские комментарии для вложенности
            return TaskComment.objects.filter(task_id=task_id).select_related('author', 'parent').prefetch_related('replies')
        return TaskComment.objects.none()

    def perform_create(self, serializer):
        comment = serializer.save(author=self.request.user)
        board = comment.task.column.board
        for user in comment.mentioned_users.all():
            if user != self.request.user:
                Notification.objects.create(
                    recipient=user,
                    sender=self.request.user,
                    task=comment.task,
                    board=board,
                    type='mentioned',
                    text=f'{self.request.user.get_full_name_display()} упомянул вас в комментарии к задаче "{comment.task.title}"'
                )


# ═══════════════════════════════
#         УВЕДОМЛЕНИЯ
# ═══════════════════════════════

class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user).select_related('sender', 'task', 'board')
        board_id = self.request.query_params.get('board', None)
        if board_id:
            qs = qs.filter(board_id=board_id)
        return qs

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return Response({'count': count})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({'status': 'ok'})

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notif = self.get_object()
        notif.is_read = True
        notif.save()
        return Response({'status': 'ok'})