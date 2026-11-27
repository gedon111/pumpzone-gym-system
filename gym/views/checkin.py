"""
Check-in screen: one box, always focused. Tap a card on the USB reader,
or type a member code, phone or nickname, then Enter.

After a check-in the page reloads with ?last=<id>, so refreshing never logs
the same visit twice, and the box is ready for the next person at once.
"""

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .. import checkin
from ..models import CheckIn, Member
from ..summary import summarize


def check_in(request):
    today = timezone.localdate()
    context = {"query": "", "choices": [], "not_found": False, "result": None}

    if request.method == "POST":
        member_pk = request.POST.get("member")
        if member_pk:  # staff picked one name from a list
            member = get_object_or_404(Member, pk=member_pk, is_archived=False)
            visit = checkin.log(member, request.user, CheckIn.TYPED)
            return redirect(reverse("check_in") + f"?last={visit.pk}")

        query = request.POST.get("code", "")
        found = checkin.find(query)
        if len(found.members) == 1:
            visit = checkin.log(found.members[0], request.user, found.how)
            return redirect(reverse("check_in") + f"?last={visit.pk}")
        context.update(query=query, choices=found.members, not_found=not found.members)

    last = request.GET.get("last")
    if last and last.isdigit():
        visit = CheckIn.objects.select_related("member").filter(pk=last).first()
        if visit:
            s = summarize(visit.member, today)
            tone, headline, detail = checkin.verdict(s)
            context["result"] = {"visit": visit, "s": s, "tone": tone, "headline": headline, "detail": detail}

    today_visits = CheckIn.objects.filter(at__date=today).select_related("member")
    context["count_today"] = today_visits.count()
    context["recent"] = today_visits[:12]
    return render(request, "gym/check_in.html", context)
