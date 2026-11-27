"""The GitHub Pages snapshot: fake data only, relative links, nothing kept in the database."""

import re
import shutil
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from gym.models import CheckIn, Member


@override_settings(DEBUG=True)
class StaticExportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=StringIO())

    def setUp(self):
        self.out = Path(tempfile.mkdtemp()) / "_site"
        self.addCleanup(shutil.rmtree, self.out.parent, ignore_errors=True)

    def test_exports_every_screen_with_relative_links_and_keeps_nothing(self):
        visits = CheckIn.objects.count()
        call_command("export_static", str(self.out), stdout=StringIO())
        self.assertEqual(CheckIn.objects.count(), visits)  # demo check-ins were rolled back

        for page in ["index.html", "show-expiring.html", "members/index.html", "payments/index.html",
                     "checkin/index.html", "signups/index.html", "join/index.html", "demo-only/index.html",
                     "static/css/pumpzone.css", ".nojekyll"]:
            self.assertTrue((self.out / page).exists(), page)
        member = Member.objects.first()
        self.assertTrue((self.out / f"members/{member.pk}/renew/index.html").exists())

        html = (self.out / "members/index.html").read_text(encoding="utf-8")
        self.assertIn("Online demo", html)
        self.assertIn('href="../static/css/pumpzone.css"', html)
        self.assertFalse(re.search(r'(href|src|action)="/', html), "a link still points at the server")
        self.assertIn('href="../demo-only/index.html"', html)  # admin link: not in the demo

    def test_refuses_a_database_with_real_looking_numbers(self):
        Member.objects.create(full_name="Real Person", phone="0917 123 4567")
        with self.assertRaisesMessage(CommandError, "not fake demo numbers"):
            call_command("export_static", str(self.out), stdout=StringIO())

    @override_settings(DEBUG=False)
    def test_refuses_when_debug_is_off(self):
        with self.assertRaisesMessage(CommandError, "DEBUG is off"):
            call_command("export_static", str(self.out), stdout=StringIO())
