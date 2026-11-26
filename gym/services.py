"""
The actions staff take at the desk. Screens call these; they never
create memberships or payments themselves. Each action is all-or-nothing
(transaction.atomic): if anything fails, nothing is saved.
"""

from decimal import Decimal

from django.db import transaction

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


def record_payment(*, amount, method, user, membership=None, walk_in_name="", reference_no=""):
    """Money received. Checked by Payment.clean() (GCash ref, amount > 0)."""
    payment = Payment(
        membership=membership, walk_in_name=walk_in_name, amount=Decimal(amount),
        method=method, reference_no=reference_no.strip(), received_by=user,
    )
    payment.full_clean()
    payment.save()
    return payment
