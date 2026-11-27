# Pumpzone Membership System: Prototype Plan

Version 1, 2026-11-26.

**Update 2026-11-26:** the current build is the **local prototype for the pitch (M0)**, not the live system, so the "no M2 before M1" rule still holds for go-live. Hosting (M5) is deferred; the app may later run on the developer's own server, possibly in Docker. Decisions made with the developer:
- Staff can change the agreed price (discounts); the change records who made it.
- Late flag after `GRACE_DAYS` = 3 (a setting).
- CSV import matches existing members by phone number. Members also get a `nickname` field, because the logbook uses nicknames while registration uses the full name.
- Walk-ins are logged as a day-pass payment with a name, valid for that day only.
- NFC membership cards are the planned check-in method (replacing the QR-first idea in Phase 3). Not built in v1.

**Update 2026-11-27: answers relayed by the developer.** These change the build as follows:

| Topic | Answer | What was built |
|---|---|---|
| Prices | Adult: day PHP 100, 15 days PHP 450, 30 days PHP 900. Student: day PHP 70, 15 days PHP 400, 30 days PHP 650 (from memory, to be confirmed). | Six plans in the demo seed. The 3 Months plan is dropped. "30 days" uses the calendar-month rule (25 Nov to 25 Dec). 15 days = start day plus 14. |
| Grace period | 3 days, for now | Unchanged. It is the `PUMPZONE_GRACE_DAYS` setting. |
| Getting members in | Members (or staff) type their own details in | **Sign-up mode** on the desk phone, tablet or laptop: the device locks to a sign-up form, and staff unlock it with their password. Staff then check each sign-up: new member, notebook member (carry over the period they already paid), same as an existing member, or dismiss. |
| Payment methods | About 1 in 10 pay by GCash. Cash and GCash only, plus a fake QR Ph | "Other" is removed. A DEMO QR shows when GCash is chosen. The real QR image from the GCash app replaces it through a setting. |
| Staff | One per floor, 2 floors | A per-staff cash-up (one row per drawer). SQLite is in WAL mode so two desks can save at once. |
| Walk-ins | Tracked by name | Unchanged, plus an adult or student day pass choice. |
| NFC | Not decided, but make it ready | A card number on each member, and a **Check-in screen**. A USB NFC reader in keyboard mode types the card number. Without one, staff type a code, phone or nickname. |
| Hosting | Undecided, temporary | Stays local. |

**Deviation from section 1 "Not in v1":** check-in is now built (typed or card), because "NFC ready" needs somewhere to tap the card. Automatic reminders, online payments and turnstiles are still out.

**Notebook move-over plan (replaces typing the whole notebook into a CSV):**
1. For about one month, keep the desk phone ready in sign-up mode when members arrive.
2. Every active member visits at least once a month. They type their own details, and staff carry over their notebook period (plan, start date, amount paid). The payment is dated on the notebook date, so today's drawer stays correct.
3. After 30 days, everyone active is in the system. Retire the notebook. Anyone missing can still go in by CSV import.

Labels used below:
- **[FACT]** checked against a source on 2026-11-26.
- **[GUESS]** an estimate. Confirm it before you quote it to the owner.

---

## 1. Goal and scope

Replace the paper notebook with a phone-friendly web app that staff use at the front desk. It should:

1. Show who is active, who expires within 7 days, and who has already expired.
2. Record every payment (cash or GCash) and flag members who have not paid.
3. Make adding and renewing a member take less than a minute.

**Not in v1:** automatic SMS or Messenger reminders, QR or NFC check-in, GCash API integration, a member-facing app, online payments.

**Honest reality check**
- A well-built Google Sheet with conditional formatting solves about 60% of this problem for PHP 0. The owner may ask why they should pay you instead. Your answer: separate staff logins, a payment history that cannot be quietly edited, a one-screen expiry dashboard, and no formulas to break. If you cannot explain that clearly, the pitch will fail.
- You read Python but cannot write it from scratch. Building this will mean pairing with an AI assistant and reading every line before you ship it. Plan for 4 to 6 weekends, not 1.
- The weakest part of the business is **you supporting it**. If the app goes down at 6 AM and you are in school, the gym is stuck. Section 11 covers this.

---

## 2. Stack decisions

| Area | Decision | Why | Rejected alternative | Why rejected |
|---|---|---|---|---|
| Backend | **Django 5.x (Python)** | You read Python. It comes with login, an admin panel, forms, and a database layer. The admin panel alone gives the owner a working back office for free. | Flask / FastAPI | You would have to build login, admin, and forms yourself. That is more code to maintain. |
| Frontend | **Django templates + one hand-written CSS file** (`static/css/pumpzone.css`) that reproduces the approved Anti-Flat mockup (`mockup/dashboard.html`). No build step. Fonts are self-hosted from the mockup's OFL files. (Changed from Pico.css, which would give a default flat look.) Add HTMX later only if a page feels slow. | No JavaScript framework to learn. Pages work on any phone browser. | React / Next.js | It means a second language, a build pipeline, and an API layer. That is too much for one part-time maintainer. |
| Database | **SQLite** (one file) | 100 visits a day is tiny. SQLite handles thousands of writes a minute. Backup means copying one file. | PostgreSQL / Supabase | It is another service to run, and the Supabase free tier pauses projects that sit idle. You gain nothing at this size. |
| Hosting | **PythonAnywhere**. Build on the free tier, then run the live gym on the **Developer plan, USD 10 a month**. | It runs Python natively, has persistent disk for SQLite, no cold starts, a browser console, scheduled tasks for backups, and HTTPS. It is the easiest deploy for a Python beginner. | Render free web service + Neon free Postgres | Render's free tier sleeps after idle time, so the first load each morning takes about 30 to 60 seconds **[GUESS]**. You would also run two services. Keep it only as the PHP 0 fallback (Section 7). |
| Auth | **Django built-in login, one account per staff member**, plus an "Owner" group and a "Staff" group | Every payment records who received it. That is the main reason the owner will trust the system with cash. | A shared PIN or one shared login | Nobody is accountable for cash, which is the exact problem a notebook already has. |

---

## 3. Data model

All tables get `created_at` and `updated_at`. Django's built-in `auth_user` table holds staff accounts.

### Plan (price list)
| Field | Type | Notes |
|---|---|---|
| id | int | |
| name | text | Examples: "Monthly", "Student Monthly", "3 Months", "Daily Pass" **[GUESS: real plans unknown]** |
| duration_days | int | 30, 90, 1 |
| price | decimal | In PHP |
| is_active | bool | Hide old prices without deleting history |

### Member
| Field | Type | Notes |
|---|---|---|
| id | int | |
| member_code | text, unique | Example: PZ-0001. It goes on the QR card later. |
| full_name | text | |
| phone | text | Optional, but needed for reminders later |
| emergency_contact_name / phone | text | Optional |
| joined_on | date | From the notebook if known |
| consent_given_on | date | Data Privacy Act consent (Section 9) |
| notes | text | Free text. Do **not** store health conditions (Section 9). |
| is_archived | bool | Use this instead of deleting |

### Membership (one row per paid period)
| Field | Type | Notes |
|---|---|---|
| id | int | |
| member | FK Member | |
| plan | FK Plan | |
| start_date | date | |
| end_date | date | start_date + plan.duration_days - 1 |
| price_agreed | decimal | Copied from the plan, editable for discounts |
| created_by | FK User | |

### Payment
| Field | Type | Notes |
|---|---|---|
| id | int | |
| membership | FK Membership | |
| amount | decimal | Partial payments are allowed |
| method | choice | cash, gcash, other |
| reference_no | text | GCash reference number. Required when the method is gcash. |
| paid_on | datetime | |
| received_by | FK User | |
| is_voided / void_reason | bool / text | Staff cannot delete payments. They void them with a reason. Only the owner can void. |

### Calculated values (not stored)
- **Balance** = price_agreed - sum of non-voided payments.
- **Status**, based on the member's latest membership:
  - Active: today <= end_date and more than 7 days remain
  - Expiring: 0 to 7 days remain
  - Expired: end_date < today
- **Unpaid flag**: balance > 0. It turns into a **Late** flag when the balance is still unpaid `GRACE_DAYS` (a setting, default 3) after start_date.

Walk-in daily customers are an open question. If they pay per visit and nobody tracks them by name, v1 can log them as a simple "walk-in sale" payment with no member attached.

---

## 4. v1 screens and flows

Every screen must work on a phone in portrait mode, because the desk device is probably a phone.

1. **Login.**
2. **Dashboard** (home): four tap-able count cards: Active, Expiring in 7 days, Expired (last 30 days), Unpaid/Late. Below them, today's payments split into cash and GCash. The owner will check that total against the cash drawer.
3. **Member list**: search by name, phone or code. Filter by status. Each row shows name, end date, a status color, and an unpaid badge.
4. **Member detail**: contact info, membership history, payments, and buttons for **Renew** and **Log payment**.
5. **Add member**: name, phone, optional emergency contact, a consent checkbox, plan, start date (default today), and an optional first payment in the same form. Target: under 60 seconds.
6. **Renew**: pick a plan. The start date defaults to the later of today or the day after the current end date, so early renewals do not lose days. Record the payment in the same step.
7. **Log payment**: amount, method, GCash ref, against a chosen membership.
8. **Owner only**: Django admin for plans, staff accounts and voids, plus a **CSV export** of members and payments.

**Main flow at the desk:** a member walks in, staff searches the name, the status color shows instantly, and staff renews or collects payment if the member is expired or unpaid.

---

## 5. Importing the notebook

1. Make a Google Sheet template with columns: `full_name, phone, plan_name, start_date, end_date, amount_paid, notes`.
2. **Enter only active members and those expired in the last 60 days.** Leave older history in the notebook and keep it as an archive. This is the biggest time saver.
3. Someone types the rows in. At about 1 minute per member, 300 members is about 5 hours **[GUESS: member count unknown]**. Negotiate who does this. If you do it, charge for it or include it in the upfront fee.
4. Download the sheet as CSV. A Django management command (`python manage.py import_members file.csv`) creates the Member, Membership and Payment rows. It does a dry run first and prints the rows it cannot read.
5. Staff spot-check 20 random members against the notebook.
6. **Run both in parallel for 2 weeks** (notebook plus app), then retire the notebook.

Rejected: photographing pages and using OCR. Handwritten notebooks give poor accuracy, and fixing the errors takes longer than typing.

---

## 6. Hosting and running costs

Exchange rate assumed: USD 1 = PHP 58 **[GUESS, check on the day]**.

| Item | Cost | Notes |
|---|---|---|
| PythonAnywhere free tier (building and demo) | PHP 0 | |
| PythonAnywhere Developer (live) | USD 10/mo, about **PHP 580/mo** | **[FACT]** Pay with a card. A GCash virtual card may work **[GUESS]**. |
| Custom domain, e.g. pumpzone.com (optional) | about PHP 600 to 900/yr **[GUESS]** | Only possible on the paid plan. You can skip it. |
| Desk device | PHP 0 if staff use the gym phone | A cheap Android tablet costs about PHP 4,000 to 7,000 **[GUESS]** |
| **Total running cost** | **about PHP 580 to 650/mo** | |

### Free-tier limits and what breaks **[FACT, PythonAnywhere free account changes effective 2026-01-15]**
| Limit | What breaks |
|---|---|
| Web app **expires after 1 month** unless renewed | The app goes offline at the desk. **This alone makes the free tier unfit for real use.** |
| No scheduled tasks for new accounts | No automatic daily backups |
| No MySQL for new accounts | Nothing. SQLite is a file, so it still works. |
| 512 MB disk | Nothing for years. The database will stay under 50 MB **[GUESS]**. |
| 100 CPU seconds/day (consoles) | Running imports in the console may hit it. The web app itself is light. |
| Restricted outbound internet (whitelist) | SMS APIs may be blocked, so reminders need the paid plan anyway |
| No custom domain, community support only | You get a `yourname.pythonanywhere.com` link, which looks less professional |

**Decision:** demo on the free tier and go live on Developer. Build the PHP 580 into the monthly fee.

---

## 7. PHP 0 fallback (only if the owner refuses any monthly cost)

Render free web service plus Neon free Postgres. Expect a slow first load after idle time, two dashboards to manage, and free-tier terms that change without much notice. Tell the owner plainly that this setup is less reliable.

---

## 8. Backups

1. **Daily automatic** (paid plan scheduled task): copy `db.sqlite3` to a dated file and keep the last 14 copies on the server.
2. **Weekly off-site**: you download the latest copy to your PC and an encrypted Google Drive folder. Set a phone reminder.
3. **Owner self-service**: the CSV export button means the owner always has their data, even if you disappear. Say this in the pitch. It builds trust.
4. **Test a restore once** before go-live. A backup you have never restored does not count as a backup.

---

## 9. Data privacy (Philippine Data Privacy Act, RA 10173) basics

I am not a lawyer. This is a minimum checklist.

- **Collect only what you need**: name, phone, optional emergency contact. **Do not store health conditions, IDs, or photos in v1.** Health information is "sensitive personal information" under the Act and needs stricter handling.
- **Consent**: have a short printed or on-screen notice saying what is collected, why (membership tracking and reminders), who can see it, and how long it is kept. Record `consent_given_on`.
- **Roles**: the gym owner is the *personal information controller*. You are the *processor*. Put a short written processing agreement in your contract.
- **Security**: HTTPS (included), individual logins, strong passwords, no shared accounts, encrypted off-site backups, and no exporting member lists to personal chats.
- **Member rights**: members can ask to see, correct, or delete their data. Archive plus a delete option in the admin covers this.
- **Retention**: suggested policy is to delete or anonymize members inactive for 2 years **[GUESS, owner decides]**.
- **Breaches**: if data leaks, the NPC must be notified within 72 hours. Write down who calls whom.
- **NPC registration**: likely **not** required for a gym this size. Registration is generally for organizations with 250+ employees or those processing sensitive data of 1,000+ people **[GUESS, verify on privacy.gov.ph]**.

---

## 10. Later phases (not v1)

### Phase 2: reminders
| Option | Cost | Reality |
|---|---|---|
| **"Send reminder" button that opens the staff phone's SMS app with a prefilled message** (`sms:` link) | PHP 0 (uses the gym's load or unli-text) | **Recommended first.** No API, no approvals. A human taps send. |
| SMS API (Semaphore or another PH aggregator) | about PHP 0.50 to 1.00 per SMS **[GUESS]**. 300 members x 2 reminders/mo is about PHP 300 to 600/mo. | Needs the paid hosting plan for outbound access, sender name registration, and prepaid credits. |
| Facebook Messenger | Free per message | **Poor fit.** Pages can only message freely within 24 hours of the member's last message. Reminders outside that window need a qualifying message tag, and payment nagging usually does not qualify. It also needs a Meta app and app review. |

### Phase 3: QR check-in (do this before NFC)
- Each member gets a printed or laminated card with a QR code of their `member_code`: about PHP 5 to 20 per card **[GUESS]**.
- Scanning: the desk phone camera on a web page (free), or a USB/Bluetooth 2D barcode scanner at about PHP 800 to 2,000 **[GUESS]**.
- Adds a CheckIn table (member, time, staff). The scan screen shows a big green or red status.

### Phase 4: NFC (optional)
- USB NFC reader (ACR122U class) about PHP 1,500 to 3,000. NFC cards or keyfobs about PHP 15 to 50 each **[GUESS]**.
- Browser support is the weak point: Web NFC only works in Chrome on Android. A USB reader works like a keyboard, which is simpler.
- **Unrealistic for this project**: automatic turnstiles or door locks. They need hardware, installation, safety and liability work beyond a freelance web project.

---

## 11. Build order and milestones

| # | Milestone | Done when | Estimate **[GUESS]** |
|---|---|---|---|
| M0 | **Pitch mockup** | 3 to 4 screenshots or a clickable demo with fake members (dashboard, member list, renew). Show the owner **before** building more. | 1 weekend |
| M1 | Owner meeting | Open questions answered (Section 13). Plans and prices confirmed. Fee agreed. | 1 visit |
| M2 | Models and admin | Plan, Member, Membership and Payment work in the Django admin locally | 1 weekend |
| M3 | Staff screens | Dashboard, list, add, renew and log payment work on a phone | 1 to 2 weekends |
| M4 | Import | Import command tested on a 20-row sample | 1 evening |
| M5 | Deploy and backups | Live on PythonAnywhere Developer, daily backup task running, restore tested, staff accounts created | 1 weekend |
| M6 | Pilot | 2 weeks running alongside the notebook. Fix what staff complain about. | 2 weeks |
| M7 | Handover | Notebook retired. A one-page staff guide. Owner has the CSV export. | 1 day |

Rule: do not start M2 until the owner says yes at M1.

---

## 12. Pricing suggestion **[GUESS, adjust after M1]**

- **Upfront: PHP 8,000 to 12,000.** Suggested: **PHP 10,000**, covering the build, notebook import of up to 300 members, staff training and the 2-week pilot.
- **Monthly: PHP 1,200.** About PHP 600 is hosting, and the rest covers backups, bug fixes, and small changes (up to about 2 hours a month).
- Offer **the first month of upkeep free** during the pilot to lower the owner's risk.

**Reasoning:** if a monthly membership is around PHP 800 to 1,200 **[GUESS]**, the system pays for itself when it catches **one to two** forgotten renewals or late payments a month. With 50 to 100 visits a day, that is very likely. Do not price much lower: under PHP 1,000 a month you are paying to support the gym. Do not price much higher for a first client: you have no track record yet, and a Google Sheet is the free competitor.

**Contract must say:** hosting costs pass through at cost if the USD price changes, the owner owns the data, response time (e.g. same day during gym hours), and what counts as a new feature (billed separately).

---

## 13. Open questions for the gym owner

Answered on 2026-11-27 (see the update at the top): plans and prices, grace period, monthly end date, cash vs GCash split, staff per floor, walk-ins by name.

Still open:
1. **Prices:** please confirm the six prices. They were given from memory.
2. **"30 days":** does it mean the same date next month (25 Nov to 25 Dec, as built), or exactly 30 days?
3. **Students:** does staff check a student ID before giving the student price? If so, should the system record it?
4. **GCash:** is there one GCash number for the gym? Send the QR image from the GCash app (Receive > QR) to replace the demo one.
5. **Moving off the notebook:** are you OK with members typing their own details on the desk phone for about a month (see the move-over plan above)? How many active members are there right now?
6. **Desk devices:** what is on each floor's desk (phone, tablet, laptop)? Is the gym's Wi-Fi reliable on both floors?
7. **NFC:** would you buy a USB reader (about PHP 1,500 to 3,000 **[GUESS]**) and cards or keyfobs (about PHP 15 to 50 each **[GUESS]**)? Who pays for a lost card?
8. **Hosting and fee:** would you pay about PHP 1,200 a month for hosting and upkeep? This decides when the system goes online.

---

## 14. Sources checked
- PythonAnywhere free account features: https://help.pythonanywhere.com/pages/FreeAccountsFeatures/
- PythonAnywhere free account changes (2025-12-15, effective 2026-01-15): https://blog.pythonanywhere.com/221/
- PythonAnywhere new plans and pricing: https://blog.pythonanywhere.com/222/ and https://www.pythonanywhere.com/pricing/
