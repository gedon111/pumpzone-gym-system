"""
Check-in: find the member from a card tap or what staff type, log the
visit, and say in one word whether they may train.

NFC-ready without any driver or JavaScript: a USB NFC reader in "keyboard
mode" (ACR122U class, or the cheap 13.56 MHz USB readers) types the card
number and presses Enter, exactly as if staff had typed it. So the same
box takes a card tap, a member code, a phone number or a nickname.
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
