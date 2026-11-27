"""The demo seed gives the same mix of statuses as the mockup."""

from collections import Counter
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from gym import status
from gym.models import Member, Plan


@override_settings(DEBUG=True)
class SeedTests(TestCase):
    def test_seed_makes_mockup_mix(self):
        call_command("seed_demo", stdout=StringIO())
        counts = Counter(m.expiry_status() for m in Member.objects.all())
        self.assertEqual(counts[status.ACTIVE], 186)
        self.assertEqual(counts[status.EXPIRING], 14)
        self.assertEqual(counts[status.EXPIRED], 23)
        self.assertTrue(all(m.phone.startswith("0900 000") for m in Member.objects.all()))

    def test_seed_uses_the_gym_price_list(self):
        call_command("seed_demo", stdout=StringIO())
        prices = {p.name: int(p.price) for p in Plan.objects.all()}
        self.assertEqual(prices, {"Monthly": 900, "15 Days": 450, "Day Pass": 100,
                                  "Student Monthly": 650, "Student 15 Days": 400, "Student Day Pass": 70})
        # Every 15-day membership really lasts 15 days (start day counts as day 1).
        for m in Member.objects.filter(memberships__plan__name__endswith="15 Days").distinct():
            for ms in m.memberships.filter(plan__length=15):
                self.assertEqual((ms.end_date - ms.start_date).days, 14)
