from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    # add your dashboard, profile, etc. routes here
]
