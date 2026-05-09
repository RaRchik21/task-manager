from rest_framework import status
from rest_framework.test import APITestCase

from .models import Board, BoardMembership, BoardSettings, Column, Task, User


class BoardApiTests(APITestCase):
    def setUp(self):
        self.password = 'Pass12345!'
        self.user = User.objects.create_user(username='user', password=self.password, role='junior')
        self.other_user = User.objects.create_user(username='other', password=self.password, role='senior')
        self.third_user = User.objects.create_user(username='third', password=self.password, role='specialist')

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_regular_user_sees_only_self_in_users_list(self):
        self.authenticate(self.user)

        response = self.client.get('/api/users/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.user.id)

    def test_all_for_board_returns_all_non_admin_users_for_regular_user(self):
        self.authenticate(self.user)

        response = self.client.get('/api/users/all_for_board/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {item['id'] for item in response.data}
        self.assertEqual(returned_ids, {self.user.id, self.other_user.id, self.third_user.id})

    def test_board_settings_current_is_available_without_auth(self):
        BoardSettings.objects.create(system_name='Custom Tracker')

        response = self.client.get('/api/board-settings/current/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['system_name'], 'Custom Tracker')

    def test_board_creator_can_edit_column(self):
        board = Board.objects.create(name='Board', creator=self.user)
        column = Column.objects.create(name='Todo', board=board, order=0)
        self.authenticate(self.user)

        response = self.client.patch(
            f'/api/columns/{column.id}/',
            {'name': 'Updated'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        column.refresh_from_db()
        self.assertEqual(column.name, 'Updated')

    def test_assigned_user_sees_task_in_board_queryset(self):
        board = Board.objects.create(name='Board', creator=self.other_user)
        BoardMembership.objects.create(board=board, user=self.user, role='viewer')
        column = Column.objects.create(name='Todo', board=board, order=0)
        task = Task.objects.create(title='Assigned', column=column, created_by=self.other_user)
        task.assigned_to.add(self.user)
        self.authenticate(self.user)

        response = self.client.get(f'/api/tasks/?board={board.id}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], task.id)

    def test_new_lead_member_gets_default_board_permissions(self):
        board = Board.objects.create(name='Board', creator=self.user)
        self.other_user.role = 'lead'
        self.other_user.save(update_fields=['role'])
        self.authenticate(self.user)

        response = self.client.post(
            f'/api/boards/{board.id}/add_member/',
            {'user_id': self.other_user.id, 'role': 'viewer'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        membership = BoardMembership.objects.get(board=board, user=self.other_user)
        self.assertTrue(membership.view_all_tasks)
        self.assertTrue(membership.edit_columns)
        self.assertTrue(membership.reorder_columns)
