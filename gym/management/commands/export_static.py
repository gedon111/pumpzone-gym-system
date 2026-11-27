"""
Save the demo as plain HTML pages for GitHub Pages (see gym/static_export.py).

    python manage.py export_static _site

Only works on a database filled by seed_demo (fake phone numbers only).
The GitHub Actions workflow (.github/workflows/pages.yml) runs this on
GitHub with a fresh demo database, so you normally don't run it yourself.
"""

from django.core.management.base import BaseCommand, CommandError

from gym.static_export import NotDemoData, export


class Command(BaseCommand):
    help = "Save the demo screens as plain HTML for the online demo (fake data only)."

    def add_arguments(self, parser):
        parser.add_argument("out_dir", nargs="?", default="_site", help="Folder to write (wiped first). Default: _site")

    def handle(self, *args, **options):
        try:
            export(options["out_dir"], log=self.stdout.write)
        except NotDemoData as e:
            raise CommandError(f"Refusing to export: {e}")
