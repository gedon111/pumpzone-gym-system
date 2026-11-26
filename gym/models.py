"""
Database tables. Each class below becomes one table.

    Plan        the price list (Monthly, Student Monthly, 3 Months, Day Pass)
    Member      a person on file
    Membership  one paid period for a member (one row per renewal)
    Payment     money received, cash or GCash. Never deleted, only voided.

Status (active / expiring / expired) is never stored. It is worked out
from dates each time, so it can never be out of date. See status.py.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from . import dates, status


def today():
    """Today's date in Manila time (settings.TIME_ZONE)."""
    return timezone.localdate()


class TimeStamped(models.Model):
    """Adds created_at / updated_at to every table that uses it."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True  # not a table itself


# ---------------------------------------------------------------------------
class Plan(TimeStamped):
    UNIT_CHOICES = [(dates.MONTH, "Months"), (dates.DAY, "Days")]

    name = models.CharField(max_length=60, unique=True)
    length = models.PositiveIntegerField(default=1, help_text="How many months or days.")
    unit = models.CharField(max_length=5, choices=UNIT_CHOICES, default=dates.MONTH)
    price = models.DecimalField(max_digits=9, decimal_places=2)
    is_active = models.BooleanField(default=True, help_text="Untick to hide an old price without deleting history.")

    class Meta:
        ordering = ["unit", "length", "name"]

    def __str__(self):
        return self.name

    def end_date_for(self, start):
        return dates.membership_end_date(start, self.unit, self.length)


# ---------------------------------------------------------------------------
class Member(TimeStamped):
    member_code = models.CharField(
        max_length=12, unique=True, editable=False,
        help_text="Year joined + number, e.g. 2026-0001. Set automatically and never changes.",
    )
    full_name = models.CharField(max_length=120)
    nickname = models.CharField(max_length=60, blank=True, help_text="Name used in the logbook.")
    phone = models.CharField(max_length=20, blank=True, db_index=True)
    birth_date = models.DateField(null=True, blank=True, help_text="Optional. Only used to show age.")
    emergency_contact_name = models.CharField(max_length=120, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    joined_on = models.DateField(default=today)
    consent_given_on = models.DateField(
        null=True, blank=True, help_text="Date the member agreed to the privacy notice."
    )
    notes = models.TextField(blank=True, help_text="Do NOT write health conditions here.")
    is_archived = models.BooleanField(default=False, help_text="Hide instead of deleting.")

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.member_code})"

    def save(self, *args, **kwargs):
        if not self.member_code:
            self.member_code = self.next_code(self.joined_on.year)
        super().save(*args, **kwargs)

    @staticmethod
    def next_code(year):
        """Next free code for that year: 2026-0001, 2026-0002, ..."""
        last = (
            Member.objects.filter(member_code__startswith=f"{year}-")
            .order_by("-member_code")
            .values_list("member_code", flat=True)
            .first()
        )
        number = int(last.split("-")[1]) + 1 if last else 1
        return f"{year}-{number:04d}"

    # --- worked-out values (not stored) -----------------------------------
    @property
    def age(self):
        if not self.birth_date:
            return None
        t = today()
        had_birthday = (t.month, t.day) >= (self.birth_date.month, self.birth_date.day)
        return t.year - self.birth_date.year - (0 if had_birthday else 1)

    @property
    def latest_membership(self):
        """The membership that ends last. Its end date decides the status."""
        return self.memberships.order_by("-end_date", "-id").first()

    def expiry_status(self, on=None):
        latest = self.latest_membership
        return status.expiry_status(
            latest.end_date if latest else None,
            on or today(),
            settings.EXPIRING_WITHIN_DAYS,
        )

    @property
    def balance(self):
        """Total still owed across all memberships."""
        return sum((m.balance for m in self.memberships.all()), Decimal("0"))

    def payment_flag(self, on=None):
        """LATE if any membership is late, else UNPAID if any is unpaid, else None."""
        flags = {m.payment_flag(on) for m in self.memberships.all()}
        if status.LATE in flags:
            return status.LATE
        if status.UNPAID in flags:
            return status.UNPAID
        return None


# ---------------------------------------------------------------------------
class Membership(TimeStamped):
    member = models.ForeignKey(Member, on_delete=models.PROTECT, related_name="memberships")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="memberships")
    start_date = models.DateField(default=today)
    end_date = models.DateField(blank=True, help_text="Last valid day. Leave blank to work it out from the plan.")
    list_price = models.DecimalField(
        max_digits=9, decimal_places=2, editable=False,
        help_text="The plan price at the time, kept so discounts are visible.",
    )
    price_agreed = models.DecimalField(
        max_digits=9, decimal_places=2, blank=True,
        help_text="What the member must pay. Lower than the plan price = discount.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, editable=False,
        related_name="+", help_text="Staff who sold it (and set any discount).",
    )

    class Meta:
        ordering = ["-end_date"]

    def __str__(self):
        return f"{self.member.full_name}: {self.plan} {self.start_date:%d %b} to {self.end_date:%d %b %Y}"

    def save(self, *args, **kwargs):
        # Fill in anything left blank from the plan.
        if not self.end_date:
            self.end_date = self.plan.end_date_for(self.start_date)
        if self.list_price is None:
            self.list_price = self.plan.price
        if self.price_agreed is None:
            self.price_agreed = self.plan.price
        super().save(*args, **kwargs)

    @property
    def discount(self):
        return self.list_price - self.price_agreed

    @property
    def amount_paid(self):
        total = self.payments.filter(is_voided=False).aggregate(t=Sum("amount"))["t"]
        return total or Decimal("0")

    @property
    def balance(self):
        return self.price_agreed - self.amount_paid

    def payment_flag(self, on=None):
        return status.payment_flag(self.balance, self.start_date, on or today(), settings.GRACE_DAYS)


# ---------------------------------------------------------------------------
class Payment(TimeStamped):
    CASH, GCASH, OTHER = "cash", "gcash", "other"
    METHOD_CHOICES = [(CASH, "Cash"), (GCASH, "GCash"), (OTHER, "Other")]

    # A payment is for a member's membership, OR a walk-in day pass (name only).
    membership = models.ForeignKey(
        Membership, on_delete=models.PROTECT, null=True, blank=True, related_name="payments"
    )
    walk_in_name = models.CharField(
        max_length=120, blank=True, help_text="Walk-in day pass only. Valid on the day paid."
    )
    amount = models.DecimalField(max_digits=9, decimal_places=2)
    method = models.CharField(max_length=6, choices=METHOD_CHOICES, default=CASH)
    reference_no = models.CharField(max_length=40, blank=True, help_text="Required for GCash.")
    paid_on = models.DateTimeField(default=timezone.now)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, editable=False, related_name="+"
    )

    # Payments are never deleted. The owner voids a mistake and gives a reason.
    is_voided = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-paid_on"]

    def __str__(self):
        who = self.membership.member.full_name if self.membership else f"Walk-in: {self.walk_in_name}"
        return f"₱{self.amount} {self.get_method_display()} · {who}"

    def clean(self):
        """Form checks. Runs in the admin and in our own forms."""
        errors = {}
        if bool(self.membership_id) == bool(self.walk_in_name):
            errors["walk_in_name"] = "Choose a membership, or type a walk-in name. Not both."
        if self.method == self.GCASH and not self.reference_no.strip():
            errors["reference_no"] = "GCash payments need the reference number."
        if self.amount is not None and self.amount <= 0:
            errors["amount"] = "Amount must be more than zero."
        if self.is_voided and not self.void_reason.strip():
            errors["void_reason"] = "Say why this payment is voided."
        if errors:
            raise ValidationError(errors)

    @property
    def is_walk_in(self):
        return self.membership_id is None
