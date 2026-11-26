"""Member screens."""

from django.shortcuts import render


def member_list(request):
    """Placeholder until Step 5."""
    return render(request, "gym/placeholder.html", {"title": "Members", "step": 5})
