"""
Small helpers used inside templates. Load with {% load pumpzone %}.

    {{ amount|peso }}         -> ₱1,000
    {{ "Marco Cruz"|initials }} -> MC
    {% icon "refresh" %}       -> an inline SVG line icon (same set as the mockup)
"""

from decimal import Decimal

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def peso(value):
    """Format money as pesos. Whole pesos drop the .00."""
    if value in (None, ""):
        return ""
    value = Decimal(value)
    text = f"{value:,.0f}" if value == value.to_integral() else f"{value:,.2f}"
    return f"₱{text}"


@register.filter
def initials(name):
    parts = [p for p in str(name).split() if p]
    return "".join(p[0] for p in parts[:2]).upper()


# Line icons (Lucide style, as used in the mockup). Each value is the SVG inside.
ICONS = {
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "refresh": '<path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>',
    "plus": '<path d="M5 12h14"/><path d="M12 5v14"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "x-circle": '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "cash": '<rect width="20" height="12" x="2" y="6" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/>',
    "message": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "arrow-left": '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
}


@register.simple_tag
def icon(name, size=18):
    return format_html(
        '<svg aria-hidden="true" width="{}" height="{}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">{}</svg>',
        size, size, mark_safe(ICONS[name]),
    )
