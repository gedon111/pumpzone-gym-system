"""Values every template can use."""

from django.conf import settings
from django.utils import timezone

from . import kiosk
from .models import SignUp


def pumpzone(request):
    user = getattr(request, "user", None)
    signed_in = bool(user and user.is_authenticated) and not kiosk.is_on(request)
    return {
        # Sign-ups waiting for staff (the number on the "Sign-ups" tab).
        "pending_signups": SignUp.objects.filter(status=SignUp.PENDING).count() if signed_in else 0,
        # Shows the "Sample data" badge while running locally with DEBUG on.
        "settings_debug": settings.DEBUG,
        # Today as YYYYMMDD, so tables can show just the time for today's rows.
        "now_ymd": timezone.localdate().strftime("%Y%m%d"),
    }
