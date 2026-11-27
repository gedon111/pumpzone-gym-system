"""
The actions staff take at the desk. Screens call these; they never
create memberships or payments themselves. Each action is all-or-nothing
(transaction.atomic): if anything fails, nothing is saved.
"""

from datetime import datetime, time
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import Member, Membership, Payment

# How the member is paying right now (radio buttons on the forms).
PAY_FULL, PAY_PARTIAL, PAY_LATER = "full", "partial", "later"


@transaction.atomic
def sell_membership(*, member, plan, start_date, user, price_agreed=None,
                    pay=PAY_FULL, amount=None, method=Payment.CASH, reference_no=""):
    """
    New membership period for a member (first sign-up or a renewal),
    plus the payment taken at the counter, if any.
    """
    membership = Membership.objects.create(
        member=member, plan=plan, start_date=start_date,
        price_agreed=price_agreed if price_agreed is not None else plan.price,
        created_by=user,
    )
    if pay == PAY_FULL:
        amount = membership.price_agreed
    if pay in (PAY_FULL, PAY_PARTIAL) and amount and amount > 0:
        record_payment(membership=membership, amount=amount, method=method, reference_no=reference_no, user=user)
    return membership


@transaction.atomic
def add_member(*, member_fields, user, **sale):
    """Create the member and sell their first membership in one go."""
    member = Member.objects.create(**member_fields)
    sell_membership(member=member, user=user, **sale)
    return member


def record_payment(*, amount, method, user, membership=None, walk_in_name="", walk_in_plan=None,
                   reference_no="", paid_on=None):
    """Money received. Checked by Payment.clean() (GCash ref, amount > 0)."""
    payment = Payment(
        membership=membership, walk_in_name=walk_in_name, walk_in_plan=walk_in_plan, amount=Decimal(amount),
        method=method, reference_no=reference_no.strip(), received_by=user,
        paid_on=paid_on or timezone.now(),
    )
    payment.full_clean()
    payment.save()
    return payment


NOTEBOOK_REF = "from notebook"


@transaction.atomic
def carry_over_membership(*, member, plan, start_date, amount_paid, method, user, end_date=None):
    """
    A period the member already paid for in the paper notebook.

    The payment is dated at noon on the notebook start date, so it does
    NOT count in today's drawer. It has no "received by" (nobody in the
    system took it) and its reference says "from notebook".
    """
    membership = Membership.objects.create(
        member=member, plan=plan, start_date=start_date, end_date=end_date,
        price_agreed=plan.price, created_by=user,
    )
    if amount_paid and amount_paid > 0:
        record_payment(
            membership=membership, amount=amount_paid, method=method, user=None, reference_no=NOTEBOOK_REF,
            paid_on=timezone.make_aware(datetime.combine(start_date, time(12, 0))),
        )
    return membership
