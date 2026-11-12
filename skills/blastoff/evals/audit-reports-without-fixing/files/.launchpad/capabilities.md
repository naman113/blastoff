# Capabilities: Rota
Built from ../rota at commit 643a352 on 2026-11-12.

| Capability | What a user can do | Evidence | Status |
|---|---|---|---|
| Weekly rota from a template | A manager copies a template week into real shifts in one step | app/routes/shifts.py (create_week), web/pages/week.html, tests/test_shifts.py | Shipped |
| Double-booking prevention | Assigning someone to overlapping shifts is refused | app/routes/shifts.py (assign), tests/test_shifts.py | Shipped |
| My week view | Each staff member sees their own shifts | app/routes/shifts.py (my_week) | Shipped |
| Shift swaps with manager approval | Staff ask to swap; a manager approves and the shift is reassigned | app/routes/swaps.py, tests/test_swaps.py | Shipped |
| Text reminders | Everyone gets a text at 17:00 with tomorrow's shift | app/jobs/reminders.py (needs TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM) | Shipped |
| Payroll export | Download hours as a spreadsheet file | app/routes/export.py (returns the header only; calculation is a TODO) | Stub |
| Open shift claiming | Staff claim unfilled shifts themselves | app/flags.py (OPEN_SHIFT_BIDDING = False) | Hidden |

## Facts that help a sale
- Multi-clinic: yes (clinic_id on every model, app/models.py)
- Two roles: manager and staff (app/auth.py)
- Sign-in: email and password only; no single sign-on found
- Text messages go through Twilio; the clinic needs no app installed

## In the README but not found in code
- "AI demand forecasting"

## Not in this repo (stated by the owner)
- Set-up call to load the first rota
