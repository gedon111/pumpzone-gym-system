"""Backups are written and old ones are pruned."""

import shutil
import sqlite3
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.db import connection
from django.test import TransactionTestCase, override_settings


class BackupTests(TransactionTestCase):
    def test_backup_and_prune(self):
        data_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, data_dir, True)
        db_file = data_dir / "source.sqlite3"
        # Make a small real database file to back up.
        con = sqlite3.connect(db_file)
        con.execute("create table t (x)")
        con.commit()
        con.close()
        backups = data_dir / "backups"
        backups.mkdir()
        for i in range(3):
            (backups / f"db-2020-01-0{i + 1}_000000.sqlite3").write_text("old")

        db = {**connection.settings_dict, "NAME": db_file}
        with override_settings(DATA_DIR=data_dir, DATABASES={"default": db}):
            call_command("backup_db", "--keep", "2", stdout=StringIO())

        kept = sorted(p.name for p in backups.iterdir())
        self.assertEqual(len(kept), 2)
        self.assertEqual(kept[0], "db-2020-01-03_000000.sqlite3")  # newest old one survives
        self.assertTrue(kept[1].startswith("db-20") and kept[1] != kept[0])
