"""Check-in: card tap (USB reader types the number + Enter), code, phone, nickname."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from gym import checkin, status
from gym.models import CheckIn, Member, Membership, Payment, Plan
from gym.summary import summarize


class CheckInTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.monthly = Plan.objects.create(name="Monthly", price=Decimal("900"))
        self.lea = User.objects.create_user("lea", first_name="Lea", password="not-a-real-pass-1")
        self.client.force_login(self.lea)

    def member(self, name="Marco Dela Cruz", ends_in_days=20, paid=True, **fields):
        m = Member.objects.create(full_name=name, **fields)
        ms = Membership.objects.create(member=m, plan=self.monthly, start_date=self.today - timedelta(days=10),
                                       end_date=self.today + timedelta(days=ends_in_days))
        if paid:
            Payment.objects.create(membership=ms, amount=ms.price_agreed)
        return m

    def tap(self, code):
        return self.client.post("/checkin/", {"code": code}, follow=True)

    def test_card_tap_checks_in_and_shows_green(self):
        m = self.member(card_uid="04 a1:b2 c3")  # saved tidied as 04A1B2C3
        r = self.tap("04A1B2C3")
        visit = CheckIn.objects.get()
        self.assertEqual((visit.member, visit.how, visit.by, visit.status_then), (m, CheckIn.CARD, self.lea, status.ACTIVE))
        self.assertEqual(r.context["result"]["tone"], checkin.GO)
        self.assertContains(r, "Active")

    def test_member_code_and_phone_without_spaces(self):
        m = self.member(phone="0900 000 1234")
        self.tap(m.member_code.lower())
        self.tap("09000001234")
        self.assertEqual(CheckIn.objects.filter(member=m, how=CheckIn.TYPED).count(), 2)

    def test_expired_member_is_still_logged_and_shown_red(self):
        m = self.member(ends_in_days=-3)
        r = self.tap(m.member_code)
        self.assertEqual(CheckIn.objects.get().status_then, status.EXPIRED)
        self.assertEqual(r.context["result"]["tone"], checkin.OUT)
        self.assertContains(r, "Renew")

    def test_late_payer_is_red_and_expiring_is_amber(self):
        late = self.member("Late Payer", paid=False)  # started 10 days ago, nothing paid, grace is 3
        soon = self.member("Soon Ending", ends_in_days=2)
        self.assertEqual(checkin.verdict(summarize(late, self.today))[0], checkin.OUT)
        self.assertEqual(checkin.verdict(summarize(soon, self.today))[0], checkin.SOON)

    def test_unknown_card_logs_nothing(self):
        self.member()
        r = self.tap("FFFF0000")
        self.assertTrue(r.context["not_found"])
        self.assertFalse(CheckIn.objects.exists())

    def test_two_name_matches_ask_staff_to_pick(self):
        self.member("Ana Lim")
        b = self.member("Ana Reyes")
        r = self.tap("Ana")
        self.assertEqual(len(r.context["choices"]), 2)
        self.assertFalse(CheckIn.objects.exists())
        self.client.post("/checkin/", {"member": b.pk})
        self.assertEqual(CheckIn.objects.get().member, b)

    def test_refresh_after_check_in_does_not_log_twice(self):
        m = self.member()
        r = self.tap(m.member_code)
        self.client.get(r.redirect_chain[-1][0])  # reload the result page
        self.assertEqual(CheckIn.objects.count(), 1)

    def test_card_number_must_be_unique_on_edit(self):
        self.member("Ana Lim", card_uid="04A1B2C3")
        other = self.member("Ben Tan")
        r = self.client.post(f"/members/{other.pk}/edit/", {"full_name": "Ben Tan", "card_uid": "04 a1 b2 c3"})
        self.assertContains(r, "already linked to Ana Lim")
        r = self.client.post(f"/members/{other.pk}/edit/", {"full_name": "Ben Tan", "card_uid": "99887766"})
        other.refresh_from_db()
        self.assertEqual(other.card_uid, "99887766")

    def test_members_without_cards_do_not_clash(self):
        self.member("Ana Lim", card_uid="")
        self.member("Ben Tan", card_uid=None)
        self.assertEqual(Member.objects.filter(card_uid=None).count(), 2)

    def test_dashboard_and_member_page_show_visits(self):
        m = self.member()
        self.tap(m.member_code)
        self.assertEqual(self.client.get("/").context["checkins_today"], 1)
        self.assertEqual(len(self.client.get(f"/members/{m.pk}/").context["check_ins"]), 1)

    def test_student_plan_reminds_staff_to_check_id_or_uniform(self):
        student = Plan.objects.create(name="Student Monthly", price=Decimal("650"))
        m = Member.objects.create(full_name="Bea Santos")
        ms = Membership.objects.create(member=m, plan=student, start_date=self.today,
                                       end_date=self.today + timedelta(days=20))
        Payment.objects.create(membership=ms, amount=ms.price_agreed)
        tone, _, detail = checkin.verdict(summarize(m, self.today))
        self.assertEqual(tone, checkin.GO)
        self.assertIn("student ID or school uniform", detail)
        self.assertNotIn("student ID", checkin.verdict(summarize(self.member(), self.today))[2])
