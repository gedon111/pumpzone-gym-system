"""The dashboard shows the right counts, filters and money."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from gym.models import Member, Membership, Payment, Plan


class DashboardTests(TestCase):
    def setUp(self):
        today = timezone.localdate()
        plan = Plan.objects.create(name="Day", length=1, unit="day", price=Decimal("100"))
        staff = User.objects.create_user("lea", password="not-a-real-pass-1")
        self.client.force_login(staff)

        def member(name, ends_in_days, paid=True):
            m = Member.objects.create(full_name=name)
            ms = Membership.objects.create(member=m, plan=plan, start_date=today - timedelta(days=10),
                                           end_date=today + timedelta(days=ends_in_days))
            if paid:
                Payment.objects.create(membership=ms, amount=Decimal("100"), method=Payment.GCASH, reference_no="1")
            return m

        member("Active Annie", 20)
        member("Expiring Ernie", 3)
        member("Expired Edna", -5)
        member("Owing Oscar", 20, paid=False)
        Payment.objects.create(walk_in_name="Walky", amount=Decimal("150"))

    def test_counts_and_action_list(self):
        r = self.client.get("/")
        self.assertEqual(r.context["by_status"]["active"], 2)
        self.assertEqual([t["count"] for t in r.context["tabs"]], [3, 1, 1, 1])  # all, expiring, expired, unpaid
        self.assertContains(r, "1 membership runs out this week.")
        names = [s.member.full_name for s in r.context["rows"]]
        self.assertNotIn("Active Annie", names)  # nothing to do for her

    def test_filter_tab(self):
        rows = self.client.get("/?show=unpaid").context["rows"]
        self.assertEqual([s.member.full_name for s in rows], ["Owing Oscar"])

    def test_collected_today(self):
        collected = self.client.get("/").context["collected"]
        self.assertEqual(collected["total"], Decimal("450"))  # 3 x 100 GCash + 150 cash walk-in
        self.assertEqual({m["key"]: m["amount"] for m in collected["methods"]},
                         {"cash": Decimal("150"), "gcash": Decimal("300")})

    def test_calendar_marks_end_day(self):
        calendar = self.client.get("/").context["calendar"]
        self.assertEqual(len(calendar), 28)
        self.assertEqual(calendar[3]["count"], 1)  # Expiring Ernie
        self.assertTrue(calendar[0]["is_today"])
