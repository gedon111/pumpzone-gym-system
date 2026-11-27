"""Member self sign-up on the desk phone, and the staff check afterwards."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from gym import status
from gym.models import Member, Payment, Plan, SignUp
from gym.views.dashboard import collected_today

PASSWORD = "not-a-real-pass-1"


class SignUpModeTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.monthly = Plan.objects.create(name="Monthly", price=Decimal("900"))
        self.lea = User.objects.create_user("lea", first_name="Lea", password=PASSWORD)
        self.client.force_login(self.lea)

    def start(self):
        return self.client.post("/join/start/")

    def join(self, **extra):
        data = {"full_name": "Jessa Villanueva", "nickname": "Jess", "phone": "0900 000 2222",
                "says_existing": "no", "consent": "on"}
        data.update(extra)
        return self.client.post("/join/", data)

    # ---- the lock -----------------------------------------------------------
    def test_sign_up_mode_blocks_every_other_page(self):
        self.assertRedirects(self.start(), "/join/")
        for url in ["/", "/members/", "/payments/", "/signups/", "/admin/", "/members/add/"]:
            self.assertRedirects(self.client.get(url), "/join/", msg_prefix=url, fetch_redirect_response=False)

    def test_unlock_needs_a_real_staff_password(self):
        self.start()
        r = self.client.post("/join/unlock/", {"username": "lea", "password": "wrong"})
        self.assertContains(r, "Wrong username or password")
        self.assertRedirects(self.client.get("/members/"), "/join/")
        r = self.client.post("/join/unlock/", {"username": "lea", "password": PASSWORD})
        self.assertRedirects(r, "/signups/")
        self.assertEqual(self.client.get("/members/").status_code, 200)

    def test_unlock_pauses_after_five_wrong_tries(self):
        self.start()
        for _ in range(5):
            self.client.post("/join/unlock/", {"username": "lea", "password": "wrong"})
        r = self.client.post("/join/unlock/", {"username": "lea", "password": PASSWORD})
        self.assertContains(r, "Too many wrong tries")
        self.assertRedirects(self.client.get("/members/"), "/join/")

    def test_the_staff_member_who_unlocks_becomes_the_user(self):
        User.objects.create_user("rico", first_name="Rico", password=PASSWORD)
        self.start()
        self.client.post("/join/unlock/", {"username": "rico", "password": PASSWORD})
        self.assertEqual(self.client.get("/signups/").context["user"].username, "rico")

    # ---- the member's form --------------------------------------------------
    def test_join_saves_a_pending_sign_up_and_reveals_nothing(self):
        Member.objects.create(full_name="Someone Else", phone="0900 000 2222")  # same number on file
        self.start()
        r = self.join()
        self.assertRedirects(r, "/join/done/")
        sign_up = SignUp.objects.get()
        self.assertEqual((sign_up.status, sign_up.entered_on, sign_up.consent_given_on),
                         (SignUp.PENDING, self.lea, self.today))
        self.assertNotContains(self.client.get("/join/done/"), "Someone Else")

    def test_join_needs_consent_and_a_full_number(self):
        self.start()
        self.assertContains(self.join(consent=""), "This field is required")
        self.assertContains(self.join(phone="0900"), "full mobile number")
        self.assertFalse(SignUp.objects.exists())


class StaffCheckTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.monthly = Plan.objects.create(name="Monthly", price=Decimal("900"))
        self.lea = User.objects.create_user("lea", first_name="Lea", password=PASSWORD)
        self.client.force_login(self.lea)
        self.sign_up = SignUp.objects.create(full_name="Jessa Villanueva", nickname="Jess", phone="0900 000 2222",
                                             emergency_contact_name="Mama Villanueva", says_existing=True)

    def test_review_finds_a_member_with_the_same_phone_whatever_the_spacing(self):
        same = Member.objects.create(full_name="Jessa V.", phone="09000002222")
        r = self.client.get(f"/signups/{self.sign_up.pk}/")
        self.assertEqual([m["member"] for m in r.context["matches"]], [same])
        self.assertEqual(r.context["matches"][0]["why"], "same phone")

    def test_dashboard_and_nav_show_pending_count(self):
        r = self.client.get("/")
        self.assertEqual(r.context["pending_signups"], 1)
        self.assertContains(r, "1 new sign-up")

    def test_carry_over_creates_a_paid_past_period_and_leaves_today_alone(self):
        start = self.today - timedelta(days=10)
        r = self.client.post(f"/signups/{self.sign_up.pk}/carry-over/", {
            "plan": self.monthly.pk, "start_date": start.isoformat(), "amount_paid": "900", "method": "cash"})
        member = Member.objects.get(full_name="Jessa Villanueva")
        self.assertRedirects(r, f"/members/{member.pk}/")
        self.assertEqual(member.expiry_status(), status.ACTIVE)
        self.assertEqual(member.balance, Decimal("0"))
        self.assertEqual(member.emergency_contact_name, "Mama Villanueva")
        self.assertEqual(member.consent_given_on, self.sign_up.consent_given_on)
        payment = Payment.objects.get()
        self.assertEqual((payment.reference_no, payment.received_by, timezone.localdate(payment.paid_on)),
                         ("from notebook", None, start))
        self.assertEqual(collected_today(self.today)["total"], Decimal("0"))
        self.sign_up.refresh_from_db()
        self.assertEqual((self.sign_up.status, self.sign_up.member, self.sign_up.handled_by),
                         (SignUp.DONE, member, self.lea))

    def test_carry_over_refuses_a_start_date_of_today(self):
        r = self.client.post(f"/signups/{self.sign_up.pk}/carry-over/", {
            "plan": self.monthly.pk, "start_date": self.today.isoformat(), "amount_paid": "900", "method": "cash"})
        self.assertContains(r, "use New member")
        self.assertFalse(Member.objects.exists())

    def test_new_member_form_is_filled_in_and_closes_the_sign_up(self):
        url = f"/members/add/?signup={self.sign_up.pk}"
        form = self.client.get(url).context["form"]
        self.assertEqual((form.initial["full_name"], form.initial["consent"]), ("Jessa Villanueva", True))
        self.client.post(url, {"full_name": "Jessa Villanueva", "nickname": "Jess", "phone": "0900 000 2222",
                               "plan": self.monthly.pk, "start_date": self.today.isoformat(), "pay": "full",
                               "method": "cash", "consent": "on"})
        member = Member.objects.get()
        self.assertEqual(member.emergency_contact_name, "Mama Villanueva")
        self.sign_up.refresh_from_db()
        self.assertEqual((self.sign_up.status, self.sign_up.member), (SignUp.DONE, member))

    def test_link_updates_the_existing_member_without_blanking_fields(self):
        member = Member.objects.create(full_name="Jessa V.", phone="0900 000 2222", birth_date=self.today - timedelta(days=9000))
        self.client.post(f"/signups/{self.sign_up.pk}/link/{member.pk}/")
        member.refresh_from_db()
        self.assertEqual((member.full_name, member.nickname), ("Jessa Villanueva", "Jess"))
        self.assertIsNotNone(member.birth_date)  # sign-up left it blank, so it was kept
        self.assertEqual(Member.objects.count(), 1)

    def test_dismiss_keeps_the_record(self):
        self.client.post(f"/signups/{self.sign_up.pk}/dismiss/")
        self.sign_up.refresh_from_db()
        self.assertEqual((self.sign_up.status, self.sign_up.handled_by), (SignUp.DISMISSED, self.lea))
        # A handled sign-up can't be used twice.
        r = self.client.post(f"/signups/{self.sign_up.pk}/dismiss/")
        self.assertEqual(r.status_code, 404)
