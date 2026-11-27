# Pumpzone membership system

A **local prototype** of a front-desk membership system for Pumpzone gym. It replaces the paper notebook and the logbook:
- who is active, who expires this week, and who still owes money;
- every cash or GCash payment, with the staff name on each one;
- who checked in today, by card tap or typed code.

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

Fills the database with fake demo data:
- 223 members (phones all start `0900 000`) on the gym's real price list, with their payments;
- 30 demo cards, numbered `DEMO0001` to `DEMO0030`;
- 60 check-ins today and 2 sign-ups waiting to be checked;
- three demo sign-ins.

It refuses to run when DEBUG is off, so it can't wipe a live gym.

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

**To use it from both floors' desks** (same Wi-Fi, demo only):

One PC runs the server. Each floor's phone, tablet or laptop opens it in a browser and signs in with that staff member's own account.

1. Find the PC's IP address with `ipconfig`, for example `192.168.1.20`.
2. Start the server:
   ```powershell
   $env:PUMPZONE_ALLOWED_HOSTS = "localhost,127.0.0.1,192.168.1.20"; .venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
   ```
3. On each desk device, open `http://192.168.1.20:8000`. Windows may ask to allow Python through the firewall.

Both desks can save at the same time. At closing, open **Payments**: the **By staff** table gives one row per staff member, so each floor counts its own drawer against its own cash total.

## 3b. Using it at the desk

**Prices** (the owner's list, to be confirmed). "30 days" runs to the same date next month: 25 Nov to 25 Dec. "15 days" counts the start day as day 1: 25 Nov to 9 Dec.

| Plan | Adult | Student |
|---|---|---|
| Day pass (walk-in) | ₱100 | ₱70 |
| 15 days | ₱450 | ₱400 |
| 30 days (Monthly) | ₱900 | ₱650 |

Student prices need a student ID or a school uniform. The plan picker and the check-in screen remind staff. The owner can change prices in `/admin/` under Plans. To retire an old price, untick "is active" so its history is kept.

**Late payments:** a balance counts as late 3 days after the start date. To change that, set `PUMPZONE_GRACE_DAYS` (see Settings). No code changes are needed.

**Check-in** (replaces the logbook): open **Check-in**. The box is ready to type in.
- **With a USB NFC reader:** tap the card. Buy the kind sold as a "USB 13.56 MHz IC/NFC card reader, keyboard emulation" (plug and play). It types the card number and presses Enter by itself, with no driver or app. It also works on an Android phone or tablet with a USB-OTG adapter. Readers like the ACR122U are a different kind: they need a driver and extra software, so they won't work this way.
- **To give a member a card:** open them, choose **Edit**, click **Card number** and tap the card. Use the same reader model for linking and checking in, because readers can write the same card's number differently (some in hex, some in decimal).
- **Without a reader:** type a member code (`2026-0001`), a phone number, or a nickname, then Enter. In the demo, try `DEMO0001`.
- **The answer:** green means Active. Amber means expiring soon or owes money. Red means expired, no membership, or late payment. Every visit is logged, even red ones, so the owner can see who trains without paying.
- Phone NFC (Web NFC) isn't used. It only works in Chrome on Android over HTTPS, and the local prototype runs over plain HTTP.

**Member sign-up** (members type their own details):
1. On the dashboard or Check-in screen, tap **Member sign-up** and hand the phone over. The phone is now in **sign-up mode**: every page except the sign-up form is blocked, so the member can't see anyone else's details.
2. The member fills it in, ticks the privacy notice and taps **Send to the front desk**.
3. To get the phone back, tap **Staff only** (or **Staff: unlock**) and type your own username and password. After 5 wrong tries it pauses for 5 minutes. Signing out also ends sign-up mode.
4. Open **Sign-ups** (the number shows how many are waiting) and check each one with the person. Choose one of:
   - **Add as new member:** opens Add member already filled in. Pick the plan and take payment.
   - **Notebook member:** they already paid in the notebook. Copy the plan, start date and amount paid. That payment is dated on the notebook start date, so it doesn't count in today's drawer.
   - **Same person: update details:** shown when someone with the same phone or name is already on file.
   - **Dismiss:** for spam or a double sign-up. It's kept, with your name.

**Moving off the notebook:** keep sign-up mode ready for about a month. Every active member visits at least once a month, so after 30 days everyone active is in the system and the notebook can be retired. For a faster bulk catch-up, use the CSV import (section 4).

**GCash:** tick GCash on any payment form and a QR code appears to show the member. They pay, then read you the reference number from their confirmation, which you type in.
- The prototype shows a **DEMO** QR. It only contains text and can't receive money.
- Going live: in the GCash app, open Receive > QR and save the image. Then set `PUMPZONE_GCASH_QR_IMAGE` to its file path (see Settings).
- A QR that fills in the amount by itself needs a paid merchant account, so it isn't included.

## 4. Import the notebook (CSV)

This is the bulk route. Sign-up mode (section 3b) is the everyday route.

1. Type the notebook into a Google Sheet with these columns: `full_name, nickname, phone, plan_name, start_date, end_date, amount_paid, method, reference_no, notes`. `method` is `cash` or `gcash`.
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

**To restore:** stop the server, then copy a backup over the live file (use your backup's real name). The database runs in WAL mode, so first delete the two helper files next to it. If you leave them, they can mix old changes into the restored copy.

```powershell
Remove-Item data\db.sqlite3-wal, data\db.sqlite3-shm -ErrorAction SilentlyContinue
```

```powershell
Copy-Item data\backups\db-2026-11-26_151736.sqlite3 data\db.sqlite3
```

Test a restore once before the gym relies on this. A backup you've never restored doesn't count.

## 6. Run the tests

```powershell
.venv\Scripts\python.exe manage.py test
```

There are 100 tests. They cover the expiry and payment rules at every boundary day (the core of the product). They also cover the screens, check-in, sign-up mode and its lock, per-staff totals, the GCash QR, SMS text, import, seed and backups.

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
| Walk-ins pay for an adult or student day pass with a name only, valid that day | `gym/views/payments.py` |
| Cash and GCash only. The GCash QR is a demo until the real image is set. | `gym/qr.py` |
| Each staff member's takings are totalled on their own (one cash drawer per floor) | `gym/cashup.py` |
| Check-in finds the member by card, code, phone or nickname, and logs every visit | `gym/checkin.py` |
| Sign-up mode blocks every page except the sign-up form until a staff password is typed | `gym/kiosk.py` |
| Notebook periods are carried over with the payment dated on the notebook start date | `gym/services.py` |
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
| `PUMPZONE_GCASH_QR_IMAGE` | File path of the gym's real GCash QR image. Blank = the demo QR |

## Project layout

| Path | What it is |
|---|---|
| `config/` | Django settings and the top-level URL map |
| `gym/models.py` | The tables: Plan, Member, Membership, Payment, CheckIn, SignUp |
| `gym/dates.py`, `gym/status.py` | Expiry and payment rules (plain Python, fully tested) |
| `gym/summary.py` | Per-member status, balance and notes for the screens |
| `gym/services.py` | Desk actions: add member, sell or renew a membership, record a payment |
| `gym/forms.py` | Form checks for the desk screens |
| `gym/views/` | The screens: `dashboard.py`, `checkin.py`, `members.py`, `payments.py`, `signups.py` |
| `gym/checkin.py`, `gym/kiosk.py` | Check-in lookup, and the sign-up mode lock |
| `gym/cashup.py`, `gym/qr.py` | Per-staff totals, and the GCash QR |
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
