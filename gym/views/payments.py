"""Payment screens: collect from a member, walk-in day pass, payments by day."""

from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from ..forms import PaymentForm, WalkInForm
from ..models import Member, Payment, Plan
from ..services import record_payment
from ..templatetags.pumpzone import peso


def payment_add(request, pk):
    """Collect money from a member. Defaults to the oldest unpaid period and its full balance."""
    member = get_object_or_404(Member, pk=pk)
    memberships = list(member.memberships.order_by("start_date"))
    owing = [m for m in memberships if m.balance > 0]
    initial = {}
    if owing:
        initial = {"membership": owing[0], "amount": owing[0].balance}
    elif memberships:
        initial = {"membership": memberships[-1]}

    form = PaymentForm(request.POST or None, member=member, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        record_payment(membership=d["membership"], amount=d["amount"], method=d["method"],
                       reference_no=d["reference_no"], user=request.user)
        left = member.balance
        messages.success(request, f"{peso(d['amount'])} received from {member.full_name}. "
                                  + (f"{peso(left)} still owed." if left > 0 else "Fully paid."))
        return redirect("member_detail", pk=member.pk)
    return render(request, "gym/payment_form.html", {
        "form": form, "member": member, "title": f"Collect from {member.full_name}", "no_membership": not memberships,
    })


def walk_in(request):
    """Day pass for a non-member: a payment with a name, valid today only."""
    day_pass = Plan.objects.filter(is_active=True, unit="day", length=1).first()
    form = WalkInForm(request.POST or None, initial={"amount": day_pass.price if day_pass else None})
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        record_payment(walk_in_name=d["walk_in_name"].strip(), amount=d["amount"], method=d["method"],
                       reference_no=d["reference_no"], user=request.user)
        messages.success(request, f"Day pass for {d['walk_in_name']}: {peso(d['amount'])} received. Valid today only.")
        return redirect("payment_list")
    return render(request, "gym/payment_form.html", {"form": form, "title": "Walk-in day pass"})


def payment_list(request):
    """All payments on one day (default today), with totals for the cash drawer."""
    today = timezone.localdate()
    day = parse_date(request.GET.get("day", "")) or today
    payments = list(Payment.objects.filter(paid_on__date=day)
                    .select_related("membership__member", "membership__plan", "received_by"))
    kept = [p for p in payments if not p.is_voided]
    totals = []
    for key, label in Payment.METHOD_CHOICES:
        amount = sum((p.amount for p in kept if p.method == key), Decimal("0"))
        if amount:
            totals.append({"label": label, "amount": amount})
    return render(request, "gym/payment_list.html", {
        "day": day, "is_today": day == today, "payments": payments, "totals": totals,
        "total": sum((p.amount for p in kept), Decimal("0")),
        "prev_day": day - timedelta(days=1), "next_day": day + timedelta(days=1) if day < today else None,
    })
