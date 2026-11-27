"""Web addresses for the front desk screens."""

from django.urls import path

from .views import checkin, dashboard, members, payments, signups

urlpatterns = [
    path("", dashboard.dashboard, name="dashboard"),
    path("checkin/", checkin.check_in, name="check_in"),
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
    # Sign-up mode: the member types on the desk phone (gym/kiosk.py)
    path("join/start/", signups.kiosk_start, name="kiosk_start"),
    path("join/", signups.join, name="join"),
    path("join/done/", signups.join_done, name="join_done"),
    path("join/unlock/", signups.join_unlock, name="join_unlock"),
    # Staff check the sign-ups
    path("signups/", signups.signup_list, name="signup_list"),
    path("signups/<int:pk>/", signups.signup_review, name="signup_review"),
    path("signups/<int:pk>/carry-over/", signups.signup_carry_over, name="signup_carry_over"),
    path("signups/<int:pk>/link/<int:member_pk>/", signups.signup_link, name="signup_link"),
    path("signups/<int:pk>/dismiss/", signups.signup_dismiss, name="signup_dismiss"),
]
