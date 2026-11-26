"""Values every template can use."""

from django.conf import settings
from django.utils import timezone


def pumpzone(request):
    # Shows the "Sample data" badge while running locally with DEBUG on.
    return {
        "settings_debug": settings.DEBUG,
        # Today as YYYYMMDD, so tables can show just the time for today's rows.
        "now_ymd": timezone.localdate().strftime("%Y%m%d"),
    }
