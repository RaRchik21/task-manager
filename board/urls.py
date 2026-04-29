from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import UserViewSet, ColumnViewSet, TaskViewSet, BoardSettingsViewSet, create_test_users, migrate_db, create_admin

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'columns', ColumnViewSet)
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'board-settings', BoardSettingsViewSet, basename='board-settings')

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('create-test-users/', create_test_users),
    path('migrate/', migrate_db),
    path('create-admin/', create_admin),
]