"""SMS reminder text and links."""

from datetime import timedelta
from decimal import Decimal
from urllib.parse import unquote

from django.test import TestCase
from django.utils import timezone

from gym.models import Member, Membership, Payment, Plan
from gym.sms import reminder_text, sms_href
from gym.summary import summarize


class SmsTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.plan = Plan.objects.create(name="Monthly", price=Decimal("1000"))

    def summary_for(self, ends_in_days, paid=True, nickname="Marky"):
        member = Member.objects.create(full_name="Marco Dela Cruz", nickname=nickname, phone="0900 000 1234")
        ms = Membership.objects.create(member=member, plan=self.plan, start_date=self.today - timedelta(days=20),
                                       end_date=self.today + timedelta(days=ends_in_days))
        if paid:
            Payment.objects.create(membership=ms, amount=Decimal("1000"))
        return summarize(member, self.today)

    def test_expiring_message_uses_nickname_and_end_date(self):
        text = reminder_text(self.summary_for(3))
        self.assertTrue(text.startswith("Hi Marky! Pumpzone Gym here."))
        self.assertIn("ends on", text)

    def test_last_day_says_today(self):
        self.assertIn("ends today", reminder_text(self.summary_for(0)))

    def test_owing_message_wins_and_avoids_peso_sign(self):
        text = reminder_text(self.summary_for(20, paid=False, nickname=""))
        self.assertTrue(text.startswith("Hi Marco!"))
        self.assertIn("PHP 1,000", text)
        self.assertNotIn("₱", text)  # keeps it a single 160-character SMS
        self.assertTrue(text.isascii())

    def test_expired_message(self):
        self.assertIn("We miss you", reminder_text(self.summary_for(-4)))

    def test_link_strips_spaces_and_encodes_body(self):
        href = sms_href("0900 000 1234", "Hi there! Salamat")
        self.assertTrue(href.startswith("sms:09000001234?&body="))
        self.assertEqual(unquote(href.split("body=")[1]), "Hi there! Salamat")

    def test_no_link_without_phone(self):
        self.assertEqual(sms_href("", "Hi"), "")

    def test_button_on_dashboard(self):
        from django.contrib.auth.models import User
        self.summary_for(2)
        self.client.force_login(User.objects.create_user("lea", password="not-a-real-pass-1"))
        self.assertContains(self.client.get("/?show=expiring"), 'href="sms:09000001234?&amp;body=')
