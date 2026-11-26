"""Tables working together: codes, end dates, balances, voids, payment checks."""

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from gym import status
from gym.models import Member, Membership, Payment, Plan


class ModelTests(TestCase):
    def setUp(self):
        self.monthly = Plan.objects.create(name="Monthly", price=Decimal("1000"))
        self.member = Member.objects.create(full_name="Test Person", joined_on=date(2026, 3, 1))

    def make_membership(self, **extra):
        return Membership.objects.create(member=self.member, plan=self.monthly, start_date=date(2026, 11, 25), **extra)

    def test_member_codes_count_up_per_year(self):
        second = Member.objects.create(full_name="Second", joined_on=date(2026, 5, 1))
        next_year = Member.objects.create(full_name="Next Year", joined_on=date(2027, 1, 2))
        self.assertEqual(self.member.member_code, "2026-0001")
        self.assertEqual(second.member_code, "2026-0002")
        self.assertEqual(next_year.member_code, "2027-0001")

    def test_membership_fills_end_date_and_prices_from_plan(self):
        m = self.make_membership()
        self.assertEqual(m.end_date, date(2026, 12, 25))
        self.assertEqual(m.list_price, Decimal("1000"))
        self.assertEqual(m.price_agreed, Decimal("1000"))

    def test_discount_is_kept_visible(self):
        m = self.make_membership(price_agreed=Decimal("800"))
        self.assertEqual(m.discount, Decimal("200"))

    def test_balance_ignores_voided_payments(self):
        m = self.make_membership()
        Payment.objects.create(membership=m, amount=Decimal("600"))
        Payment.objects.create(membership=m, amount=Decimal("400"), is_voided=True, void_reason="typo")
        self.assertEqual(m.balance, Decimal("400"))
        self.assertEqual(self.member.balance, Decimal("400"))

    def test_member_status_uses_latest_membership(self):
        old = self.make_membership()
        Membership.objects.create(member=self.member, plan=self.monthly, start_date=date(2026, 12, 26))
        self.assertEqual(self.member.latest_membership.end_date, date(2027, 1, 26))
        # 26 Dec: the old one ended yesterday, but the new one is active.
        self.assertEqual(self.member.expiry_status(on=date(2026, 12, 26)), status.ACTIVE)
        self.assertNotEqual(self.member.latest_membership, old)

    def test_member_payment_flag(self):
        self.make_membership()
        self.assertEqual(self.member.payment_flag(on=date(2026, 11, 26)), status.UNPAID)
        self.assertEqual(self.member.payment_flag(on=date(2026, 11, 29)), status.LATE)

    def test_gcash_needs_reference_number(self):
        p = Payment(membership=self.make_membership(), amount=Decimal("1000"), method=Payment.GCASH)
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_walk_in_needs_a_name_and_no_membership(self):
        with self.assertRaises(ValidationError):
            Payment(amount=Decimal("150")).full_clean()
        Payment(walk_in_name="Juan", amount=Decimal("150")).full_clean()  # no error

    def test_void_needs_a_reason(self):
        p = Payment(walk_in_name="Juan", amount=Decimal("150"), is_voided=True)
        with self.assertRaises(ValidationError):
            p.full_clean()
