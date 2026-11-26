"""Web addresses for the front desk screens."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
]
