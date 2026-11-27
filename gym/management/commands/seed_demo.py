"""
Fill the database with FAKE demo data for the pitch.

    python manage.py seed_demo          # first time
    python manage.py seed_demo --reset  # wipe gym data and seed again

Everything it makes is fake: phone numbers start with 0900 000, and
every member's notes say "Sample member". It refuses to run when
DEBUG is off, so it cannot wipe a live gym by accident.
"""

import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from gym import dates
from gym import checkin
from gym.models import CheckIn, Member, Membership, Payment, Plan, SignUp
from gym.roles import OWNER_GROUP, STAFF_GROUP

DEMO_PASSWORD = "pumpzone-demo"  # demo accounts only, local prototype
DEMO_USERS = [  # username, first name, role
    ("owner", "Owner", OWNER_GROUP),
    ("lea", "Lea", STAFF_GROUP),
    ("rico", "Rico", STAFF_GROUP),
]

# The gym's price list, as told by the owner (2026-11-27).
# "30 days" plans use the calendar-month rule: 25 Nov to 25 Dec.
PLANS = [  # name, length, unit, price, how often it is picked
    ("Monthly", 1, dates.MONTH, "900", 55),
    ("15 Days", 15, dates.DAY, "450", 10),
    ("Day Pass", 1, dates.DAY, "100", 0),            # walk-ins only
    ("Student Monthly", 1, dates.MONTH, "650", 28),
    ("Student 15 Days", 15, dates.DAY, "400", 7),
    ("Student Day Pass", 1, dates.DAY, "70", 0),     # walk-ins only
]

FIRST = ("Marco Kristine Jessa Paolo Jun Bea Ramon Angelica Ana Carlo Jerome Mae Joy Mark Joan "
         "Ryan Liza Jomar Nikki Arvin Camille Dennis Grace Kevin Rhea Allan Trisha Miguel Sheila "
         "Ivy Jayson Kaye Nestor Lovely Bryan Faith Rommel Carla Patrick Mylene").split()
LAST = ("Dela Cruz|Bautista|Villanueva|Reyes|Garcia|Navarro|Santos|Mendoza|Lim|Tan|Cruz|Ocampo|"
        "Ramos|Aquino|Castillo|Flores|Gonzales|Torres|Rivera|Aguilar|Pascual|Domingo|Salazar|"
        "Manalo|Soriano").split("|")

# How many members of each kind (matches the mockup).
COUNT_ACTIVE, COUNT_EXPIRING, COUNT_EXPIRED = 186, 14, 23
COUNT_UNPAID = 6
COUNT_PAID_TODAY = 12  # renewals that happened today, for "Collected today"
CARDS = 30            # members with a demo card number DEMO0001 ... DEMO0030
CHECK_INS_TODAY = 60  # visits so far today (a few by expired members, as happens)
SIGN_UPS_WAITING = [  # (full name, nickname, says already a member)
    ("Sample Signup Rosa", "Rose", False),
    ("Sample Signup Elmer", "", True),
]
WALK_INS_TODAY = [("Bong", "Day Pass"), ("Tess", "Day Pass"), ("Dodong", "Student Day Pass")]


def start_for_end(plan, end):
    """The start date that makes this plan end on `end`."""
    if plan.unit == dates.MONTH:
        return dates.add_months(end, -plan.length)
    return end - timedelta(days=plan.length - 1)


class Command(BaseCommand):
    help = "Fill the database with fake demo members, payments and staff accounts."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete all gym data first.")

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Refusing to seed: DEBUG is off, this looks like a live server.")
        if Member.objects.exists() and not options["reset"]:
            raise CommandError("There are already members. Use --reset to wipe them and seed again.")

        self.rng = random.Random(42)  # same "random" data every time
        self.today = timezone.localdate()

        with transaction.atomic():  # all or nothing
            if options["reset"]:
                self.wipe()
            self.make_roles_and_users()
            self.make_plans()
            self.make_members()
            self.make_walk_ins()
            self.make_cards_and_check_ins()
            self.make_sign_ups()

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {Member.objects.count()} members, {Membership.objects.count()} memberships, "
            f"{Payment.objects.count()} payments."
        ))
        self.stdout.write("Demo sign-ins: owner, lea, rico. Password: see README (demo only).")

    # ------------------------------------------------------------------
    def wipe(self):
        # Order matters: payments point at memberships, memberships at members.
        CheckIn.objects.all().delete()
        SignUp.objects.all().delete()
        Payment.objects.all().delete()
        Membership.objects.all().delete()
        Member.objects.all().delete()
        Plan.objects.all().delete()

    def make_roles_and_users(self):
        gym_perms = Permission.objects.filter(content_type__app_label="gym")
        owner_group, _ = Group.objects.get_or_create(name=OWNER_GROUP)
        owner_group.permissions.set(gym_perms)
        staff_group, _ = Group.objects.get_or_create(name=STAFF_GROUP)
        staff_group.permissions.set(gym_perms.filter(
            codename__in=["view_member", "add_member", "change_member",
                          "view_membership", "add_membership", "change_membership",
                          "view_payment", "add_payment", "view_plan"]
        ))

        self.staff = []
        for username, first_name, role in DEMO_USERS:
            user, _ = User.objects.get_or_create(username=username)
            user.first_name = first_name
            user.is_staff = role == OWNER_GROUP  # only the owner opens /admin/
            user.is_superuser = role == OWNER_GROUP
            user.set_password(DEMO_PASSWORD)
            user.save()
            user.groups.set([owner_group if role == OWNER_GROUP else staff_group])
            if role == STAFF_GROUP:
                self.staff.append(user)

    def make_plans(self):
        self.plans = []
        for name, length, unit, price, weight in PLANS:
            plan = Plan.objects.create(name=name, length=length, unit=unit, price=Decimal(price))
            if weight:
                self.plans.append((plan, weight))

    # ------------------------------------------------------------------
    def make_members(self):
        kinds = (["active"] * COUNT_ACTIVE + ["expiring"] * COUNT_EXPIRING + ["expired"] * COUNT_EXPIRED)
        self.rng.shuffle(kinds)
        active_indexes = [i for i, k in enumerate(kinds) if k == "active"]
        paid_today = set(self.rng.sample(active_indexes, COUNT_PAID_TODAY))
        unpaid = set(self.rng.sample([i for i in active_indexes if i not in paid_today], COUNT_UNPAID))

        for i, kind in enumerate(kinds):
            plan = self.pick_plan()
            start = self.today if i in paid_today else self.start_for(kind, plan)

            # About 40% have an earlier, fully paid period before this one.
            history_start = None
            if self.rng.random() < 0.4:
                history_start = start_for_end(plan, start - timedelta(days=1))

            member = Member.objects.create(
                full_name=f"{self.rng.choice(FIRST)} {self.rng.choice(LAST)}",
                nickname=self.rng.choice(["", "", self.rng.choice(FIRST)]),
                phone=f"0900 000 {i + 1:04d}",  # clearly fake numbers
                birth_date=self.fake_birth_date(),
                joined_on=history_start or start,
                consent_given_on=history_start or start,
                notes="Sample member (fake data).",
            )
            if history_start:
                old = self.sell(member, plan, history_start)
                self.pay(old, old.price_agreed, history_start)

            current = self.sell(member, plan, start)
            if i in unpaid:
                # Owes money: paid part of it, or nothing.
                part = self.rng.choice([Decimal("0"), Decimal("300")])
                if part:
                    self.pay(current, part, start)
            else:
                self.pay(current, current.price_agreed, start)

    def pick_plan(self):
        plans, weights = zip(*self.plans)
        return self.rng.choices(plans, weights=weights)[0]

    def start_for(self, kind, plan):
        """Pick a start date that gives the wanted status today."""
        if kind == "expiring":
            days_left = self.rng.randint(0, 7)
        elif kind == "expired":
            days_left = -self.rng.randint(1, 30)
        elif plan.unit == dates.DAY:
            days_left = self.rng.randint(8, plan.length - 1)  # a 15-day plan has at most 14 days left
        else:
            days_left = self.rng.randint(8, 28 * plan.length)
        return start_for_end(plan, self.today + timedelta(days=days_left))

    def fake_birth_date(self):
        if self.rng.random() < 0.5:
            return None
        return self.today - timedelta(days=self.rng.randint(16 * 365, 55 * 365))

    def sell(self, member, plan, start):
        discount = Decimal("100") if self.rng.random() < 0.05 else Decimal("0")
        return Membership.objects.create(
            member=member, plan=plan, start_date=start,
            price_agreed=plan.price - discount, created_by=self.rng.choice(self.staff),
        )

    def pay(self, membership, amount, on_date):
        method = self.rng.choice([Payment.CASH, Payment.CASH, Payment.GCASH])
        Payment.objects.create(
            membership=membership, amount=amount, method=method,
            reference_no=self.fake_gcash_ref() if method == Payment.GCASH else "",
            paid_on=self.time_on(on_date), received_by=self.rng.choice(self.staff),
        )

    def make_walk_ins(self):
        for name, pass_name in WALK_INS_TODAY:
            day_pass = Plan.objects.get(name=pass_name)
            Payment.objects.create(
                walk_in_name=name, walk_in_plan=day_pass, amount=day_pass.price, method=Payment.CASH,
                paid_on=self.time_on(self.today), received_by=self.rng.choice(self.staff),
            )

    def make_cards_and_check_ins(self):
        members = list(Member.objects.order_by("pk"))
        for n, member in enumerate(self.rng.sample(members, CARDS), start=1):
            member.card_uid = f"DEMO{n:04d}"  # a real card number looks like 04A1B2C3D4E5F6
            member.save(update_fields=["card_uid"])

        carded = {m.pk for m in Member.objects.exclude(card_uid=None)}
        for member in self.rng.sample(members, CHECK_INS_TODAY):
            visit = checkin.log(member, self.rng.choice(self.staff),
                                CheckIn.CARD if member.pk in carded else CheckIn.TYPED)
            visit.at = self.time_on(self.today)
            visit.save(update_fields=["at"])

    def make_sign_ups(self):
        for n, (name, nickname, existing) in enumerate(SIGN_UPS_WAITING, start=1):
            SignUp.objects.create(full_name=name, nickname=nickname, phone=f"0900 000 98{n:02d}",
                                  says_existing=existing, entered_on=self.staff[0])

    def time_on(self, day):
        """A gym-hours time on that day, never later than right now."""
        moment = timezone.make_aware(datetime.combine(day, time(self.rng.randint(6, 20), self.rng.randint(0, 59))))
        return min(moment, timezone.now())

    def fake_gcash_ref(self):
        return f"{self.rng.randint(1000, 9999)} {self.rng.randint(100, 999)} {self.rng.randint(100, 999)}"
