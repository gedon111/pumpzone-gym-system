"""Two floors, two desks: each staff member's takings are totalled on their own."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase

from gym.cashup import by_staff
from gym.models import Member, Membership, Payment, Plan


class CashUpTests(TestCase):
    def setUp(self):
        plan = Plan.objects.create(name="Monthly", price=Decimal("900"))
        member = Member.objects.create(full_name="Ana Lim", phone="0900 000 0001")
        self.ms = Membership.objects.create(member=member, plan=plan)
        self.lea = User.objects.create_user("lea", first_name="Lea", password="not-a-real-pass-1")
        self.rico = User.objects.create_user("rico", first_name="Rico", password="not-a-real-pass-1")

    def pay(self, user, amount, method=Payment.CASH, voided=False):
        return Payment.objects.create(
            membership=self.ms, amount=Decimal(amount), method=method, received_by=user,
            reference_no="1234" if method == Payment.GCASH else "", is_voided=voided,
            void_reason="mistake" if voided else "",
        )

    def test_totals_per_staff_member_skip_voided(self):
        self.pay(self.lea, "900")
        self.pay(self.lea, "450", Payment.GCASH)
        self.pay(self.rico, "100")
        self.pay(self.rico, "900", voided=True)
        rows = {r.name: r for r in by_staff(Payment.objects.select_related("received_by"))}
        self.assertEqual((rows["Lea"].cash, rows["Lea"].gcash, rows["Lea"].total, rows["Lea"].count),
                         (Decimal("900"), Decimal("450"), Decimal("1350"), 2))
        self.assertEqual((rows["Rico"].cash, rows["Rico"].count), (Decimal("100"), 1))

    def test_payments_page_and_dashboard_show_staff_rows(self):
        self.pay(self.lea, "900")
        self.pay(self.rico, "100")
        self.client.force_login(self.lea)
        page = self.client.get("/payments/")
        self.assertContains(page, "By staff")
        self.assertEqual([r.name for r in page.context["staff"]], ["Lea", "Rico"])
        self.assertEqual(len(self.client.get("/").context["collected"]["staff"]), 2)

    def test_database_is_set_up_for_two_desks(self):
        with connection.cursor() as c:
            c.execute("PRAGMA busy_timeout")
            self.assertGreaterEqual(c.fetchone()[0], 20000)
