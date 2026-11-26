"""Web addresses for the front desk screens."""

from django.urls import path

from .views import dashboard, members, payments

urlpatterns = [
    path("", dashboard.dashboard, name="dashboard"),
    path("members/", members.member_list, name="member_list"),
    path("members/<int:pk>/", members.member_detail, name="member_detail"),
    path("members/<int:pk>/renew/", members.member_renew, name="member_renew"),
    path("members/<int:pk>/pay/", payments.payment_add, name="payment_add"),
    path("payments/", payments.payment_list, name="payment_list"),
]
