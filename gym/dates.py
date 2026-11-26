"""
Date math for memberships. Plain Python, no database, so it is easy to test.

The gym's rule (agreed 2026-11-26): a monthly plan that starts on 25 Nov
has 25 Dec as its LAST valid day. It counts as expired from 26 Dec.
"""

import calendar
from datetime import date, timedelta

# Plan length units. Stored on each Plan.
MONTH = "month"
DAY = "day"


def add_months(start: date, months: int) -> date:
    """
    Same day-of-month, `months` later.

    If that day does not exist (31 Jan + 1 month), use the last day of the
    month instead (28 or 29 Feb).
    """
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    last_day_of_month = calendar.monthrange(year, month)[1]
    return date(year, month, min(start.day, last_day_of_month))


def membership_end_date(start: date, unit: str, length: int) -> date:
    """
    Last day a member may still train.

    - Month plans: same date N months later (25 Nov + 1 month = 25 Dec).
    - Day plans: the start day counts as day 1, so a 1-day pass ends the
      same day and a 7-day pass ends 6 days later.
    """
    if unit == MONTH:
        return add_months(start, length)
    return start + timedelta(days=length - 1)


def renewal_start_date(current_end: date | None, today: date) -> date:
    """
    Start date for a renewal.

    Renewing early must not waste paid days, so the new period starts the
    day after the current one ends. If the old one already ended (or there
    is none), the new one starts today.
    """
    if current_end is None:
        return today
    return max(today, current_end + timedelta(days=1))
