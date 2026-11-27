"""
Member self sign-up on the desk phone, and the staff check afterwards.

Member side (sign-up mode, see gym/kiosk.py):
    kiosk_start   staff tap "Member sign-up": the phone locks to the form
    join          the member types their details
    join_done     "Thanks, hand the phone back"
    join_unlock   staff type their password to leave sign-up mode

Staff side:
    signup_list        sign-ups waiting to be checked
    signup_review      one sign-up, with any member who has the same phone or name
    signup_carry_over  "Notebook member": create them with the period they already paid
    signup_link        "Already on file": update that member's details
    signup_dismiss     spam or a double sign-up (kept, with who dismissed it)
    "New member" goes to the normal Add member form, filled in (members.member_add).
"""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .. import kiosk
from ..forms import PRIVACY_NOTICE, CarryOverForm, SignUpForm, UnlockForm
from ..importer import digits
from ..models import Member, Plan, SignUp
from ..services import carry_over_membership

MAX_TRIES = 5                     # wrong passwords before unlock pauses
PAUSE = timedelta(minutes=5)      # how long it pauses
PAUSE_KEY = "kiosk_paused_until"


# ---- Member side -------------------------------------------------------------
@require_POST
def kiosk_start(request):
    kiosk.turn_on(request)
    return redirect("join")


def join(request):
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        sign_up = form.save(commit=False)
        sign_up.consent_given_on = timezone.localdate()
        sign_up.entered_on = request.user
        sign_up.save()
        return redirect("join_done")
    return render(request, "gym/join.html", {"form": form, "privacy_notice": PRIVACY_NOTICE})


def join_done(request):
    return render(request, "gym/join_done.html")


def join_unlock(request):
    """Leave sign-up mode. The staff member who unlocks becomes the signed-in user."""
    if not kiosk.is_on(request):
        return redirect("signup_list")
    form = UnlockForm(request.POST or None)
    paused_until = request.session.get(PAUSE_KEY)
    paused = paused_until and timezone.now().timestamp() < paused_until

    if request.method == "POST" and not paused and form.is_valid():
        user = authenticate(request, username=form.cleaned_data["username"], password=form.cleaned_data["password"])
        if user is not None and user.is_active:
            login(request, user)
            kiosk.turn_off(request)
            request.session.pop(PAUSE_KEY, None)
            messages.success(request, "Sign-up mode is off.")
            return redirect("signup_list")
        tries = request.session.get(kiosk.FAILED_KEY, 0) + 1
        request.session[kiosk.FAILED_KEY] = tries
        if tries >= MAX_TRIES:
            request.session[PAUSE_KEY] = (timezone.now() + PAUSE).timestamp()
            request.session[kiosk.FAILED_KEY] = 0
            paused = True
        else:
            form.add_error(None, "Wrong username or password.")
    return render(request, "gym/join_unlock.html", {"form": form, "paused": paused})


# ---- Staff side --------------------------------------------------------------
def signup_list(request):
    pending = SignUp.objects.filter(status=SignUp.PENDING).order_by("created_at")
    recent = SignUp.objects.exclude(status=SignUp.PENDING).select_related("member", "handled_by")[:15]
    return render(request, "gym/signup_list.html", {"pending": pending, "recent": recent})


def possible_matches(sign_up):
    """Members with the same phone (spaces ignored) or the same full name or nickname."""
    phone = digits(sign_up.phone)
    names = {sign_up.full_name.lower(), (sign_up.nickname or sign_up.full_name).lower()}
    found = []
    for m in Member.objects.filter(is_archived=False):
        same_phone = bool(phone) and digits(m.phone) == phone
        same_name = m.full_name.lower() in names or (m.nickname and m.nickname.lower() in names)
        if same_phone or same_name:
            found.append({"member": m, "why": "same phone" if same_phone else "same name"})
    found.sort(key=lambda f: f["why"] != "same phone")  # phone matches first
    return found


def signup_review(request, pk, carry_form=None):
    sign_up = get_object_or_404(SignUp, pk=pk)
    monthly = Plan.objects.filter(is_active=True, name="Monthly").first()
    form = carry_form or CarryOverForm(initial={"plan": monthly, "amount_paid": monthly.price if monthly else None})
    return render(request, "gym/signup_review.html", {
        "sign_up": sign_up, "matches": possible_matches(sign_up), "carry_form": form,
    })


def pending_or_404(pk):
    return get_object_or_404(SignUp, pk=pk, status=SignUp.PENDING)


@require_POST
def signup_carry_over(request, pk):
    sign_up = pending_or_404(pk)
    form = CarryOverForm(request.POST)
    if not form.is_valid():
        return signup_review(request, pk, carry_form=form)
    d = form.cleaned_data
    member = Member.objects.create(
        **sign_up.member_fields(), joined_on=d["start_date"],
        notes=f"Carried over from the notebook on {timezone.localdate():%d %b %Y}.",
    )
    membership = carry_over_membership(member=member, plan=d["plan"], start_date=d["start_date"],
                                       end_date=d["end_date"], amount_paid=d["amount_paid"],
                                       method=d["method"], user=request.user)
    sign_up.close(SignUp.DONE, request.user, member)
    messages.success(request, f"{member.full_name} added as {member.member_code}, "
                              f"{membership.plan.name} until {membership.end_date:%d %b %Y}.")
    return redirect("member_detail", pk=member.pk)


@require_POST
def signup_link(request, pk, member_pk):
    sign_up = pending_or_404(pk)
    member = get_object_or_404(Member, pk=member_pk)
    # Copy over what they typed, but never blank out something already on file.
    for field, value in sign_up.member_fields().items():
        if value:
            setattr(member, field, value)
    member.save()
    sign_up.close(SignUp.DONE, request.user, member)
    messages.success(request, f"Updated {member.full_name}'s details from the sign-up.")
    return redirect("member_detail", pk=member.pk)


@require_POST
def signup_dismiss(request, pk):
    sign_up = pending_or_404(pk)
    sign_up.close(SignUp.DISMISSED, request.user)
    messages.success(request, f"Dismissed the sign-up from {sign_up.full_name}.")
    return redirect("signup_list")
