"""
URL configuration for task_manager project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include

from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API бэкенда (все маршруты из board.urls)
    path('', include('board.urls')),  # ваши /api/tasks, /api/columns и т.д.
    
    # Фронтенд страницы
    path('main/', TemplateView.as_view(template_name='index.html'), name='main'),
    path('structure/', TemplateView.as_view(template_name='orgchart.html'), name='structure'),
    
    # Перенаправление корня на /main
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    
    # Для обратной совместимости (если кто-то переходит по старым ссылкам)
    path('index.html', TemplateView.as_view(template_name='index.html')),
    path('orgchart.html', TemplateView.as_view(template_name='orgchart.html')),
]