"""
"Message this member": builds an sms: link that opens the desk phone's own
SMS app with a reminder already typed. Staff press send. No paid SMS service.

Two details that matter:
- Messages say "PHP", not "₱". One ₱ sign switches the whole SMS to
  Unicode, which cuts it from 160 to 70 characters (2-3 texts instead of 1).
- The link uses "?&body=". Android reads the "?", iPhone reads the "&",
  so the same link pre-fills the message on both.
"""

import re
from urllib.parse import quote

from . import status

GYM_NAME = "Pumpzone Gym"


def first_name(member):
    return member.nickname.strip() or member.full_name.split()[0]


def money(amount):
    return f"PHP {amount:,.0f}"


def reminder_text(summary):
    """Pick the right message for this member. `summary` is a MemberSummary."""
    m = summary.member
    hi = f"Hi {first_name(m)}! {GYM_NAME} here."
    latest = summary.latest
    if summary.is_owing:
        plan = f" for your {latest.plan.name}" if latest else ""
        return (f"{hi} Friendly reminder: you still have a balance of {money(summary.balance)}{plan}. "
                f"You can pay at the front desk, cash or GCash. Salamat!")
    if summary.status == status.EXPIRING:
        when = "today" if summary.days_left == 0 else f"on {latest.end_date:%d %b}"
        return f"{hi} Your {latest.plan.name} membership ends {when}. Renew at the front desk to keep training. Salamat!"
    if summary.status == status.EXPIRED:
        return f"{hi} Your membership ended on {latest.end_date:%d %b}. We miss you! Drop by the front desk to renew. Salamat!"
    if latest:
        return f"{hi} Your membership is active until {latest.end_date:%d %b}. See you at the gym!"
    return f"{hi} See you at the gym!"


def sms_href(phone, text):
    """sms: link, or '' if there is no usable phone number."""
    number = re.sub(r"[^\d+]", "", phone or "")
    if len(number) < 7:
        return ""
    return f"sms:{number}?&body={quote(text)}"


def sms_link_for(summary):
    return sms_href(summary.member.phone, reminder_text(summary))
