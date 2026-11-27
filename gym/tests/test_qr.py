"""GCash QR: demo code by default, the gym's real image when the setting points to one."""

import os
import tempfile
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from gym import qr
from gym.models import Payment, Plan

# A 1x1 PNG, standing in for the owner's real QR image.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


class QrTests(TestCase):
    def test_demo_qr_by_default(self):
        html, is_demo = qr.gcash_qr()
        self.assertTrue(is_demo)
        self.assertIn("<svg", html)

    def test_real_image_when_setting_points_to_a_file(self):
        f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        f.write(TINY_PNG)
        f.close()
        self.addCleanup(os.remove, f.name)
        with override_settings(GCASH_QR_IMAGE=f.name):
            html, is_demo = qr.gcash_qr()
        self.assertFalse(is_demo)
        self.assertIn('src="data:image/png;base64,', html)

    @override_settings(GCASH_QR_IMAGE="C:/does/not/exist.png")
    def test_missing_file_falls_back_to_demo(self):
        self.assertTrue(qr.gcash_qr()[1])

    def test_payment_forms_show_the_panel_and_only_cash_or_gcash(self):
        Plan.objects.create(name="Day Pass", length=1, unit="day", price=Decimal("100"))
        self.client.force_login(User.objects.create_user("lea", password="not-a-real-pass-1"))
        for url in ["/members/add/", "/payments/walk-in/"]:
            r = self.client.get(url)
            self.assertContains(r, 'class="gcash-panel"')
            self.assertContains(r, "qr-stamp")
            self.assertNotContains(r, 'value="other"')
        self.assertEqual([k for k, _ in Payment.METHOD_CHOICES], ["cash", "gcash"])
