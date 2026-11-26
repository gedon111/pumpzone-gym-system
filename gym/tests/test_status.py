"""Expiry status and payment flags at every boundary day. No database needed."""

from datetime import date, timedelta
from decimal import Decimal

from django.test import SimpleTestCase

from gym import status

TODAY = date(2026, 11, 26)


def ends_in(days):
    return TODAY + timedelta(days=days)


class ExpiryStatusTests(SimpleTestCase):
    def test_eight_days_left_is_active(self):
        self.assertEqual(status.expiry_status(ends_in(8), TODAY), status.ACTIVE)

    def test_seven_days_left_is_expiring(self):
        self.assertEqual(status.expiry_status(ends_in(7), TODAY), status.EXPIRING)

    def test_last_day_is_still_expiring_not_expired(self):
        self.assertEqual(status.expiry_status(ends_in(0), TODAY), status.EXPIRING)

    def test_day_after_last_day_is_expired(self):
        self.assertEqual(status.expiry_status(ends_in(-1), TODAY), status.EXPIRED)

    def test_no_membership(self):
        self.assertEqual(status.expiry_status(None, TODAY), status.NONE)

    def test_days_left(self):
        self.assertEqual(status.days_left(ends_in(3), TODAY), 3)
        self.assertEqual(status.days_left(ends_in(-2), TODAY), -2)


class PaymentFlagTests(SimpleTestCase):
    start = date(2026, 11, 25)  # grace days: 26, 27, 28 Nov. Late from 29 Nov.

    def flag(self, balance, on):
        return status.payment_flag(Decimal(balance), self.start, on, grace_days=3)

    def test_fully_paid_has_no_flag(self):
        self.assertIsNone(self.flag("0", date(2026, 12, 20)))

    def test_overpaid_has_no_flag(self):
        self.assertIsNone(self.flag("-100", date(2026, 12, 20)))

    def test_owed_on_last_grace_day_is_unpaid(self):
        self.assertEqual(self.flag("500", date(2026, 11, 28)), status.UNPAID)

    def test_owed_after_grace_period_is_late(self):
        self.assertEqual(self.flag("500", date(2026, 11, 29)), status.LATE)
