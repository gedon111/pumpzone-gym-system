"""
Forms for the desk screens. Each form checks the input; the view then
passes the clean values to services.py.

Phone-friendly widgets: type=tel opens the number pad, type=date opens
the date picker, inputmode=decimal opens the number keyboard for money.
"""

from django import forms
from django.utils import timezone

from .models import Member, Membership, Payment, Plan
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
        fields = ["full_name", "nickname", "phone", "birth_date", "emergency_contact_name", "emergency_contact_phone", "notes"]
        widgets = {"phone": PHONE, "emergency_contact_phone": PHONE, "birth_date": DATE,
                   "notes": forms.Textarea(attrs={"rows": 3})}


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


class WalkInForm(forms.Form):
    """Day pass for someone who is not a member. Valid on the day paid."""

    walk_in_name = forms.CharField(label="Name", max_length=120)
    amount = forms.DecimalField(min_value=0.01, widget=MONEY)
    method = forms.ChoiceField(widget=forms.RadioSelect, choices=Payment.METHOD_CHOICES, initial=Payment.CASH)
    reference_no = forms.CharField(label="GCash reference no.", required=False, max_length=40,
                                   widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "off"}))

    def clean(self):
        data = super().clean()
        if data.get("method") == Payment.GCASH and not data.get("reference_no", "").strip():
            self.add_error("reference_no", "GCash payments need the reference number.")
        return data
