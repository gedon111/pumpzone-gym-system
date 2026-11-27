"""
Home screen (front desk dashboard). Layout follows mockup/dashboard.html:

    hero         headline + dot grid (every member is one square)
    tiles        Active / Expiring in 7 days / Expired last 30 days / Unpaid or late
    action list  members who need something today, with filter tabs (?show=...)
    side         money collected today, 4-week expiry calendar
    table        latest payments
"""

from collections import Counter
from datetime import timedelta
from decimal import Decimal

from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from .. import status
from ..cashup import by_staff
from ..models import Payment
from ..summary import summarize_all, urgency

FILTERS = [  # (key in ?show=, tab label)
    ("all", "All"),
    ("expiring", "Expiring"),
    ("expired", "Expired"),
    ("unpaid", "Unpaid"),
]
CAPTIONS = {
    "all": "Everyone who needs attention today",
    "expiring": "Ending within 7 days. Offer a renewal.",
    "expired": "Expired in the last 30 days. Invite them back.",
    "unpaid": "Still owe money. Late = past the grace period.",
}
DOT_CLASS = {status.ACTIVE: "c-act", status.EXPIRING: "c-soon", status.EXPIRED: "c-out", status.NONE: "c-none"}


def dashboard(request):
    today = timezone.localdate()
    summaries = summarize_all(today)

    # ---- counts ------------------------------------------------------------
    by_status = Counter(s.status for s in summaries)
    needs_action = sorted((s for s in summaries if s.needs_action), key=urgency)
    groups = {
        "all": needs_action,
        "expiring": [s for s in needs_action if s.status == status.EXPIRING],
        "expired": [s for s in needs_action if s.status == status.EXPIRED],
        "unpaid": [s for s in needs_action if s.is_owing],
    }
    owing_total = sum((s.balance for s in groups["unpaid"]), Decimal("0"))

    show = request.GET.get("show", "all")
    if show not in groups:
        show = "all"

    tiles = [
        {"key": "active", "label": "Active", "value": by_status[status.ACTIVE], "sub": "More than 7 days left", "dot": "c-act",
         "href": reverse("member_list") + "?status=active"},
        {"key": "expiring", "label": "Expiring in 7 days", "value": len(groups["expiring"]), "sub": "Renew before they lapse", "dot": "c-soon", "href": "?show=expiring#action"},
        {"key": "expired", "label": "Expired, last 30 days", "value": len(groups["expired"]), "sub": "Win-back list", "dot": "c-out", "href": "?show=expired#action"},
        {"key": "unpaid", "label": "Unpaid or late", "value": len(groups["unpaid"]), "sub": f"₱{owing_total:,.0f} still owed", "dot": "c-soon", "href": "?show=unpaid#action"},
    ]

    # ---- dot grid: every member, sorted by status --------------------------
    order = [status.ACTIVE, status.EXPIRING, status.EXPIRED, status.NONE]
    dots = [DOT_CLASS[s.status] for s in sorted(summaries, key=lambda s: order.index(s.status))]

    context = {
        "today": today,
        "summaries_count": len(summaries),
        "by_status": {k: by_status[k] for k in order},
        "dots": dots,
        "tiles": tiles,
        "show": show,
        "tabs": [{"key": k, "label": label, "count": len(groups[k])} for k, label in FILTERS],
        "rows": groups[show],
        "caption": CAPTIONS[show],
        "expiring_count": len(groups["expiring"]),
        "owing_count": len(groups["unpaid"]),
        "calendar": expiry_calendar(summaries, today),
        "weekdays": [(today + timedelta(days=i)).strftime("%a") for i in range(7)],
        "collected": collected_today(today),
        "latest_payments": Payment.objects.select_related("membership__member", "membership__plan", "walk_in_plan", "received_by")[:8],
    }
    return render(request, "gym/dashboard.html", context)


def expiry_calendar(summaries, today, days=28):
    """How many memberships end on each of the next 4 weeks' days."""
    ends = Counter(s.latest.end_date for s in summaries if s.latest)
    cells = []
    for i in range(days):
        day = today + timedelta(days=i)
        count = ends[day]
        level = 0 if count == 0 else 1 if count <= 2 else 2 if count <= 4 else 3
        cells.append({"date": day, "count": count, "level": level, "is_today": i == 0})
    return cells


def collected_today(today):
    """Money taken today, split by method. Voided payments are left out."""
    payments = list(Payment.objects.filter(paid_on__date=today, is_voided=False).select_related("received_by"))
    total = Decimal("0")
    methods = []
    for key, label in Payment.METHOD_CHOICES:
        rows = [p for p in payments if p.method == key]
        amount = sum((p.amount for p in rows), Decimal("0"))
        total += amount
        methods.append({"key": key, "label": label, "count": len(rows), "amount": amount})
    for m in methods:
        m["share"] = round(m["amount"] / total * 100) if total else 0
    return {"total": total, "count": sum(m["count"] for m in methods), "methods": methods,
            "staff": by_staff(payments)}  # one row per desk / floor
