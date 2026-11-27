"""
Cash-up per staff member. Pumpzone has two floors with one desk each, and
each desk has its own cash drawer. Splitting the day's money by who took
it lets each floor count its drawer against its own row.

Voided payments are left out, like every other total in the app.
"""

from dataclasses import dataclass
from decimal import Decimal

from .models import Payment


@dataclass
class StaffTotal:
    name: str
    count: int = 0
    cash: Decimal = Decimal("0")
    gcash: Decimal = Decimal("0")

    @property
    def total(self):
        return self.cash + self.gcash


def staff_name(user):
    if user is None:
        return "No staff recorded"  # e.g. imported from the notebook
    return user.get_full_name() or user.username


def by_staff(payments):
    """One StaffTotal per staff member, biggest total first. `payments` is any list of Payment."""
    rows = {}
    for p in payments:
        if p.is_voided:
            continue
        row = rows.setdefault(p.received_by_id, StaffTotal(staff_name(p.received_by)))
        row.count += 1
        if p.method == Payment.GCASH:
            row.gcash += p.amount
        else:
            row.cash += p.amount
    return sorted(rows.values(), key=lambda r: (-r.total, r.name))
