"""The desk screens: add, renew, collect, walk-in, search, and every page opening."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from gym.models import Member, Membership, Payment, Plan


class ScreenTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.monthly = Plan.objects.create(name="Monthly", price=Decimal("1000"))
        self.day_pass = Plan.objects.create(name="Day Pass", length=1, unit="day", price=Decimal("150"))
        self.lea = User.objects.create_user("lea", first_name="Lea", password="not-a-real-pass-1")
        self.client.force_login(self.lea)

    def make_member(self, ends_in_days=10, phone="0900 000 1111"):
        member = Member.objects.create(full_name="Marco Dela Cruz", nickname="Marky", phone=phone)
        Membership.objects.create(member=member, plan=self.monthly,
                                  start_date=self.today - timedelta(days=20),
                                  end_date=self.today + timedelta(days=ends_in_days))
        return member

    # ---- Add member ---------------------------------------------------------
    def add(self, **extra):
        data = {"full_name": "Jessa Villanueva", "phone": "0900 000 2222", "plan": self.monthly.pk,
                "start_date": self.today.isoformat(), "pay": "full", "method": "cash", "consent": "on"}
        data.update(extra)
        return self.client.post("/members/add/", data)

    def test_add_member_paid_in_full(self):
        r = self.add()
        member = Member.objects.get(full_name="Jessa Villanueva")
        self.assertRedirects(r, f"/members/{member.pk}/")
        self.assertEqual(member.balance, Decimal("0"))
        payment = Payment.objects.get()
        self.assertEqual(payment.received_by, self.lea)
        self.assertEqual(member.memberships.get().created_by, self.lea)

    def test_add_member_part_payment_with_discount(self):
        self.add(price_agreed="800", pay="partial", amount="300")
        member = Member.objects.get()
        self.assertEqual(member.memberships.get().discount, Decimal("200"))
        self.assertEqual(member.balance, Decimal("500"))

    def test_add_member_needs_consent_and_gcash_ref(self):
        self.add(consent="", method="gcash")
        self.assertFalse(Member.objects.exists())

    def test_add_member_rejects_duplicate_phone(self):
        self.make_member(phone="0900 000 2222")
        r = self.add()
        self.assertContains(r, "Already on file")
        self.assertEqual(Member.objects.count(), 1)

    # ---- Renew --------------------------------------------------------------
    def test_renew_defaults_to_day_after_current_end(self):
        member = self.make_member(ends_in_days=3)
        form = self.client.get(f"/members/{member.pk}/renew/").context["form"]
        self.assertEqual(form.initial["start_date"], self.today + timedelta(days=4))
        self.assertEqual(form.initial["plan"], self.monthly)

    def test_renew_creates_new_period(self):
        member = self.make_member(ends_in_days=3)
        start = self.today + timedelta(days=4)
        self.client.post(f"/members/{member.pk}/renew/", {
            "plan": self.monthly.pk, "start_date": start.isoformat(), "pay": "full",
            "method": "gcash", "reference_no": "1234 567 890"})
        self.assertEqual(member.memberships.count(), 2)
        self.assertEqual(member.latest_membership.start_date, start)

    # ---- Collect payment ----------------------------------------------------
    def test_collect_defaults_to_full_balance(self):
        member = self.make_member()
        form = self.client.get(f"/members/{member.pk}/pay/").context["form"]
        self.assertEqual(form.initial["amount"], Decimal("1000"))
        self.client.post(f"/members/{member.pk}/pay/", {
            "membership": member.memberships.get().pk, "amount": "1000", "method": "cash"})
        self.assertEqual(member.balance, Decimal("0"))

    # ---- Walk-in ------------------------------------------------------------
    def test_walk_in_day_pass(self):
        self.assertEqual(self.client.get("/payments/walk-in/").context["form"].initial["amount"], Decimal("150"))
        self.client.post("/payments/walk-in/", {"walk_in_name": "Bong", "amount": "150", "method": "cash"})
        payment = Payment.objects.get()
        self.assertTrue(payment.is_walk_in)
        self.assertContains(self.client.get("/payments/"), "Bong")

    # ---- Search and pages ---------------------------------------------------
    def test_search_by_nickname_code_and_phone_without_spaces(self):
        member = self.make_member()
        for q in ["marky", member.member_code, "09000001111"]:
            rows = self.client.get("/members/", {"q": q}).context["rows"]
            self.assertEqual([s.member for s in rows], [member], q)

    def test_every_page_opens(self):
        member = self.make_member()
        for url in ["/", "/members/", "/members/add/", f"/members/{member.pk}/", f"/members/{member.pk}/edit/",
                    f"/members/{member.pk}/renew/", f"/members/{member.pk}/pay/", "/payments/",
                    "/payments/walk-in/", "/members/?status=owing", "/payments/?day=2026-01-01"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
