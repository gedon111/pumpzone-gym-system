"""Member screens."""

from django.shortcuts import render


def member_list(request):
    """Placeholder until Step 5."""
    return render(request, "gym/placeholder.html", {"title": "Members", "step": 5})


def member_detail(request, pk):
    """Placeholder until Step 5."""
    return render(request, "gym/placeholder.html", {"title": "Member", "step": 5})


def member_renew(request, pk):
    """Placeholder until Step 5."""
    return render(request, "gym/placeholder.html", {"title": "Renew", "step": 5})
