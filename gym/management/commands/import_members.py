"""
Import members from the notebook CSV.

    python manage.py import_members samples/sample_members.csv           # check only
    python manage.py import_members samples/sample_members.csv --commit  # save

The column list and rules are in gym/importer.py.
"""

from django.core.management.base import BaseCommand, CommandError

from gym.importer import read_csv, save_rows


class Command(BaseCommand):
    help = "Check (and with --commit, import) members from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument("csv_file")
        parser.add_argument("--commit", action="store_true", help="Actually save. Without it, nothing is saved.")

    def handle(self, csv_file, commit, **options):
        try:
            result = read_csv(csv_file)
        except FileNotFoundError:
            raise CommandError(f"File not found: {csv_file}")

        for line, reason in result.skipped:
            self.stdout.write(self.style.WARNING(f"  line {line}: SKIPPED, {reason}"))
        for line, reason in result.errors:
            self.stdout.write(self.style.ERROR(f"  line {line}: ERROR, {reason}"))
        self.stdout.write(f"{len(result.rows)} ready, {len(result.skipped)} skipped, {len(result.errors)} errors.")

        if not result.ok:
            raise CommandError("Fix the errors above and run again. Nothing was saved.")
        if not commit:
            self.stdout.write(self.style.NOTICE("Dry run: nothing saved. Add --commit to import."))
            return
        count = save_rows(result.rows)
        self.stdout.write(self.style.SUCCESS(f"Imported {count} members."))
