"""Home screen."""

from django.shortcuts import render


def dashboard(request):
    """Placeholder until Step 4 builds the real dashboard."""
    return render(request, "gym/placeholder.html", {"title": "Dashboard", "step": 4})
