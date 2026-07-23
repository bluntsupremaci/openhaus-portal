"""
Main URL configuration for OpenHaus project.
"""

from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Authentication & User Management
    path('accounts/', include('accounts.urls')),

    # Portal & Dashboard
    path('', include('portal.urls')),

    # API / FAS Endpoint
    path('api/', include('api.urls')),

    # Health check
    path('health/', lambda r: HttpResponse('OK'), name='health'),

    # Admin Logout Fix
    path('admin/logout/', auth_views.LogoutView.as_view(next_page='/admin/'), name='admin_logout'),
]