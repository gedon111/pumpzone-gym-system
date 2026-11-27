"""
Owner back office (Django admin at /admin/).

Rules enforced here:
- Payments can never be deleted, and their money fields cannot be edited
  after saving. A mistake is voided (owner only) and logged again.
- Who sold a membership / received a payment is filled in automatically.
- Django admin also keeps its own history of every change and who made it.
"""

from django.contrib import admin

from .models import Member, Membership, Payment, Plan
from .roles import is_owner

LOCKED_PAYMENT_FIELDS = ("membership", "walk_in_name", "walk_in_plan", "amount", "method", "reference_no", "paid_on")


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "length", "unit", "price", "is_active")
    list_filter = ("is_active", "unit")


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    fields = ("plan", "start_date", "end_date", "price_agreed", "list_price", "created_by")
    readonly_fields = ("list_price", "created_by")
    show_change_link = True


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("member_code", "full_name", "nickname", "phone", "joined_on", "is_archived")
    search_fields = ("member_code", "full_name", "nickname", "phone")
    list_filter = ("is_archived", "joined_on")
    readonly_fields = ("member_code",)
    inlines = [MembershipInline]

    def save_formset(self, request, form, formset, change):
        # Record which staff member created each new membership.
        for membership in formset.save(commit=False):
            if not membership.pk:
                membership.created_by = request.user
            membership.save()
        formset.save_m2m()


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ("paid_on", "amount", "method", "reference_no", "received_by", "is_voided")
    readonly_fields = fields  # add payments from the Payment page, not here
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("member", "plan", "start_date", "end_date", "list_price", "price_agreed", "created_by")
    search_fields = ("member__full_name", "member__nickname", "member__member_code")
    list_filter = ("plan",)
    readonly_fields = ("list_price", "created_by")
    autocomplete_fields = ("member",)
    inlines = [PaymentInline]

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("paid_on", "__str__", "method", "reference_no", "received_by", "is_voided")
    list_filter = ("method", "is_voided", "paid_on")
    search_fields = ("reference_no", "walk_in_name", "membership__member__full_name")
    autocomplete_fields = ("membership",)

    def get_readonly_fields(self, request, obj=None):
        fields = ["received_by"]
        if obj:  # already saved: money details are locked for everyone
            fields += LOCKED_PAYMENT_FIELDS
        if not is_owner(request.user):
            fields += ["is_voided", "void_reason"]
        return fields

    def has_delete_permission(self, request, obj=None):
        return False  # void instead

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.received_by = request.user
        super().save_model(request, obj, form, change)
