"""Web addresses for the front desk screens."""

from django.urls import path

from .views import dashboard, members, payments

urlpatterns = [
    path("", dashboard.dashboard, name="dashboard"),
    # Members
    path("members/", members.member_list, name="member_list"),
    path("members/add/", members.member_add, name="member_add"),
    path("members/<int:pk>/", members.member_detail, name="member_detail"),
    path("members/<int:pk>/edit/", members.member_edit, name="member_edit"),
    path("members/<int:pk>/renew/", members.member_renew, name="member_renew"),
    # Payments
    path("members/<int:pk>/pay/", payments.payment_add, name="payment_add"),
    path("payments/", payments.payment_list, name="payment_list"),
    path("payments/walk-in/", payments.walk_in, name="walk_in"),
]
