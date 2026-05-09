from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import UserViewSet, ColumnViewSet, TaskViewSet, BoardViewSet, BoardChatViewSet, BoardSettingsViewSet, create_test_users, migrate_db, create_admin

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'columns', ColumnViewSet)
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'boards', BoardViewSet, basename='board')
router.register(r'board-chat', BoardChatViewSet, basename='board-chat')
router.register(r'board-settings', BoardSettingsViewSet, basename='board-settings')
from .views import NotificationViewSet, TaskCommentViewSet
router.register(r'comments', TaskCommentViewSet, basename='comment')
router.register(r'notifications', NotificationViewSet, basename='notification')
urlpatterns = [
    path('api/', include(router.urls)),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('create-test-users/', create_test_users),
    path('migrate/', migrate_db),
    path('create-admin/', create_admin),
    
]
