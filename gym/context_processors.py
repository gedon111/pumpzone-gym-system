"""Values every template can use."""

from django.conf import settings


def pumpzone(request):
    # Shows the "Sample data" badge while running locally with DEBUG on.
    return {"settings_debug": settings.DEBUG}
