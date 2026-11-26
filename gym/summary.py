"""
One summary per member: status, days left, money owed, and the short
note shown on screen ("2 days left", "Late 5 days").

Used by the dashboard and the member list. Loads every member with
their memberships and payments in 3 database queries total, then does
the rest in Python. Fast enough for thousands of members.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db.models import Prefetch

from . import status
from .models import Member, Membership


def members_with_history(queryset=None):
    """Members plus their memberships (with plan) and payments, preloaded."""
    queryset = queryset if queryset is not None else Member.objects.filter(is_archived=False)
    return queryset.prefetch_related(
        Prefetch("memberships", queryset=Membership.objects.select_related("plan").prefetch_related("payments"))
    )


@dataclass
class MemberSummary:
    member: Member
    latest: Membership | None
    status: str          # status.ACTIVE / EXPIRING / EXPIRED / NONE
    days_left: int | None
    balance: Decimal
    flag: str | None     # status.UNPAID / LATE / None
    late_days: int       # days past the grace period (0 if not late)

    @property
    def needs_action(self):
        recently_expired = self.status == status.EXPIRED and self.days_left >= -30
        return self.status == status.EXPIRING or recently_expired or self.flag is not None

    @property
    def is_owing(self):
        return self.flag is not None

    @property
    def can_renew(self):
        return self.status in (status.EXPIRING, status.EXPIRED, status.NONE)

    @property
    def status_note(self):
        """Short text for the status chip."""
        d = self.days_left
        if self.status == status.EXPIRING:
            return "Last day today" if d == 0 else f"{d} day{'s' if d != 1 else ''} left"
        if self.status == status.EXPIRED:
            return "Expired yesterday" if d == -1 else f"Expired {-d} days ago"
        if self.status == status.ACTIVE:
            return f"Active, {d} days left"
        return "No membership yet"

    @property
    def flag_note(self):
        if self.flag == status.LATE:
            return f"Late {self.late_days} day{'s' if self.late_days != 1 else ''}"
        if self.flag == status.UNPAID:
            return "Unpaid"
        return ""


def summarize(member: Member, today: date) -> MemberSummary:
    """Work out everything the screens show about one member."""
    latest = member.latest_membership
    days_left = status.days_left(latest.end_date, today) if latest else None
    member_status = status.expiry_status(latest.end_date if latest else None, today, settings.EXPIRING_WITHIN_DAYS)

    # Money: look at every membership that still has a balance.
    owing = [m for m in member.memberships.all() if m.balance > 0]
    balance = sum((m.balance for m in owing), Decimal("0"))
    flag, late_days = None, 0
    if owing:
        oldest_start = min(m.start_date for m in owing)
        flag = status.payment_flag(balance, oldest_start, today, settings.GRACE_DAYS)
        if flag == status.LATE:
            late_days = (today - oldest_start).days - settings.GRACE_DAYS

    return MemberSummary(member, latest, member_status, days_left, balance, flag, late_days)


def summarize_all(today: date, queryset=None) -> list[MemberSummary]:
    return [summarize(m, today) for m in members_with_history(queryset)]


# Sort order for lists: most urgent first.
STATUS_ORDER = {status.EXPIRING: 0, status.EXPIRED: 1, status.ACTIVE: 2, status.NONE: 3}


def urgency(s: MemberSummary):
    if s.status == status.EXPIRING:
        return (0, s.days_left)
    if s.flag == status.LATE:
        return (1, -s.late_days)
    if s.status == status.EXPIRED:
        return (2, -s.days_left)
    return (3, s.member.full_name)
