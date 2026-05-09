from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

handler404 = 'board.views.custom_404'

urlpatterns = [
    # ⬇️ ЭТО ДОЛЖНО БЫТЬ ПЕРВЫМ ⬇️
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    
    path('admin/', admin.site.urls),
    
    # API бэкенда
    path('', include('board.urls')),
    
    # Фронтенд страницы
    path('main/', TemplateView.as_view(template_name='index.html'), name='main'),
    path('structure/', TemplateView.as_view(template_name='orgchart.html'), name='structure'),
    path('boards/', TemplateView.as_view(template_name='boards.html'), name='boards'),
    path('tests/', TemplateView.as_view(template_name='tests.html'), name='tests'),
]
