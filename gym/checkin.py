"""
Check-in: find the member from a card tap or what staff type, log the
visit, and say in one word whether they may train.

NFC-ready without any driver or JavaScript: a USB NFC reader that works
as a keyboard ("keyboard emulation" / "HID", 13.56 MHz) types the card
number and presses Enter, exactly as if staff had typed it. So the same
box takes a card tap, a member code, a phone number or a nickname.
(Readers like the ACR122U are NOT keyboard readers: they need a driver
and extra software, so don't buy that kind for this.)
"""

from dataclasses import dataclass

from django.db.models import Q
from django.utils import timezone

from . import status
from .importer import digits
from .models import CheckIn, Member, clean_card_uid
from .summary import MemberSummary, members_with_history, summarize

# What the big result card says. tone = colour: go (green), soon (amber), out (red).
GO, SOON, OUT = "go", "soon", "out"

# Owner's rule for student prices (2026-11-27).
STUDENT_CHECK = "Student rate: check their student ID or school uniform."


@dataclass
class Lookup:
    members: list       # 0 = not found, 1 = found, 2+ = staff pick one
    how: str            # CheckIn.CARD if it matched a card number, else CheckIn.TYPED


def find(text) -> Lookup:
    text = (text or "").strip()
    if not text:
        return Lookup([], CheckIn.TYPED)
    active = members_with_history(Member.objects.filter(is_archived=False))

    uid = clean_card_uid(text)
    by_card = list(active.filter(card_uid=uid)) if uid else []
    if by_card:
        return Lookup(by_card, CheckIn.CARD)

    by_code = list(active.filter(member_code__iexact=text))
    if by_code:
        return Lookup(by_code, CheckIn.TYPED)

    number = digits(text)
    if len(number) >= 7:  # looks like a phone number
        by_phone = [m for m in active.exclude(phone="") if digits(m.phone) == number]
        if by_phone:
            return Lookup(by_phone, CheckIn.TYPED)

    by_name = list(active.filter(Q(nickname__iexact=text) | Q(full_name__icontains=text))[:12])
    return Lookup(by_name, CheckIn.TYPED)


def log(member, user, how) -> CheckIn:
    """Record the visit, with the status it had at that moment."""
    s = summarize(member, timezone.localdate())
    return CheckIn.objects.create(member=member, by=user, how=how, status_then=s.status)


def verdict(s: MemberSummary):
    """(tone, headline, detail) for the big result card."""
    tone, headline, detail = plain_verdict(s)
    if s.latest and s.latest.plan.is_student and tone != OUT:
        detail = f"{detail} {STUDENT_CHECK}"
    return tone, headline, detail


def plain_verdict(s: MemberSummary):
    end = s.latest.end_date if s.latest else None
    if s.status == status.EXPIRED:
        return OUT, "Expired", f"Ended {end:%d %b}. Renew before training."
    if s.status == status.NONE:
        return OUT, "No membership", "Sell a plan before training."
    if s.flag == status.LATE:
        return OUT, f"Owes ₱{s.balance:,.0f}", f"Late {s.late_days} day{'s' if s.late_days != 1 else ''}. Collect before training."
    if s.status == status.EXPIRING:
        when = "today" if s.days_left == 0 else f"in {s.days_left} day{'s' if s.days_left != 1 else ''}"
        detail = f"Ends {when} ({end:%d %b}). Offer a renewal."
        return SOON, "Expiring", detail + (f" Also owes ₱{s.balance:,.0f}." if s.is_owing else "")
    if s.is_owing:
        return SOON, "Active, owes", f"Until {end:%d %b}. Still owes ₱{s.balance:,.0f}."
    return GO, "Active", f"Until {end:%d %b}. Enjoy the session!"
