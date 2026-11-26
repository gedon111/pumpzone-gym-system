# Pumpzone membership system

A local prototype of a front-desk membership system for Pumpzone gym. It tracks members, expiry dates and payments (cash or GCash). Built with Django and SQLite, with no JavaScript build step.

All member data in this repo is **fake sample data**. The database file is never committed.

The commands below are for Windows PowerShell, run from this folder.

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

Create your own sign-in (it asks for a username and password):

```powershell
.venv\Scripts\python.exe manage.py createsuperuser
```

## 2. Run

```powershell
.venv\Scripts\python.exe manage.py runserver
```

Open http://127.0.0.1:8000 and sign in. The owner back office is at http://127.0.0.1:8000/admin/.

To use it from the front-desk phone on the same Wi-Fi, run it with `runserver 0.0.0.0:8000` and add your PC's IP address to `PUMPZONE_ALLOWED_HOSTS`. This is for demos only, not for a live gym.

## 3. Seed demo data

Fills the database with 223 **fake** members (phones all start `0900 000`), their payments, and three demo sign-ins. It only runs when DEBUG is on, so it can't wipe a live gym.

```powershell
.venv\Scripts\python.exe manage.py seed_demo
```

To wipe the gym data and start fresh:

```powershell
.venv\Scripts\python.exe manage.py seed_demo --reset
```

Demo sign-ins (local demo only, never use on a real server):

| Username | Role | Password |
|---|---|---|
| `owner` | Owner: can open `/admin/` and void payments | `pumpzone-demo` |
| `lea` | Front desk staff | `pumpzone-demo` |
| `rico` | Front desk staff | `pumpzone-demo` |

## 4. Back up the database

The whole database is one file: `data\db.sqlite3`. Stop the server first, then copy the file with a date in its name:

```powershell
New-Item -ItemType Directory -Force backups; Copy-Item data\db.sqlite3 "backups\db-$(Get-Date -Format yyyy-MM-dd).sqlite3"
```

To restore, stop the server and copy a backup back over `data\db.sqlite3`.

## 5. Run the tests

```powershell
.venv\Scripts\python.exe manage.py test
```

## Settings

Local development needs no settings. For a real server (or Docker later), see `.env.example`. The variables are:

- `PUMPZONE_SECRET_KEY`
- `PUMPZONE_DEBUG`
- `PUMPZONE_ALLOWED_HOSTS`
- `PUMPZONE_DATA_DIR`
- `PUMPZONE_GRACE_DAYS`

## Project layout

| Path | What it is |
|---|---|
| `config/` | Django settings and the top-level URL map |
| `gym/` | The app: members, memberships, payments, screens |
| `templates/` | Shared templates (login page) |
| `static/` | CSS and fonts |
| `mockup/dashboard.html` | The approved design mockup |
| `PLAN.md` | Plan, data model and decisions |
| `data/` | The database (not in git) |
