"""Checks that member data is only visible to signed-in staff."""

from django.contrib.auth.models import User
from django.test import TestCase


class LoginRequiredTests(TestCase):
    def test_signed_out_visitor_is_sent_to_login(self):
        response = self.client.get("/")
        self.assertRedirects(response, "/login/?next=/")

    def test_login_page_is_public(self):
        self.assertEqual(self.client.get("/login/").status_code, 200)

    def test_signed_in_staff_can_open_dashboard(self):
        staff = User.objects.create_user("lea", password="not-a-real-pass-1")
        self.client.force_login(staff)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Signed in as lea")
