"""Top-level URL map. Each line connects a web address to the code that answers it."""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    # Owner back office (plans, staff accounts, voids).
    path("admin/", admin.site.urls),
    # Staff sign in / sign out. Django's built-in views do the work.
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    # Everything else belongs to the gym app.
    path("", include("gym.urls")),
]
