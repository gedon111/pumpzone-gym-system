"""CSV import: good rows, bad rows, duplicates, and never saving half a file."""

import os
import tempfile
from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase

from gym.importer import read_csv
from gym.models import Member, Payment, Plan

HEADER = "full_name,nickname,phone,plan_name,start_date,end_date,amount_paid,method,reference_no,notes\n"


class ImportTests(TestCase):
    def setUp(self):
        Plan.objects.create(name="Monthly", price=Decimal("1000"))

    def csv(self, body, header=HEADER):
        f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
        f.write(header + body)
        f.close()
        self.addCleanup(os.remove, f.name)
        return f.name

    def run_import(self, path, commit=True):
        call_command("import_members", path, *(["--commit"] if commit else []), stdout=StringIO())

    def test_good_rows_import_with_payments(self):
        path = self.csv("Ana Lim,Ana,0900 000 0001,monthly,25/11/2026,,\"1,000\",gcash,123,\n"
                        "Ben Tan,,0900 000 0002,Monthly,2026-11-01,,0,,,\n")
        self.run_import(path)
        ana = Member.objects.get(full_name="Ana Lim")
        self.assertEqual(ana.latest_membership.end_date, date(2026, 12, 25))
        self.assertEqual(ana.balance, Decimal("0"))
        self.assertEqual(Member.objects.get(full_name="Ben Tan").balance, Decimal("1000"))
        self.assertEqual(Payment.objects.count(), 1)

    def test_dry_run_saves_nothing(self):
        self.run_import(self.csv("Ana Lim,,0900 000 0001,Monthly,2026-11-25,,1000,cash,,\n"), commit=False)
        self.assertFalse(Member.objects.exists())

    def test_one_bad_row_blocks_the_whole_file(self):
        path = self.csv("Ana Lim,,0900 000 0001,Monthly,2026-11-25,,1000,cash,,\n"
                        "Ben Tan,,0900 000 0002,Yearly,11/25/2026,,abc,card,,\n")
        result = read_csv(path)
        reasons = " ".join(r for _, r in result.errors)
        for expected in ["Unknown plan", "not a date", "not a number", "must be cash"]:
            self.assertIn(expected, reasons)
        with self.assertRaises(CommandError):
            self.run_import(path)
        self.assertFalse(Member.objects.exists())

    def test_existing_phone_is_skipped_even_with_different_spacing(self):
        Member.objects.create(full_name="Ana Lim", phone="09000000001")
        result = read_csv(self.csv("Ana L.,,0900 000 0001,Monthly,2026-11-25,,,,,\n"))
        self.assertEqual(len(result.skipped), 1)
        self.assertEqual(result.rows, [])

    def test_no_phone_matches_on_name_or_nickname(self):
        Member.objects.create(full_name="Marco Dela Cruz", nickname="Marky")
        result = read_csv(self.csv("Marky,,,Monthly,2026-11-25,,,,,\n"))
        self.assertEqual(len(result.skipped), 1)

    def test_same_phone_twice_in_file_is_an_error(self):
        result = read_csv(self.csv("A One,,0900 000 0001,Monthly,2026-11-25,,,,,\n"
                                   "A Two,,0900-000-0001,Monthly,2026-11-25,,,,,\n"))
        self.assertEqual(len(result.errors), 1)

    def test_missing_column(self):
        result = read_csv(self.csv("Ana,0900\n", header="full_name,phone\n"))
        self.assertIn("Missing column", result.errors[0][1])

    def test_sample_file_is_valid(self):
        Plan.objects.create(name="Student Monthly", price=Decimal("650"))
        Plan.objects.create(name="15 Days", length=15, unit="day", price=Decimal("450"))
        Plan.objects.create(name="Student 15 Days", length=15, unit="day", price=Decimal("400"))
        result = read_csv("samples/sample_members.csv")
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(len(result.rows), 8)

    def test_method_other_is_rejected(self):
        result = read_csv(self.csv("Ana Lim,,0900 000 0001,Monthly,2026-11-25,,1000,other,,\n"))
        self.assertIn("must be cash or gcash", result.errors[0][1])
