"""
Member status rules: the core of the product. Plain Python, fully tested.

Expiry status (from the end date of the member's latest membership):
    ACTIVE    more than 7 days left
    EXPIRING  0 to 7 days left (0 = today is the last day)
    EXPIRED   the last day has passed
    NONE      the member has never had a membership

Payment flag (from the money still owed on a membership):
    None      fully paid
    UNPAID    money owed, still inside the grace period
    LATE      money owed and the grace period is over
"""

from datetime import date
from decimal import Decimal

ACTIVE = "active"
EXPIRING = "expiring"
EXPIRED = "expired"
NONE = "none"

UNPAID = "unpaid"
LATE = "late"


def days_left(end_date: date, today: date) -> int:
    """Days until the last valid day. 0 = today is the last day, negative = expired."""
    return (end_date - today).days


def expiry_status(end_date: date | None, today: date, expiring_within: int = 7) -> str:
    """Active, expiring or expired, based on the last valid day."""
    if end_date is None:
        return NONE
    left = days_left(end_date, today)
    if left < 0:
        return EXPIRED
    if left <= expiring_within:
        return EXPIRING
    return ACTIVE


def payment_flag(balance: Decimal, start_date: date, today: date, grace_days: int = 3) -> str | None:
    """
    Unpaid or late, based on money still owed.

    With 3 grace days, a membership starting 25 Nov may be unpaid on
    25, 26, 27 and 28 Nov. From 29 Nov it is late.
    """
    if balance <= 0:
        return None
    if (today - start_date).days > grace_days:
        return LATE
    return UNPAID
