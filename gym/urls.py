"""Web addresses for the front desk screens."""

from django.urls import path

from .views import dashboard, members, payments

urlpatterns = [
    path("", dashboard.dashboard, name="dashboard"),
    path("members/", members.member_list, name="member_list"),
    path("payments/", payments.payment_list, name="payment_list"),
]
