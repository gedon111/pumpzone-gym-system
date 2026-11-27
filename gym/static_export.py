"""
Save the app's screens as plain HTML files, for the online demo on GitHub
Pages. GitHub Pages can only host fixed files, so it can't run Django or
a database: this is a read-only snapshot of the real app with FAKE data.

How it works:
1. Sign in as a demo staff member with Django's test client (no server).
2. Open every screen worth showing (PAGES below) and keep the HTML.
3. Rewrite every link so it points at the saved file, relative to the
   page, so the site works under github.io/<repo>/ and when opened from disk.
   Links to pages that weren't saved go to a short "demo only" page.
4. Add a banner, and stop forms from sending (nothing can be saved online).
5. Copy static/ (CSS, fonts).

Everything happens inside a database transaction that is rolled back at the
end, so the demo check-ins it makes are never kept.

Safety: it refuses to run unless DEBUG is on and every phone number is a
fake demo one (0900 000 ...), so real member data can't be published.
"""

import re
import shutil
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.test import Client
from django.utils import timezone

from . import status
from .models import Member, SignUp
from .summary import summarize_all

FAKE_PHONE_PREFIX = "0900 000"
DEMO_USER = "lea"
DEMO_ONLY = "/demo-only/"
LINK = re.compile(r'(href|src|action)="([^"]*)"')


class NotDemoData(Exception):
    pass


def check_demo_data():
    """Stop if this database could hold real people."""
    if not settings.DEBUG:
        raise NotDemoData("DEBUG is off. Only export from a local demo database.")
    phones = list(Member.objects.values_list("phone", flat=True)) + list(SignUp.objects.values_list("phone", flat=True))
    if not phones:
        raise NotDemoData("No members. Run `manage.py seed_demo` first.")
    real = [p for p in phones if not p.startswith(FAKE_PHONE_PREFIX)]
    if real:
        raise NotDemoData(f"{len(real)} phone number(s) are not fake demo numbers. "
                          "Export only from a database filled by seed_demo.")


# ---- Which pages to save --------------------------------------------------------
def page_list(client, today):
    """Every URL to save. Check-in results are made here (rolled back later)."""
    urls = ["/", "/?show=expiring", "/?show=expired", "/?show=unpaid", "/login/",
            "/members/", "/members/add/", "/payments/walk-in/", "/checkin/", "/signups/",
            "/join/", "/join/done/"]
    urls += [f"/members/?status={s}" for s in ["active", "expiring", "expired", "owing"]]
    urls += [f"/payments/?day={today - timedelta(days=n):%Y-%m-%d}" for n in range(1, 7)]
    urls.append("/payments/")

    for m in Member.objects.filter(is_archived=False).values_list("pk", flat=True):
        urls += [f"/members/{m}/", f"/members/{m}/renew/", f"/members/{m}/pay/", f"/members/{m}/edit/"]
    for s in SignUp.objects.filter(status=SignUp.PENDING).values_list("pk", flat=True):
        urls += [f"/signups/{s}/", f"/members/add/?signup={s}"]

    # One check-in result of each colour, so the demo shows all three.
    wanted = {status.ACTIVE: None, status.EXPIRING: None, status.EXPIRED: None}
    for s in summarize_all(today):
        if s.status in wanted and wanted[s.status] is None and not s.is_owing:
            wanted[s.status] = s.member
    owing = next((s.member for s in summarize_all(today) if s.is_owing and s.status == status.ACTIVE), None)
    for member in [*wanted.values(), owing]:
        if member:
            code = member.card_uid or member.member_code
            response = client.post("/checkin/", {"code": code})
            urls.append(response["Location"])  # /checkin/?last=<id>
    return urls


# ---- Turning URLs into file names -------------------------------------------------
def file_for(url):
    """'/members/12/' -> 'members/12/index.html'; '/?show=expired' -> 'show-expired.html'."""
    parts = urlsplit(url)
    folder = parts.path.strip("/")
    query = sorted(parse_qsl(parts.query))
    name = "-".join(f"{k}-{v}" for k, v in query) + ".html" if query else "index.html"
    return f"{folder}/{name}" if folder else name


def key(url):
    """The same page written two ways ('?a=1&b=2' / '?b=2&a=1') gets one key."""
    parts = urlsplit(url)
    return parts.path + ("?" + urlencode(sorted(parse_qsl(parts.query))) if parts.query else "")


def relative(from_file, to_file):
    depth = from_file.count("/")
    return "../" * depth + to_file


def rewrite_links(html, page_url, page_file, saved):
    def fix(match):
        attr, target = match.group(1), match.group(2)
        if target.startswith(("#", "sms:", "tel:", "mailto:", "data:", "http://", "https://")):
            return match.group(0)
        absolute = urljoin(page_url, target) if target else page_url
        parts = urlsplit(absolute)
        if parts.path.startswith("/" + settings.STATIC_URL.lstrip("/")):  # CSS and fonts
            return f'{attr}="{relative(page_file, parts.path.lstrip("/"))}"'
        if attr == "action":
            return f'{attr}="#"'  # forms never send online (see DEMO_SCRIPT)
        found = saved.get(key(absolute)) or saved[key(DEMO_ONLY)]
        fragment = f"#{parts.fragment}" if parts.fragment else ""
        return f'{attr}="{relative(page_file, found)}{fragment}"'

    return LINK.sub(fix, html)


# ---- What every saved page gets -------------------------------------------------
def banner(today):
    return f"""
<div class="demo-bar" role="note">
  <strong>Online demo</strong> · fake members only · snapshot of {today:%d %b %Y}.
  Saving is switched off here. Run it on your PC to add members for real.
</div>
<dialog id="demo-dialog" class="demo-dialog">
  <p><strong>This online copy is a demo, so nothing is saved.</strong></p>
  <p>To really add a member, take a payment or check someone in, run the app on a PC (see the README).</p>
  <form method="dialog"><button class="pz-btn pz-go">OK</button></form>
</dialog>
<script>
  // Online demo only: stop every form (except the dialog's own) from sending.
  document.addEventListener("submit", function (e) {{
    if (e.target.method === "dialog") return;
    e.preventDefault();
    document.getElementById("demo-dialog").showModal();
  }});
</script>
"""


def demo_only_html(client):
    """A page for links that weren't saved (admin, search results...)."""
    html = client.get("/signups/").content.decode()  # borrow the site's header and footer
    start, end = html.index("<main"), html.index("</main>") + len("</main>")
    body = """<main class="stack"><section class="panel panel-pad narrow center">
  <h1 class="page-title">Not in the online demo</h1>
  <p class="caption">This page needs the real app with its database: the owner's admin, search,
  and anything that saves. Run it on a PC to try it (see the README).</p>
  <a class="pz-btn pz-go" href="/">Back to the dashboard</a>
</section></main>"""
    return html[:start] + body + html[end:]


def add_check_in_samples(html, samples):
    """Typing can't work online, so the check-in page links to saved results instead."""
    links = " ".join(
        f'<a class="pz-btn pz-ghost pz-small" href="{file_for(u).split("/")[-1]}">{word}</a>' for u, word in samples
    )
    box = f'<p class="help"><strong>Online demo:</strong> typing a card or code needs the real app. See a sample result: {links}</p>'
    return html.replace('<p class="help">Card readers', box + '<p class="help">Card readers', 1)


# ---- The whole export -------------------------------------------------------------
def export(out_dir, log=print):
    out = Path(out_dir)
    check_demo_data()
    today = timezone.localdate()
    if out.exists():
        shutil.rmtree(out)

    with transaction.atomic():
        client = Client(SERVER_NAME="localhost")
        client.force_login(User.objects.get(username=DEMO_USER))
        urls = list(dict.fromkeys(page_list(client, today)))  # keep order, drop repeats

        saved = {key(u): file_for(u) for u in urls}
        saved[key(DEMO_ONLY)] = file_for(DEMO_ONLY)
        pages = {}
        for url in urls:
            if url == "/login/":
                html = Client(SERVER_NAME="localhost").get(url).content.decode()
            else:
                response = client.get(url)
                if response.status_code != 200:
                    raise RuntimeError(f"{url} answered {response.status_code}")
                html = response.content.decode()
            pages[url] = html
        pages[DEMO_ONLY] = demo_only_html(client)
        samples = [(u, re.search(r'class="verdict-word">([^<]*)', pages[u]).group(1))
                   for u in urls if u.startswith("/checkin/?last=")]
        transaction.set_rollback(True)  # keep nothing the export did

    extra = banner(today)
    for url, html in pages.items():
        name = file_for(url)
        html = rewrite_links(html, url, name, saved)
        html = html.replace("<body>", "<body>" + extra, 1)
        if url == "/checkin/":
            html = add_check_in_samples(html, samples)
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")

    shutil.copytree(settings.BASE_DIR / "static", out / "static")
    (out / ".nojekyll").write_text("")  # tell GitHub Pages to serve files as they are
    log(f"Saved {len(pages)} pages to {out}")
    return len(pages)
