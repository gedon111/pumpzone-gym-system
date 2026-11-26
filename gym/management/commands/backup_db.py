"""
Back up the database to data/backups/, keeping the newest 14 copies.

    python manage.py backup_db

Safe to run while the server is running: it uses SQLite's own backup
feature, not a plain file copy. On a server, schedule it once a day.
Copy the newest file somewhere off the machine every week.
"""

import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

KEEP = 14


class Command(BaseCommand):
    help = "Copy the database to data/backups/ and delete copies older than the newest 14."

    def add_arguments(self, parser):
        parser.add_argument("--keep", type=int, default=KEEP, help=f"How many backups to keep (default {KEEP}).")

    def handle(self, keep, **options):
        source_path = Path(settings.DATABASES["default"]["NAME"])
        backup_dir = Path(settings.DATA_DIR) / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        target_path = backup_dir / f"db-{timezone.localtime():%Y-%m-%d_%H%M%S}.sqlite3"

        source = sqlite3.connect(source_path)
        target = sqlite3.connect(target_path)
        with target:
            source.backup(target)
        source.close()
        target.close()

        # Delete the oldest copies beyond `keep`. Names sort by date.
        backups = sorted(backup_dir.glob("db-*.sqlite3"))
        for old in backups[:-keep] if keep > 0 else []:
            old.unlink()

        size_kb = target_path.stat().st_size // 1024
        self.stdout.write(self.style.SUCCESS(f"Backed up to {target_path} ({size_kb} KB). {min(len(backups), keep)} kept."))
