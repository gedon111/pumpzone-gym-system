"""
The GCash / QR Ph code shown when a member pays by GCash.

Prototype: a DEMO QR. It holds plain text, so scanning it shows
"PUMPZONE DEMO - NOT A REAL GCASH ACCOUNT" and nobody can send money to it.

Going live: in the GCash app, open Receive > QR, save the image, and set
PUMPZONE_GCASH_QR_IMAGE to that file's path. That image is shown instead.
The member scans it, pays, and staff type the reference number from the
member's confirmation screen, the same as today.

A QR that fills in the amount by itself (a "dynamic" QR Ph) needs a
merchant account with a payment provider, which costs money, so it is
not part of the prototype.
"""

import base64
import mimetypes
from functools import lru_cache
from pathlib import Path

import segno
from django.conf import settings
from django.utils.html import format_html
from django.utils.safestring import mark_safe

DEMO_TEXT = "PUMPZONE DEMO - NOT A REAL GCASH ACCOUNT"


@lru_cache(maxsize=1)
def demo_qr_svg():
    """The demo QR as inline SVG (made once, then reused)."""
    qr = segno.make(DEMO_TEXT, error="m")
    return qr.svg_inline(dark="#0d0c10", light="#f1eef4", border=2, omitsize=True,
                         svgclass="qr-code", title="Demo QR code, cannot receive money")


def real_qr_img(path):
    """The owner's real QR image, embedded in the page (no file serving needed)."""
    file = Path(path)
    mime = mimetypes.guess_type(file.name)[0] or "image/png"
    data = base64.b64encode(file.read_bytes()).decode("ascii")
    return format_html('<img class="qr-code" src="data:{};base64,{}" alt="Pumpzone GCash QR code">', mime, data)


def gcash_qr():
    """HTML for the QR, and whether it is the demo one."""
    path = settings.GCASH_QR_IMAGE
    if path and Path(path).is_file():
        return real_qr_img(path), False
    return mark_safe(demo_qr_svg()), True
