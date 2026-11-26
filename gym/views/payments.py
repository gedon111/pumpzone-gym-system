"""Payment screens."""

from django.shortcuts import render


def payment_list(request):
    """Placeholder until Step 5."""
    return render(request, "gym/placeholder.html", {"title": "Payments", "step": 5})


def payment_add(request, pk):
    """Placeholder until Step 5."""
    return render(request, "gym/placeholder.html", {"title": "Log payment", "step": 5})
