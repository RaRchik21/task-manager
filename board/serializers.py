from rest_framework import serializers
from .models import User, Column, Task, BoardSettings, Board, BoardMembership, BoardChatMessage, TaskComment, Notification


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
        fields = ['id', 'username', 'password', 'first_name', 'last_name',
                  'role', 'telegram_username', 'supervisor']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserShortSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'role']

    def get_full_name(self, obj):
        return obj.get_full_name_display()


class ColumnSerializer(serializers.ModelSerializer):
    class Meta:
        model = Column
        fields = ['id', 'name', 'order', 'color', 'is_collapsed', 'board']


class BoardMembershipSerializer(serializers.ModelSerializer):
    user = UserShortSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = BoardMembership
        fields = ['id', 'board', 'user', 'user_id', 'role', 'joined_at', 'view_all_tasks', 'edit_columns', 'reorder_columns']
        read_only_fields = ['id', 'joined_at', 'user']

    def create(self, validated_data):
        user_id = validated_data.pop('user_id', None)
        if user_id:
            validated_data['user'] = User.objects.get(id=user_id)
        return super().create(validated_data)


class BoardChatMessageSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.get_full_name_display', read_only=True)
    reply_to_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    reply_to = serializers.PrimaryKeyRelatedField(read_only=True)
    reply_to_text = serializers.CharField(source='reply_to.text', read_only=True)
    reply_to_author_name = serializers.CharField(source='reply_to.author.get_full_name_display', read_only=True)

    class Meta:
        model = BoardChatMessage
        fields = ['id', 'board', 'author', 'author_name', 'reply_to', 'reply_to_id', 'reply_to_text', 'reply_to_author_name', 'text', 'created_at']
        read_only_fields = ['id', 'author', 'created_at', 'reply_to']

    def create(self, validated_data):
        reply_to_id = validated_data.pop('reply_to_id', None)
        if reply_to_id:
            try:
                validated_data['reply_to'] = BoardChatMessage.objects.get(id=reply_to_id)
            except BoardChatMessage.DoesNotExist:
                pass
        return super().create(validated_data)


class BoardSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source='creator.get_full_name_display', read_only=True)
    memberships = BoardMembershipSerializer(many=True, read_only=True)
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    viewer_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )

    class Meta:
        model = Board
        fields = ['id', 'name', 'description', 'creator', 'creator_name',
                  'created_at', 'privacy', 'allow_anyone_view', 'is_archived',
                  'memberships', 'participant_ids', 'viewer_ids']
        read_only_fields = ['id', 'creator', 'created_at', 'memberships']

    def _sync_memberships(self, board, participant_ids=None, viewer_ids=None):
        creator_id = board.creator_id

        if participant_ids is not None:
            participant_ids = [user_id for user_id in participant_ids if user_id != creator_id]
            board.memberships.filter(role='editor').exclude(user_id__in=participant_ids).delete()
            for user in User.objects.filter(id__in=participant_ids).exclude(id=creator_id):
                membership, created = BoardMembership.objects.update_or_create(
                    board=board,
                    user=user,
                    defaults={'role': 'editor'},
                )
                if created and user.role in ['admin', 'chief', 'lead']:
                    membership.view_all_tasks = True
                    membership.edit_columns = True
                    membership.reorder_columns = True
                    membership.save(update_fields=['view_all_tasks', 'edit_columns', 'reorder_columns'])

        if viewer_ids is not None:
            viewer_ids = [user_id for user_id in viewer_ids if user_id != creator_id]
            board.memberships.filter(role='viewer').exclude(user_id__in=viewer_ids).delete()
            for user in User.objects.filter(id__in=viewer_ids).exclude(id=creator_id):
                membership, created = BoardMembership.objects.update_or_create(
                    board=board,
                    user=user,
                    defaults={'role': 'viewer'},
                )
                if created and user.role in ['admin', 'chief', 'lead']:
                    membership.view_all_tasks = True
                    membership.edit_columns = True
                    membership.reorder_columns = True
                    membership.save(update_fields=['view_all_tasks', 'edit_columns', 'reorder_columns'])

    def create(self, validated_data):
        participant_ids = validated_data.pop('participant_ids', [])
        viewer_ids = validated_data.pop('viewer_ids', [])
        board = Board.objects.create(**validated_data)
        self._sync_memberships(board, participant_ids=participant_ids, viewer_ids=viewer_ids)
        return board

    def update(self, instance, validated_data):
        participant_ids = validated_data.pop('participant_ids', None)
        viewer_ids = validated_data.pop('viewer_ids', None)
        board = super().update(instance, validated_data)
        self._sync_memberships(board, participant_ids=participant_ids, viewer_ids=viewer_ids)
        return board


class TaskCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.get_full_name_display', read_only=True)
    mentioned_users = UserShortSerializer(many=True, read_only=True)
    mentioned_user_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)
    parent_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    replies = serializers.SerializerMethodField()
    parent = serializers.PrimaryKeyRelatedField(read_only=True)
    reply_to_text = serializers.CharField(source='parent.text', read_only=True)
    reply_to_author_name = serializers.CharField(source='parent.author.get_full_name_display', read_only=True)

    class Meta:
        model = TaskComment
        fields = ['id', 'task', 'author', 'author_name', 'text',
                  'mentioned_users', 'mentioned_user_ids', 'parent_id', 'parent', 'replies', 'reply_to_text', 'reply_to_author_name', 'created_at']
        read_only_fields = ['id', 'author', 'created_at', 'parent']

    def get_replies(self, obj):
        if hasattr(obj, 'replies'):
            return TaskCommentSerializer(obj.replies.all(), many=True, context=self.context).data
        return []

    def create(self, validated_data):
        mentioned_user_ids = validated_data.pop('mentioned_user_ids', [])
        parent_id = validated_data.pop('parent_id', None)
        if parent_id:
            try:
                validated_data['parent'] = TaskComment.objects.get(id=parent_id)
            except TaskComment.DoesNotExist:
                pass
        comment = super().create(validated_data)
        if mentioned_user_ids:
            comment.mentioned_users.set(User.objects.filter(id__in=mentioned_user_ids))
        return comment
        return comment


class TaskSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    assigned_to = UserShortSerializer(many=True, read_only=True)
    assigned_to_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    assigned_by_name = serializers.CharField(
        source='assigned_by.get_full_name_display', read_only=True
    )
    comments_count = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = ['id', 'title', 'comment', 'priority', 'deadline',
                  'is_archived', 'is_chief_goal', 'column',
                  'created_by', 'created_by_name',
                  'assigned_to', 'assigned_to_ids',
                  'assigned_by', 'assigned_by_name',
                  'comments_count', 'created_at']
        read_only_fields = ['id', 'created_by', 'created_at']

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name_display()

    def get_comments_count(self, obj):
        return obj.comments.count()

    def validate_assigned_to_ids(self, value):
        column = self.initial_data.get('column')
        if column is None and self.instance is not None:
            column = self.instance.column_id
        if not column:
            return value

        try:
            board_id = Column.objects.only('board_id').get(id=column).board_id
        except Column.DoesNotExist:
            raise serializers.ValidationError('Колонка не найдена')

        allowed_ids = set(
            BoardMembership.objects.filter(board_id=board_id, role='editor').values_list('user_id', flat=True)
        )
        invalid_ids = [user_id for user_id in value if user_id not in allowed_ids]
        if invalid_ids:
            raise serializers.ValidationError('Исполнителями могут быть только редакторы этой доски')
        return value

    def create(self, validated_data):
        assigned_ids = validated_data.pop('assigned_to_ids', [])
        task = Task.objects.create(**validated_data)
        if assigned_ids:
            task.assigned_to.set(User.objects.filter(id__in=assigned_ids))
        return task

    def update(self, instance, validated_data):
        assigned_ids = validated_data.pop('assigned_to_ids', None)
        task = super().update(instance, validated_data)
        if assigned_ids is not None:
            task.assigned_to.set(User.objects.filter(id__in=assigned_ids))
        return task


class NotificationSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(
        source='sender.get_full_name_display', read_only=True
    )
    task_title = serializers.CharField(source='task.title', read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'type', 'text', 'is_read', 'created_at', 'sender_name', 'task_title', 'task', 'board']


class BoardSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BoardSettings
        fields = ['system_name', 'bg_gradient', 'bg_color1', 'bg_color2', 'bg_angle',
                  'header_color', 'card_color', 'bg_opacity_header',
                  'bg_opacity_column', 'bg_opacity_card']
        


class TaskCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.get_full_name_display', read_only=True)
    mentioned_users = UserShortSerializer(many=True, read_only=True)
    mentioned_user_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)
    parent_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    replies = serializers.SerializerMethodField()
    parent = serializers.PrimaryKeyRelatedField(read_only=True)
    reply_to_text = serializers.CharField(source='parent.text', read_only=True)
    reply_to_author_name = serializers.CharField(source='parent.author.get_full_name_display', read_only=True)

    class Meta:
        model = TaskComment
        fields = ['id', 'task', 'author', 'author_name', 'text',
                  'mentioned_users', 'mentioned_user_ids', 'parent_id', 'parent', 'replies', 'reply_to_text', 'reply_to_author_name', 'created_at']
        read_only_fields = ['id', 'author', 'created_at', 'parent']

    def get_replies(self, obj):
        if hasattr(obj, 'replies'):
            return TaskCommentSerializer(obj.replies.all(), many=True, context=self.context).data
        return []

    def create(self, validated_data):
        mentioned_user_ids = validated_data.pop('mentioned_user_ids', [])
        parent_id = validated_data.pop('parent_id', None)
        comment = TaskComment.objects.create(**validated_data)
        if parent_id:
            comment.parent_id = parent_id
        if mentioned_user_ids:
            comment.mentioned_users.set(User.objects.filter(id__in=mentioned_user_ids))
        if parent_id or mentioned_user_ids:
            comment.save()
        return comment
