"""
Forms for the desk screens. Each form checks the input; the view then
passes the clean values to services.py.

Phone-friendly widgets: type=tel opens the number pad, type=date opens
the date picker, inputmode=decimal opens the number keyboard for money.
"""

from django import forms
from django.utils import timezone

from .models import Member, Membership, Payment, Plan, SignUp, clean_card_uid
from .services import PAY_FULL, PAY_LATER, PAY_PARTIAL

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
MONEY = forms.NumberInput(attrs={"inputmode": "decimal", "step": "0.01", "min": "0"})
PHONE = forms.TextInput(attrs={"type": "tel", "inputmode": "tel", "autocomplete": "off"})


def active_plans():
    return Plan.objects.filter(is_active=True)


class PaymentChoiceForm(forms.Form):
    """'How are they paying?' Shared by Add member and Renew."""

    pay = forms.ChoiceField(
        label="Payment now", widget=forms.RadioSelect, initial=PAY_FULL,
        choices=[(PAY_FULL, "Paid in full"), (PAY_PARTIAL, "Part payment"), (PAY_LATER, "Pay later")],
    )
    amount = forms.DecimalField(label="Amount paid now", required=False, min_value=0, widget=MONEY,
                                help_text="Only for a part payment.")
    method = forms.ChoiceField(widget=forms.RadioSelect, choices=Payment.METHOD_CHOICES, initial=Payment.CASH)
    reference_no = forms.CharField(label="GCash reference no.", required=False, max_length=40,
                                   widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "off"}))

    def clean(self):
        data = super().clean()
        pay = data.get("pay")
        if pay == PAY_PARTIAL and not data.get("amount"):
            self.add_error("amount", "Type how much they paid now.")
        if pay != PAY_LATER and data.get("method") == Payment.GCASH and not data.get("reference_no", "").strip():
            self.add_error("reference_no", "GCash payments need the reference number.")
        return data

    def sale_values(self):
        d = self.cleaned_data
        return {"pay": d["pay"], "amount": d.get("amount"), "method": d["method"], "reference_no": d.get("reference_no", "")}


class PlanChoiceForm(forms.Form):
    """Plan, start date and (optional) discounted price."""

    plan = forms.ModelChoiceField(queryset=Plan.objects.none(), empty_label=None)
    start_date = forms.DateField(widget=DATE)
    price_agreed = forms.DecimalField(label="Price (if discounted)", required=False, min_value=0, widget=MONEY,
                                      help_text="Leave blank for the normal price. Your name is saved with any discount.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plan"].queryset = active_plans()
        self.fields["plan"].label_from_instance = lambda p: f"{p.name} · ₱{p.price:,.0f}"
        self.fields["start_date"].initial = timezone.localdate()


class AddMemberForm(PlanChoiceForm, PaymentChoiceForm):
    full_name = forms.CharField(max_length=120, widget=forms.TextInput(attrs={"autocomplete": "off", "autocapitalize": "words"}))
    nickname = forms.CharField(max_length=60, required=False, help_text="The name used in the logbook.")
    phone = forms.CharField(max_length=20, required=False, widget=PHONE, help_text="Needed for SMS reminders.")
    birth_date = forms.DateField(required=False, widget=DATE, help_text="Only used to show age.")
    consent = forms.BooleanField(
        label="Member agreed to the privacy notice (name and number are kept for membership and reminders only).",
    )

    field_order = ["full_name", "nickname", "phone", "birth_date", "plan", "start_date", "price_agreed",
                   "pay", "amount", "method", "reference_no", "consent"]

    def clean_phone(self):
        phone = " ".join(self.cleaned_data["phone"].split())
        if phone:
            existing = Member.objects.filter(phone=phone).first()
            if existing:
                raise forms.ValidationError(f"Already on file: {existing.full_name} ({existing.member_code}). Renew them instead.")
        return phone

    def member_fields(self):
        d = self.cleaned_data
        today = timezone.localdate()
        return {"full_name": d["full_name"].strip(), "nickname": d["nickname"].strip(), "phone": d["phone"],
                "birth_date": d["birth_date"], "joined_on": d["start_date"] or today, "consent_given_on": today}

    def plan_values(self):
        d = self.cleaned_data
        return {"plan": d["plan"], "start_date": d["start_date"], "price_agreed": d["price_agreed"]}


class RenewForm(PlanChoiceForm, PaymentChoiceForm):
    field_order = ["plan", "start_date", "price_agreed", "pay", "amount", "method", "reference_no"]

    def plan_values(self):
        d = self.cleaned_data
        return {"plan": d["plan"], "start_date": d["start_date"], "price_agreed": d["price_agreed"]}


class EditMemberForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ["full_name", "nickname", "phone", "birth_date", "emergency_contact_name", "emergency_contact_phone",
                  "card_uid", "notes"]
        widgets = {"phone": PHONE, "emergency_contact_phone": PHONE, "birth_date": DATE,
                   "card_uid": forms.TextInput(attrs={"autocomplete": "off", "spellcheck": "false"}),
                   "notes": forms.Textarea(attrs={"rows": 3})}

    def clean_card_uid(self):
        # Tidy first, so "04 a1 b2" and "04A1B2" count as the same card.
        uid = clean_card_uid(self.cleaned_data.get("card_uid"))
        if uid and Member.objects.filter(card_uid=uid).exclude(pk=self.instance.pk).exists():
            other = Member.objects.get(card_uid=uid)
            raise forms.ValidationError(f"This card is already linked to {other.full_name} ({other.member_code}).")
        return uid


class PaymentForm(forms.Form):
    """Collect money against one of a member's memberships."""

    membership = forms.ModelChoiceField(queryset=Membership.objects.none(), empty_label=None, label="For")
    amount = forms.DecimalField(min_value=0.01, widget=MONEY)
    method = forms.ChoiceField(widget=forms.RadioSelect, choices=Payment.METHOD_CHOICES, initial=Payment.CASH)
    reference_no = forms.CharField(label="GCash reference no.", required=False, max_length=40,
                                   widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "off"}))

    def __init__(self, *args, member, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields["membership"]
        field.queryset = member.memberships.select_related("plan").order_by("-end_date")
        field.label_from_instance = lambda m: (
            f"{m.plan.name}, {m.start_date:%d %b} to {m.end_date:%d %b %Y} · owes ₱{m.balance:,.0f}"
        )

    def clean(self):
        data = super().clean()
        if data.get("method") == Payment.GCASH and not data.get("reference_no", "").strip():
            self.add_error("reference_no", "GCash payments need the reference number.")
        return data


def day_passes():
    """The 1-day plans: Day Pass and Student Day Pass."""
    return active_plans().filter(unit="day", length=1).order_by("-price")


class WalkInForm(forms.Form):
    """Day pass for someone who is not a member. Valid on the day paid."""

    walk_in_name = forms.CharField(label="Name", max_length=120)
    day_pass = forms.ModelChoiceField(label="Pass", queryset=Plan.objects.none(), empty_label=None,
                                      widget=forms.RadioSelect)
    amount = forms.DecimalField(required=False, min_value=0.01, widget=MONEY,
                                help_text="Leave blank for the pass price.")
    method = forms.ChoiceField(widget=forms.RadioSelect, choices=Payment.METHOD_CHOICES, initial=Payment.CASH)
    reference_no = forms.CharField(label="GCash reference no.", required=False, max_length=40,
                                   widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "off"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        passes = day_passes()
        field = self.fields["day_pass"]
        field.queryset = passes
        field.label_from_instance = lambda p: f"{p.name} · ₱{p.price:,.0f}"
        field.initial = passes.first()  # the adult pass (highest price)

    def clean(self):
        data = super().clean()
        if data.get("method") == Payment.GCASH and not data.get("reference_no", "").strip():
            self.add_error("reference_no", "GCash payments need the reference number.")
        if data.get("day_pass") and not data.get("amount"):
            data["amount"] = data["day_pass"].price  # blank = the pass price
        return data


# ---------------------------------------------------------------------------
# Sign-up mode (the member types on the desk phone) and the staff check.

PRIVACY_NOTICE = (
    "Pumpzone keeps your name, phone number and birth date only to run your membership "
    "and send you reminders. Only gym staff can see them. We never share or sell them. "
    "You can ask to see, correct or delete your details at the front desk."
)


class SignUpForm(forms.ModelForm):
    """What the member fills in themselves. Big, simple, nothing about other members."""

    says_existing = forms.TypedChoiceField(
        label="Are you already a member?", widget=forms.RadioSelect, coerce=lambda v: v == "yes", initial="no",
        choices=[("no", "No, I'm new"), ("yes", "Yes, I'm in the notebook")],
    )
    consent = forms.BooleanField(label="I agree to the privacy notice above.")

    class Meta:
        model = SignUp
        fields = ["full_name", "nickname", "phone", "birth_date", "emergency_contact_name", "emergency_contact_phone",
                  "says_existing"]
        labels = {"full_name": "Full name", "nickname": "Nickname (what we call you)", "phone": "Mobile number",
                  "emergency_contact_name": "Emergency contact name", "emergency_contact_phone": "Emergency contact number"}
        help_texts = {"phone": "For membership reminders only.", "birth_date": "Optional."}
        widgets = {"phone": PHONE, "emergency_contact_phone": PHONE, "birth_date": DATE,
                   "full_name": forms.TextInput(attrs={"autocomplete": "off", "autocapitalize": "words"}),
                   "nickname": forms.TextInput(attrs={"autocomplete": "off"})}

    def clean_phone(self):
        # Tidy the spacing only. Whether the number is already on file is
        # NEVER said here: that would let anyone check other people's numbers.
        phone = " ".join(self.cleaned_data["phone"].split())
        if len("".join(ch for ch in phone if ch.isdigit())) < 7:
            raise forms.ValidationError("Please type your full mobile number.")
        return phone


class UnlockForm(forms.Form):
    """A staff member ends sign-up mode with their own password."""

    username = forms.CharField(widget=forms.TextInput(attrs={"autocomplete": "off", "autocapitalize": "none"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "off"}))


class CarryOverForm(forms.Form):
    """A member already paid in the notebook: copy their current period in."""

    plan = forms.ModelChoiceField(queryset=Plan.objects.none(), empty_label=None)
    start_date = forms.DateField(label="Start date (from the notebook)", widget=DATE)
    end_date = forms.DateField(label="Last day", required=False, widget=DATE,
                               help_text="Only if the notebook says a different last day.")
    amount_paid = forms.DecimalField(label="Amount paid (from the notebook)", min_value=0, widget=MONEY,
                                     help_text="0 if they still owe the whole amount.")
    method = forms.ChoiceField(widget=forms.RadioSelect, choices=Payment.METHOD_CHOICES, initial=Payment.CASH)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plan"].queryset = active_plans()
        self.fields["plan"].label_from_instance = lambda p: f"{p.name} · ₱{p.price:,.0f}"

    def clean(self):
        data = super().clean()
        start, end = data.get("start_date"), data.get("end_date")
        if start and start >= timezone.localdate():
            self.add_error("start_date", "A notebook period started before today. If they pay today, "
                                         "use New member so the money counts in today's drawer.")
        if start and end and end < start:
            self.add_error("end_date", "The last day is before the start date.")
        return data
