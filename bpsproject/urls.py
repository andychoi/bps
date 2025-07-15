# project/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Admin site
    path('admin/', admin.site.urls),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # Business Planning System (bps) app
    path('bps/', include('bps.urls', namespace='bps')),
    path('',    include('common.urls', namespace='common')),
    path('accounts/', include('django.contrib.auth.urls')),

    # You can mount other apps here...
]

# Serve media/static files in DEBUG mode
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)