"""End dates and renewal start dates. No database needed."""

from datetime import date

from django.test import SimpleTestCase

from gym.dates import DAY, MONTH, add_months, membership_end_date, renewal_start_date


class EndDateTests(SimpleTestCase):
    def test_monthly_plan_ends_same_date_next_month(self):
        # The gym's rule: start 25 Nov, last valid day 25 Dec.
        self.assertEqual(membership_end_date(date(2026, 11, 25), MONTH, 1), date(2026, 12, 25))

    def test_three_month_plan_crosses_the_year(self):
        self.assertEqual(membership_end_date(date(2026, 11, 25), MONTH, 3), date(2027, 2, 25))

    def test_short_month_uses_last_day(self):
        self.assertEqual(add_months(date(2027, 1, 31), 1), date(2027, 2, 28))
        self.assertEqual(add_months(date(2028, 1, 31), 1), date(2028, 2, 29))  # leap year

    def test_day_pass_ends_same_day(self):
        self.assertEqual(membership_end_date(date(2026, 11, 26), DAY, 1), date(2026, 11, 26))

    def test_seven_day_pass_counts_start_as_day_one(self):
        self.assertEqual(membership_end_date(date(2026, 11, 26), DAY, 7), date(2026, 12, 2))


class RenewalStartTests(SimpleTestCase):
    today = date(2026, 11, 26)

    def test_early_renewal_starts_after_current_end(self):
        # Still has days left: do not waste them.
        self.assertEqual(renewal_start_date(date(2026, 11, 30), self.today), date(2026, 12, 1))

    def test_renewal_on_last_day_starts_tomorrow(self):
        self.assertEqual(renewal_start_date(self.today, self.today), date(2026, 11, 27))

    def test_late_renewal_starts_today(self):
        self.assertEqual(renewal_start_date(date(2026, 11, 1), self.today), self.today)

    def test_first_membership_starts_today(self):
        self.assertEqual(renewal_start_date(None, self.today), self.today)
