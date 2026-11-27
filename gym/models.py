"""
Database tables. Each class below becomes one table.

    Plan        the price list (Monthly, 15 Days, Day Pass, and Student versions)
    Member      a person on file
    Membership  one paid period for a member (one row per renewal)
    Payment     money received, cash or GCash. Never deleted, only voided.
    CheckIn     one visit (card tap or typed code). Replaces the logbook.
    SignUp      details a person typed in themselves on the desk phone,
                waiting for staff to check them (see views/signups.py)

Status (active / expiring / expired) is never stored. It is worked out
from dates each time, so it can never be out of date. See status.py.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
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
        ordering = ["-unit", "length", "name"]  # month plans first, day passes last

    def __str__(self):
        return self.name

    def end_date_for(self, start):
        return dates.membership_end_date(start, self.unit, self.length)


def clean_card_uid(value):
    """
    Card numbers as the reader types them, tidied: no spaces or colons,
    capital letters. Blank becomes None, so many members can have no card.
    """
    value = "".join(ch for ch in (value or "") if ch.isalnum()).upper()
    return value or None


# ---------------------------------------------------------------------------
class Member(TimeStamped):
    member_code = models.CharField(
        max_length=12, unique=True, editable=False,
        help_text="Year joined + number, e.g. 2026-0001. Set automatically and never changes.",
    )
    full_name = models.CharField(max_length=120)
    nickname = models.CharField(max_length=60, blank=True, help_text="Name used in the logbook.")
    phone = models.CharField(max_length=20, blank=True, db_index=True)
    birth_date = models.DateField(null=True, blank=True, help_text="Only used to show age.")
    emergency_contact_name = models.CharField(max_length=120, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    joined_on = models.DateField(default=today)
    consent_given_on = models.DateField(
        null=True, blank=True, help_text="Date the member agreed to the privacy notice."
    )
    notes = models.TextField(blank=True, help_text="Do NOT write health conditions here.")
    is_archived = models.BooleanField(default=False, help_text="Hide instead of deleting.")
    card_uid = models.CharField(
        "card number", max_length=40, unique=True, null=True, blank=True,
        help_text="NFC card or keyfob number. Click here and tap the card on the reader.",
    )

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.member_code})"

    def save(self, *args, **kwargs):
        if not self.member_code:
            self.member_code = self.next_code(self.joined_on.year)
        self.card_uid = clean_card_uid(self.card_uid)
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
        # Uses .all() so it reuses data already loaded by summary.py (no extra query).
        memberships = list(self.memberships.all())
        return max(memberships, key=lambda m: (m.end_date, m.id), default=None)

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
        # Summed in Python so it reuses payments already loaded by summary.py.
        return sum((p.amount for p in self.payments.all() if not p.is_voided), Decimal("0"))

    @property
    def balance(self):
        return self.price_agreed - self.amount_paid

    def payment_flag(self, on=None):
        return status.payment_flag(self.balance, self.start_date, on or today(), settings.GRACE_DAYS)


# ---------------------------------------------------------------------------
class Payment(TimeStamped):
    # The gym takes cash and GCash only (owner, 2026-11-27).
    CASH, GCASH = "cash", "gcash"
    METHOD_CHOICES = [(CASH, "Cash"), (GCASH, "GCash")]

    # A payment is for a member's membership, OR a walk-in day pass (name only).
    membership = models.ForeignKey(
        Membership, on_delete=models.PROTECT, null=True, blank=True, related_name="payments"
    )
    walk_in_name = models.CharField(
        max_length=120, blank=True, help_text="Walk-in day pass only. Valid on the day paid."
    )
    walk_in_plan = models.ForeignKey(
        Plan, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        help_text="Walk-in only: which day pass (adult or student).",
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


# ---------------------------------------------------------------------------
class CheckIn(models.Model):
    """One visit. Logged even when the membership has expired, so the owner sees it."""

    CARD, TYPED = "card", "typed"
    HOW_CHOICES = [(CARD, "Card"), (TYPED, "Typed")]

    member = models.ForeignKey(Member, on_delete=models.PROTECT, related_name="check_ins")
    at = models.DateTimeField(default=timezone.now, db_index=True)
    by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, editable=False,
                           related_name="+", help_text="Staff signed in at the desk.")
    how = models.CharField(max_length=5, choices=HOW_CHOICES, default=TYPED)
    status_then = models.CharField(max_length=10, blank=True, help_text="Member's status at check-in.")

    class Meta:
        ordering = ["-at"]

    def __str__(self):
        return f"{self.member.full_name} {self.at:%d %b %H:%M}"


# ---------------------------------------------------------------------------
class SignUp(TimeStamped):
    """
    Details a member typed in themselves (sign-up mode on the desk phone).
    Nothing here is trusted until staff check it and turn it into a Member.
    """

    PENDING, DONE, DISMISSED = "pending", "done", "dismissed"
    STATUS_CHOICES = [(PENDING, "Waiting for staff"), (DONE, "Done"), (DISMISSED, "Dismissed")]

    full_name = models.CharField(max_length=120)
    nickname = models.CharField(max_length=60, blank=True)
    phone = models.CharField(max_length=20)
    birth_date = models.DateField(null=True, blank=True)
    emergency_contact_name = models.CharField(max_length=120, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    says_existing = models.BooleanField(default=False, help_text="They said they are already a member (notebook).")
    consent_given_on = models.DateField(default=today)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    member = models.ForeignKey(Member, on_delete=models.PROTECT, null=True, blank=True, related_name="sign_ups")
    entered_on = models.ForeignKey(  # whose desk phone it was typed on
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, editable=False, related_name="+"
    )
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, editable=False, related_name="+"
    )
    handled_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.get_status_display()})"

    def member_fields(self):
        """The typed details, ready to create or update a Member."""
        return {
            "full_name": self.full_name, "nickname": self.nickname, "phone": self.phone,
            "birth_date": self.birth_date, "emergency_contact_name": self.emergency_contact_name,
            "emergency_contact_phone": self.emergency_contact_phone, "consent_given_on": self.consent_given_on,
        }

    def close(self, status, user, member=None):
        self.status = status
        self.member = member
        self.handled_by = user
        self.handled_at = timezone.now()
        self.save()
