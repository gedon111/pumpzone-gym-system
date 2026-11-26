"""The back office opens, and payment protections hold."""

from decimal import Decimal

from django.contrib.admin.sites import site
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from gym.models import Payment


class AdminTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser("owner", password="not-a-real-pass-1")
        self.staff = User.objects.create_user("lea", password="not-a-real-pass-1", is_staff=True)
        self.payment_admin = site._registry[Payment]

    def request_as(self, user):
        request = RequestFactory().get("/")
        request.user = user
        return request

    def test_every_admin_page_opens_for_owner(self):
        self.client.force_login(self.owner)
        for page in ["plan", "member", "membership", "payment"]:
            for action in ["", "add/"]:
                url = f"/admin/gym/{page}/{action}"
                self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_nobody_can_delete_payments(self):
        self.assertFalse(self.payment_admin.has_delete_permission(self.request_as(self.owner)))

    def test_only_owner_can_void(self):
        payment = Payment.objects.create(walk_in_name="Juan", amount=Decimal("150"))
        staff_locked = self.payment_admin.get_readonly_fields(self.request_as(self.staff), payment)
        owner_locked = self.payment_admin.get_readonly_fields(self.request_as(self.owner), payment)
        self.assertIn("is_voided", staff_locked)
        self.assertNotIn("is_voided", owner_locked)
        self.assertIn("amount", owner_locked)  # even the owner cannot edit the amount
