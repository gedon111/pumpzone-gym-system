"""Member screens: list and search, detail, add, edit, renew."""

from django.contrib import messages
from django.db.models import Q, Value
from django.db.models.functions import Replace
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .. import dates, status
from ..forms import AddMemberForm, EditMemberForm, RenewForm
from ..models import Member
from ..services import add_member, sell_membership
from ..summary import summarize, summarize_all, urgency
from ..templatetags.pumpzone import peso

STATUS_FILTERS = [  # (?status=..., label)
    ("", "All"),
    (status.ACTIVE, "Active"),
    (status.EXPIRING, "Expiring"),
    (status.EXPIRED, "Expired"),
    ("owing", "Owing"),
]


def member_list(request):
    """Search by name, nickname, phone (spaces ignored) or member code."""
    q = request.GET.get("q", "").strip()
    wanted = request.GET.get("status", "")
    members = Member.objects.filter(is_archived=False)
    if q:
        digits = q.replace(" ", "")
        members = members.annotate(phone_digits=Replace("phone", Value(" "), Value(""))).filter(
            Q(full_name__icontains=q) | Q(nickname__icontains=q)
            | Q(member_code__icontains=q) | Q(phone_digits__icontains=digits)
        )
    rows = summarize_all(timezone.localdate(), members)
    if wanted == "owing":
        rows = [s for s in rows if s.is_owing]
    elif wanted:
        rows = [s for s in rows if s.status == wanted]
    rows.sort(key=urgency if wanted in ("", status.EXPIRING, status.EXPIRED, "owing") else (lambda s: s.member.full_name))
    return render(request, "gym/member_list.html", {
        "rows": rows, "q": q, "wanted": wanted, "filters": STATUS_FILTERS,
    })


def member_detail(request, pk):
    member = get_object_or_404(Member, pk=pk)
    summary = summarize(member, timezone.localdate())
    memberships = member.memberships.select_related("plan", "created_by").prefetch_related("payments")
    payments = [p for m in memberships for p in m.payments.all()]
    payments.sort(key=lambda p: p.paid_on, reverse=True)
    return render(request, "gym/member_detail.html", {
        "s": summary, "member": member, "memberships": memberships, "payments": payments,
    })


def member_add(request):
    """New member + first membership + payment, on one screen."""
    form = AddMemberForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        member = add_member(member_fields=form.member_fields(), user=request.user,
                            **form.plan_values(), **form.sale_values())
        messages.success(request, f"Added {member.full_name} as {member.member_code}. {paid_text(member)}")
        return redirect("member_detail", pk=member.pk)
    return render(request, "gym/member_form.html", {"form": form, "title": "Add member", "submit": "Add member"})


def member_edit(request, pk):
    member = get_object_or_404(Member, pk=pk)
    form = EditMemberForm(request.POST or None, instance=member)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Details saved.")
        return redirect("member_detail", pk=member.pk)
    return render(request, "gym/member_form.html", {
        "form": form, "member": member, "title": f"Edit {member.full_name}", "submit": "Save details",
    })


def member_renew(request, pk):
    """
    Renew in one tap: the plan defaults to their last plan, the start
    date to the day after the current period ends (or today if expired).
    """
    member = get_object_or_404(Member, pk=pk)
    latest = member.latest_membership
    today = timezone.localdate()
    initial = {"start_date": dates.renewal_start_date(latest.end_date if latest else None, today)}
    if latest and latest.plan.is_active:
        initial["plan"] = latest.plan

    form = RenewForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        membership = sell_membership(member=member, user=request.user, **form.plan_values(), **form.sale_values())
        messages.success(request, f"Renewed {member.full_name} until {membership.end_date:%d %b %Y}. {paid_text(member)}")
        return redirect("member_detail", pk=member.pk)
    return render(request, "gym/renew.html", {
        "form": form, "member": member, "s": summarize(member, today),
    })


def paid_text(member):
    """'Fully paid.' or '₱500 still owed.' for the confirmation message."""
    owed = member.balance
    return f"{peso(owed)} still owed." if owed > 0 else "Fully paid."

