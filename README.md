# Pumpzone membership system

A **local prototype** of a front-desk membership system for Pumpzone gym. It replaces the paper notebook: who is active, who expires this week, who still owes money, and every cash or GCash payment, with the staff name on each one.

Built with Django 5.2 and SQLite, with plain HTML templates and one CSS file. No JavaScript build step.

> All member data in this repo is **fake sample data**. The database file (`data/`) is never committed.

The commands below are for **Windows PowerShell**, run from this folder.

---

## 1. Install (first time only)

Needs Python 3.12 or newer.

```powershell
python -m venv .venv
```

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```powershell
.venv\Scripts\python.exe manage.py migrate
```

## 2. Load the demo data

Fills the database with 223 fake members (phones all start `0900 000`), their payments, and three demo sign-ins. It refuses to run when DEBUG is off, so it can't wipe a live gym.

```powershell
.venv\Scripts\python.exe manage.py seed_demo
```

To wipe the gym data and start fresh:

```powershell
.venv\Scripts\python.exe manage.py seed_demo --reset
```

Demo sign-ins (**local demo only**, never on a real server):

| Username | Role | Password |
|---|---|---|
| `owner` | Owner: opens `/admin/`, can void payments | `pumpzone-demo` |
| `lea` | Front desk staff | `pumpzone-demo` |
| `rico` | Front desk staff | `pumpzone-demo` |

To make your own account instead (it asks for a password):

```powershell
.venv\Scripts\python.exe manage.py createsuperuser
```

## 3. Run

```powershell
.venv\Scripts\python.exe manage.py runserver
```

Open http://127.0.0.1:8000 and sign in. The owner back office is at http://127.0.0.1:8000/admin/.

**To stop the server**, click in that terminal and press **Ctrl + C**. Django's message says "CTRL-BREAK", but Ctrl + C works too. If it won't stop, or you closed the window, this stops whatever is running on port 8000:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

**To try it on the front-desk phone** (same Wi-Fi, demo only):

1. Find your PC's IP address with `ipconfig`, for example `192.168.1.20`.
2. Start the server:
   ```powershell
   $env:PUMPZONE_ALLOWED_HOSTS = "localhost,127.0.0.1,192.168.1.20"; .venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
   ```
3. On the phone, open `http://192.168.1.20:8000`. Windows may ask to allow Python through the firewall.

## 4. Import the notebook (CSV)

1. Type the notebook into a Google Sheet with these columns: `full_name, nickname, phone, plan_name, start_date, end_date, amount_paid, method, reference_no, notes`.
   - `samples/sample_members.csv` is a filled-in example.
   - Dates can be `2026-11-25` or `25/11/2026`, day first.
   - `end_date`, `amount_paid` and `method` may be left blank.
2. Download it as CSV into the `imports/` folder. Files there are ignored by git, so real names never reach the repo.
3. Check it first. Nothing is saved, and every problem row is listed:

```powershell
.venv\Scripts\python.exe manage.py import_members imports\notebook.csv
```

4. Once it reports 0 errors, save it:

```powershell
.venv\Scripts\python.exe manage.py import_members imports\notebook.csv --commit
```

Rows whose phone number is already on file are skipped. If a row has no phone, it's skipped when its name or nickname is already on file. Nobody is imported twice. Imported members get a note to ask for privacy consent at their next visit.

## 5. Back up and restore

The whole database is one file, `data\db.sqlite3`. This command makes a dated copy in `data\backups\` and keeps the newest 14. It's safe to run while the server is running.

```powershell
.venv\Scripts\python.exe manage.py backup_db
```

Every week, also copy the newest backup off this PC, for example to an encrypted Google Drive folder.

**To restore:** stop the server, then copy a backup over the live file (use your backup's real name):

```powershell
Copy-Item data\backups\db-2026-11-26_151736.sqlite3 data\db.sqlite3
```

Test a restore once before the gym relies on this. A backup you've never restored doesn't count.

## 6. Run the tests

```powershell
.venv\Scripts\python.exe manage.py test
```

There are 65 tests. They cover the expiry and payment rules at every boundary day (the core of the product), plus the screens, SMS text, import, seed and backups.

---

## How it works

| Rule | Where |
|---|---|
| Monthly plan: start 25 Nov, last valid day 25 Dec, expired from 26 Dec. 31 Jan ends 28 Feb. | `gym/dates.py` |
| Early renewal starts the day after the current end date, so no paid days are lost | `gym/dates.py` |
| Active = more than 7 days left. Expiring = 0 to 7 days left. Expired = past the last day. | `gym/status.py` |
| Unpaid = money owed. Late = still owed more than `GRACE_DAYS` (3) days after the start. | `gym/status.py` |
| Status is calculated from dates, never stored, so it can't go stale | `gym/summary.py` |
| Member codes are the year joined plus a number (`2026-0001`) and never change | `gym/models.py` |
| Payments can't be deleted or edited. The owner voids a mistake and must give a reason. | `gym/admin.py` |
| Every membership and payment records which staff member did it, including discounts | `gym/services.py` |
| Walk-ins pay for a day pass with a name only, valid that day | `gym/views/payments.py` |
| The SMS button opens the phone's SMS app with a pre-filled reminder. It says "PHP", not "₱", so it fits one SMS. | `gym/sms.py` |
| Login is required on every page | `LoginRequiredMiddleware` in `config/settings.py` |

## Settings

Local development needs no settings. For a real server (or Docker later), set the variables listed in `.env.example`:

| Variable | What it does |
|---|---|
| `PUMPZONE_SECRET_KEY` | A long random string, required on a server |
| `PUMPZONE_DEBUG` | `0` on a server |
| `PUMPZONE_ALLOWED_HOSTS` | Your domain name |
| `PUMPZONE_DATA_DIR` | The folder for the database and backups (a Docker volume later) |
| `PUMPZONE_GRACE_DAYS` | Days before an unpaid balance counts as late (default 3) |

## Project layout

| Path | What it is |
|---|---|
| `config/` | Django settings and the top-level URL map |
| `gym/models.py` | The tables: Plan, Member, Membership, Payment |
| `gym/dates.py`, `gym/status.py` | Expiry and payment rules (plain Python, fully tested) |
| `gym/summary.py` | Per-member status, balance and notes for the screens |
| `gym/services.py` | Desk actions: add member, sell or renew a membership, record a payment |
| `gym/forms.py` | Form checks for the desk screens |
| `gym/views/` | The screens: `dashboard.py`, `members.py`, `payments.py` |
| `gym/sms.py` | The SMS reminder text and link |
| `gym/importer.py` | CSV import rules |
| `gym/management/commands/` | `seed_demo`, `import_members`, `backup_db` |
| `gym/templates/gym/`, `templates/` | HTML templates |
| `static/css/pumpzone.css` | The Anti-Flat design system, ported from the mockup |
| `static/fonts/` | Archivo, Inter and JetBrains Mono (OFL licensed, self-hosted) |
| `mockup/dashboard.html` | The approved design mockup |
| `samples/sample_members.csv` | A fake CSV showing the import format |
| `PLAN.md` | Plan, data model and decisions |
| `data/` | The database and backups (not in git) |
