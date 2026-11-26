"""The demo seed gives the same mix of statuses as the mockup."""

from collections import Counter
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from gym import status
from gym.models import Member


@override_settings(DEBUG=True)
class SeedTests(TestCase):
    def test_seed_makes_mockup_mix(self):
        call_command("seed_demo", stdout=StringIO())
        counts = Counter(m.expiry_status() for m in Member.objects.all())
        self.assertEqual(counts[status.ACTIVE], 186)
        self.assertEqual(counts[status.EXPIRING], 14)
        self.assertEqual(counts[status.EXPIRED], 23)
        self.assertTrue(all(m.phone.startswith("0900 000") for m in Member.objects.all()))
