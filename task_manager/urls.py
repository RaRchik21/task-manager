from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

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
    
    # Для обратной совместимости
    path('index.html', TemplateView.as_view(template_name='index.html')),
    path('orgchart.html', TemplateView.as_view(template_name='orgchart.html')),
]