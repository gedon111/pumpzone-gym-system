"""
Sign-up mode: the desk phone (or a tablet or laptop) is handed to a member
so they can type in their own details.

While it is on, every page except the sign-up pages sends the phone back to
the sign-up form. The member can't open the member list, payments or the
admin, even with the Back button or by typing an address.

    on:   staff tap "Member sign-up" (views/signups.py: kiosk_start)
    off:  a staff member types their username and password (join_unlock),
          or someone signs out

It sits after LoginRequiredMiddleware in settings.MIDDLEWARE, so the phone
must still be signed in to a staff account.
"""

from django.shortcuts import redirect

SESSION_KEY = "kiosk"
FAILED_KEY = "kiosk_failed"

# The only pages that open in sign-up mode (URL names from gym/urls.py and config/urls.py).
ALLOWED = {"join", "join_done", "join_unlock", "logout"}


def is_on(request):
    return bool(request.session.get(SESSION_KEY))


def turn_on(request):
    request.session[SESSION_KEY] = True
    request.session[FAILED_KEY] = 0


def turn_off(request):
    request.session.pop(SESSION_KEY, None)
    request.session.pop(FAILED_KEY, None)


class KioskLockMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not hasattr(request, "session") or not is_on(request):
            return None  # normal staff use
        match = request.resolver_match
        if match and match.view_name in ALLOWED:
            return None
        return redirect("join")
