"""Front desk screens. Login is enforced for all of them by LoginRequiredMiddleware."""

from django.shortcuts import render


def dashboard(request):
    """Home screen. Placeholder until Step 4 builds the real dashboard."""
    return render(request, "gym/dashboard.html")
