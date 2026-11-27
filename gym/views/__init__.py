"""
Front desk screens, one file per area:

    dashboard.py   home screen
    checkin.py     card tap / typed check-in (replaces the logbook)
    members.py     list, detail, add, renew
    payments.py    log payment, walk-ins, payment list
    signups.py     members type their own details; staff check them

Login is required for all of them (LoginRequiredMiddleware in settings).
"""
