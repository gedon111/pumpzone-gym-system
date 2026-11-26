"""
Read the notebook data from a CSV file and load it into the database.

Columns (first row must be these headers, in any order):
    full_name      required
    nickname       optional, the logbook name
    phone          optional but strongly recommended (used to spot duplicates)
    plan_name      required, must match a Plan name, e.g. "Monthly"
    start_date     required, 2026-11-25 or 25/11/2026 (day first)
    end_date       optional, worked out from the plan if blank
    amount_paid    optional, 0 or blank = nothing paid yet
    method         optional, cash (default), gcash or other
    reference_no   optional, GCash reference
    notes          optional

Rules:
- Checking (dry run) never saves anything.
- Saving only happens if EVERY row is readable. Fix the file and run again.
- A row whose phone (or, with no phone, whose name or nickname) is already
  on file is SKIPPED and listed, never imported twice.
"""

import csv
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Member, Membership, Payment, Plan

REQUIRED = ["full_name", "plan_name", "start_date"]
KNOWN = REQUIRED + ["nickname", "phone", "end_date", "amount_paid", "method", "reference_no", "notes"]
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
METHODS = {"cash": Payment.CASH, "gcash": Payment.GCASH, "g-cash": Payment.GCASH, "other": Payment.OTHER}


@dataclass
class Row:
    line: int
    full_name: str
    nickname: str
    phone: str
    plan: Plan
    start_date: date
    end_date: date | None
    amount_paid: Decimal
    method: str
    reference_no: str
    notes: str


@dataclass
class ImportResult:
    rows: list = field(default_factory=list)      # ready to import
    skipped: list = field(default_factory=list)   # (line, reason) already on file
    errors: list = field(default_factory=list)    # (line, reason) must be fixed

    @property
    def ok(self):
        return not self.errors


def digits(phone):
    return re.sub(r"\D", "", phone or "")


def parse_date(text, column, line, errors):
    text = (text or "").strip()
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    errors.append((line, f"{column} '{text}' is not a date. Use 2026-11-25 or 25/11/2026."))
    return None


def read_csv(path) -> ImportResult:
    """Check every row. Saves nothing."""
    result = ImportResult()
    plans = {p.name.lower(): p for p in Plan.objects.all()}
    phones_on_file = {digits(p) for p in Member.objects.exclude(phone="").values_list("phone", flat=True)}
    phones_in_file = {}

    # utf-8-sig removes the invisible marker Excel / Google Sheets may add.
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = [h.strip().lower() for h in (reader.fieldnames or [])]
        missing = [h for h in REQUIRED if h not in headers]
        if missing:
            result.errors.append((1, f"Missing column(s): {', '.join(missing)}. Expected: {', '.join(KNOWN)}"))
            return result
        reader.fieldnames = headers

        for line, raw in enumerate(reader, start=2):  # line 1 is the header
            values = {k: (v or "").strip() for k, v in raw.items() if k}
            if not any(values.values()):
                continue  # blank line
            row = check_row(line, values, plans, result.errors)
            if row is None:
                continue

            # Duplicates: by phone, or by name / nickname when there is no phone.
            key = digits(row.phone)
            if key and key in phones_on_file:
                result.skipped.append((line, f"{row.full_name}: phone {row.phone} is already on file"))
                continue
            if key and key in phones_in_file:
                result.errors.append((line, f"Same phone as line {phones_in_file[key]}. Merge or fix one of them."))
                continue
            if not key and Member.objects.filter(
                Q(full_name__iexact=row.full_name) | Q(nickname__iexact=row.nickname or row.full_name)
            ).exists():
                result.skipped.append((line, f"{row.full_name}: no phone, and this name is already on file"))
                continue
            if key:
                phones_in_file[key] = line
            result.rows.append(row)
    return result


def check_row(line, v, plans, errors):
    """Turn one CSV line into a Row, or add errors and return None."""
    before = len(errors)
    if not v.get("full_name"):
        errors.append((line, "full_name is empty."))
    plan = plans.get(v.get("plan_name", "").lower())
    if not plan:
        errors.append((line, f"Unknown plan '{v.get('plan_name', '')}'. Use one of: {', '.join(p.name for p in plans.values())}."))
    start = parse_date(v.get("start_date"), "start_date", line, errors)
    if not v.get("start_date"):
        errors.append((line, "start_date is empty."))
    end = parse_date(v.get("end_date"), "end_date", line, errors)
    if start and end and end < start:
        errors.append((line, "end_date is before start_date."))
    try:
        amount = Decimal((v.get("amount_paid") or "0").replace(",", ""))  # "1,000" -> 1000
        if amount < 0:
            raise InvalidOperation
    except InvalidOperation:
        errors.append((line, f"amount_paid '{v.get('amount_paid')}' is not a number."))
        amount = Decimal("0")
    method = METHODS.get((v.get("method") or "cash").lower())
    if not method:
        errors.append((line, f"method '{v.get('method')}' must be cash, gcash or other."))
    if len(errors) > before:
        return None
    return Row(line, v["full_name"], v.get("nickname", ""), " ".join(v.get("phone", "").split()), plan, start, end,
               amount, method, v.get("reference_no", ""), v.get("notes", ""))


@transaction.atomic
def save_rows(rows):
    """Create members, memberships and payments. All or nothing."""
    for r in rows:
        member = Member.objects.create(
            full_name=r.full_name, nickname=r.nickname, phone=r.phone, joined_on=r.start_date,
            notes=("Imported from notebook. Ask for privacy consent at next visit.\n" + r.notes).strip(),
        )
        membership = Membership.objects.create(member=member, plan=r.plan, start_date=r.start_date,
                                               end_date=r.end_date)  # blank end date = worked out from the plan
        if r.amount_paid > 0:
            Payment.objects.create(
                membership=membership, amount=r.amount_paid, method=r.method,
                reference_no=r.reference_no or ("not recorded (import)" if r.method == Payment.GCASH else ""),
                paid_on=timezone.make_aware(datetime.combine(r.start_date, time(12, 0))),  # noon, Manila time
            )
    return len(rows)
