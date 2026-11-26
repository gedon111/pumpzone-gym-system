"""Payment screens."""

from django.shortcuts import render


def payment_list(request):
    """Placeholder until Step 5."""
    return render(request, "gym/placeholder.html", {"title": "Payments", "step": 5})
