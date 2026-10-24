"""Venue bookings (Diese) and the general ledger (MIP), built from the same world as Tessitura.

Both systems are derived from the Tessitura data, the way they are in real life:
  * Diese books the halls. Every Tessitura performance is a Diese event (with a
    load-in rehearsal and the show itself). Rentals by outside clients and internal
    rehearsals fill the rest of the calendar.
  * MIP is the ledger. Each day, Tessitura's ticket sales, subscriptions and gifts and
    Diese's rental fees are posted as one balanced journal per system. Payroll and other
    costs are posted at month end, so the ledger has a real income statement.

Planted exceptions, for the revenue-to-ledger reconciliation to catch (docs/adr/ADR-009):
  1. Year-end cut-off: gifts received on June 30 of the last fiscal year were posted two
     days later, so they landed in July: the next fiscal year.
  2. One unposted batch: one day's Tessitura journal never reached the ledger.
  3. A manual reclass in May of the last fiscal year moved $25,000 between funds
     (fund totals change, the overall total doesn't).
  4. A few rentals were invoiced, then cancelled in Diese; the ledger still has them.
Each is a one-time event, so the reconciliation shows a short list where every line has a story.

Cash and budget, so finance can run a cash flow and budget vs actual:
  * The ledger opens with a cash balance (Operating Cash against net assets).
  * Staff are paid biweekly, the most common US pay frequency: every other Friday, for the
    two weeks ending the Saturday before (paid in arrears). The ledger still books the
    month's salaries at month end (the accrual), so Accrued Payroll at month end is what
    staff have earned but not yet been paid. Supplier and artist bills (accounts payable)
    are paid 30 days after month end. Ticketing, gifts and rentals arrive as cash (rentals
    are prepaid). So cash = opening + receipts - payments.
  * Each fiscal year has an adopted budget (MIP's budget module), approved mid-June:
    last year's actuals by month, account, fund and department, plus planned growth.
    The first year, which has no prior year, is budgeted from its own activity.
Payments and the opening balance use their own journal numbers (JS/GS), so adding
them never renumbers an existing journal line.
Diese also has a few concert events with no Tessitura link, and a few bookings that end
before they start, for the data quality checks.

Everything is deterministic: the same seed and date always give the same rows.
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

# ----------------------------------------------------------------------------- reference data
# (room_id, name, room_type, tessitura venue_id or None, capacity, hourly rental rate)
ROOMS = [
    ("R01", "Main Hall", "Hall", "V01", 2800, 4500),
    ("R02", "Recital Hall", "Hall", "V02", 600, 1200),
    ("R03", "Studio Hall", "Hall", "V03", 270, 450),
    ("R04", "Rehearsal Studio A", "Rehearsal", None, 80, 120),
    ("R05", "Rehearsal Studio B", "Rehearsal", None, 60, 120),
    ("R06", "Rooftop Terrace", "Event Space", None, 200, 800),
]
RENTAL_CHANCE = {"R01": 0.20, "R02": 0.25, "R03": 0.25, "R04": 0.15, "R05": 0.15, "R06": 0.30}
CLIENTS = [  # fictional organisations: (name, type)
    ("Riverside Youth Orchestra", "Nonprofit"), ("Metro Choral Society", "Nonprofit"),
    ("Hudson Valley Conservatory", "Education"), ("Northwind Capital", "Corporate"),
    ("Lumen Pharmaceuticals", "Corporate"), ("Brightline Media Group", "Corporate"),
    ("East Side Ballet School", "Education"), ("City Gay Men's Chorus", "Nonprofit"),
    ("Okafor Family", "Private"), ("Delgado-Chen Wedding", "Private"),
    ("Atlas Film Festival", "Nonprofit"), ("Summit Law Partners", "Corporate"),
]
ENSEMBLES = ["Harmonia Chamber Players", "Harmonia Youth Ensemble", "Resident Jazz Trio", "Community Choir"]

GL_ACCOUNTS = [  # (code, name, type, group, normal balance)
    ("1010", "Operating Cash", "Asset", "Cash", "Debit"),
    ("1100", "Accounts Receivable", "Asset", "Receivables", "Debit"),
    ("2100", "Accounts Payable", "Liability", "Payables", "Credit"),
    ("2200", "Accrued Payroll", "Liability", "Payables", "Credit"),
    ("3100", "Net Assets Without Donor Restrictions", "Net Assets", "Net Assets", "Credit"),
    ("4100", "Single Ticket Revenue", "Revenue", "Earned Revenue", "Credit"),
    ("4110", "Subscription Revenue", "Revenue", "Earned Revenue", "Credit"),
    ("4200", "Contributions - Individuals", "Revenue", "Contributed Revenue", "Credit"),
    ("4300", "Venue Rental Revenue", "Revenue", "Earned Revenue", "Credit"),
    ("5100", "Artist Fees", "Expense", "Program Expenses", "Debit"),
    ("5200", "Salaries and Wages", "Expense", "Personnel", "Debit"),
    ("5300", "Venue Operations", "Expense", "Occupancy", "Debit"),
    ("5400", "Marketing and Advertising", "Expense", "Program Expenses", "Debit"),
    ("5500", "Education Program Costs", "Expense", "Program Expenses", "Debit"),
    ("5600", "General and Administrative", "Expense", "Management and General", "Debit"),
]
DEPARTMENTS = [
    ("100", "Artistic Programming"), ("200", "Development"), ("300", "Education"),
    ("400", "Marketing and Sales"), ("500", "Venue Operations and Rentals"), ("600", "Finance and Administration"),
]
# MIP fund codes. Finance keeps the Tessitura fund each one matches; Gold uses it to join the two.
GL_FUNDS = [  # (code, name, restriction, tessitura fund_id)
    ("GEN", "General Operating", "Without Donor Restrictions", "F01"),
    ("EDU", "Music Education", "With Donor Restrictions", "F02"),
    ("ART", "Artistic Excellence", "With Donor Restrictions", "F03"),
    ("END", "Endowment", "With Donor Restrictions - Perpetual", "F04"),
    ("ACC", "Community Access", "With Donor Restrictions", "F05"),
]
FUND_BY_TESSITURA = {f[3]: f[0] for f in GL_FUNDS}
OPENING_CASH = 12_000_000            # Operating Cash on the first day of the data
PAY_LAG_DAYS = {"AP": 30}           # bills booked at month end, paid this many days later
FIRST_PAYDAY = date(2023, 7, 14)    # a Friday; paydays repeat every 14 days
MONTHLY_PAYROLL = {"100": 520_000, "200": 240_000, "300": 180_000, "400": 210_000, "500": 300_000, "600": 260_000}


def ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def rooms() -> list[dict]:
    return [{"room_id": r[0], "room_name": r[1], "room_type": r[2], "venue_id": r[3], "capacity": r[4],
             "hourly_rate": r[5]} for r in ROOMS]


def gl_accounts() -> list[dict]:
    return [{"account_code": a[0], "account_name": a[1], "account_type": a[2], "account_group": a[3],
             "normal_balance": a[4], "is_active": True} for a in GL_ACCOUNTS]


def departments() -> list[dict]:
    return [{"department_code": d[0], "department_name": d[1]} for d in DEPARTMENTS]


def gl_funds() -> list[dict]:
    return [{"fund_code": f[0], "fund_name": f[1], "restriction": f[2], "tessitura_fund_id": f[3]} for f in GL_FUNDS]


def cutoff_day(end: date) -> date:
    """The most recent fiscal year end (June 30) on or before the load date."""
    return date(end.year if (end.month, end.day) >= (6, 30) else end.year - 1, 6, 30)


def unposted_batch_day(start: date) -> date:
    """The one day whose Tessitura journal never reached the ledger: the first Friday 600 days in."""
    d = start + timedelta(days=600)
    while d.weekday() != 4:
        d += timedelta(days=1)
    return d


# ----------------------------------------------------------------------------- Diese
class Diese:
    """The hall calendar. Each day's events are rebuilt from the date alone, so a daily run
    can find what was booked, cancelled or finished today without keeping state."""

    def __init__(self, seed: int, performances: list[dict]):
        self.seed = seed
        self.perfs_by_day: dict[date, list[dict]] = {}
        for p in performances:
            self.perfs_by_day.setdefault(datetime.fromisoformat(p["performance_datetime"]).date(), []).append(p)
        self.last_day = max(self.perfs_by_day)

    def day(self, d: date) -> list[tuple[dict, list[dict], dict]]:
        """Every event held on day d: (event, its bookings, hidden facts such as when it was booked)."""
        rng = random.Random(self.seed * 1_000_003 + d.toordinal())
        out, n = [], 0
        busy = set()

        def event_id():
            nonlocal n
            n += 1
            return f"E{d:%Y%m%d}{n:02d}"

        for p in self.perfs_by_day.get(d, []):
            room = next(r for r in ROOMS if r[3] == p["venue_id"])
            busy.add(room[0])
            show = datetime.fromisoformat(p["performance_datetime"])
            eid = event_id()
            linked = rng.random() >= 0.015                       # bad data: no link to the Tessitura performance
            booked = datetime.combine(d - timedelta(days=rng.randint(200, 320)), time(10, 0))
            ev = {"event_id": eid, "event_name": p["title"], "event_type": "Concert",
                  "client_name": "Harmonia Hall Presents", "client_type": "Internal",
                  "tessitura_performance_id": p["performance_id"] if linked else None,
                  "event_date": d.isoformat(), "status": "Cancelled" if p["status"] == "Cancelled" else "Confirmed",
                  "created_at": ts(booked)}
            bookings = [
                self._booking(eid, 1, room[0], datetime.combine(d, time(10, 0)), 3, "Rehearsal", 0, rng),
                self._booking(eid, 2, room[0], show - timedelta(hours=1), 3.5, "Performance", 0, rng),
            ]
            out.append((ev, bookings, {"booked": booked, "cancelled": None, "posted_then_cancelled": False}))

        for r in ROOMS:
            if r[0] in busy:
                continue
            if r[2] == "Rehearsal" and rng.random() < 0.5:     # internal rehearsal, no fee
                eid = event_id()
                booked = datetime.combine(d - timedelta(days=rng.randint(7, 60)), time(9, 0))
                ev = {"event_id": eid, "event_name": f"{rng.choice(ENSEMBLES)} rehearsal", "event_type": "Rehearsal",
                      "client_name": "Harmonia Hall", "client_type": "Internal", "tessitura_performance_id": None,
                      "event_date": d.isoformat(), "status": "Confirmed", "created_at": ts(booked)}
                start = datetime.combine(d, time(rng.choice([9, 13, 17]), 0))
                out.append((ev, [self._booking(eid, 1, r[0], start, 3, "Rehearsal", 0, rng)],
                            {"booked": booked, "cancelled": None, "posted_then_cancelled": False}))
            elif rng.random() < RENTAL_CHANCE[r[0]]:              # rental by an outside client
                eid = event_id()
                client, ctype = rng.choice(CLIENTS)
                booked = datetime.combine(d - timedelta(days=rng.randint(14, 240)), time(rng.randint(9, 17), 0))
                hours = rng.choice([4, 4, 5, 6])
                start = datetime.combine(d, time(rng.choice([10, 14, 18]), 0))
                fee = round(hours * r[5] * rng.uniform(0.9, 1.1), 2)
                cancelled = None
                status = "Confirmed"
                if rng.random() < 0.04:
                    status = "Cancelled"
                    cancelled = booked + timedelta(days=rng.randint(1, max(1, (d - booked.date()).days - 1)))
                elif (d - booked.date()).days > 150 and rng.random() < 0.3:
                    status = "Tentative"                          # a hold the client hasn't confirmed yet
                # Planted: cancelled a few days before the event, but finance had already invoiced it
                # and never voided the invoice, so the ledger still shows the revenue.
                posted_then_cancelled = status == "Cancelled" and rng.random() < 0.05
                if posted_then_cancelled:
                    cancelled = datetime.combine(d - timedelta(days=rng.randint(1, 5)), time(11, 0))
                occasion = rng.choice(["Concert", "Gala", "Graduation", "Conference", "Recital", "Reception"])
                ev = {"event_id": eid, "event_name": f"{client}: {occasion}",
                      "event_type": "Rental", "client_name": client, "client_type": ctype, "tessitura_performance_id": None,
                      "event_date": d.isoformat(), "status": status, "created_at": ts(booked)}
                b = self._booking(eid, 1, r[0], start, hours, "Event", fee, rng)
                out.append((ev, [b], {"booked": booked, "cancelled": cancelled, "posted_then_cancelled": posted_then_cancelled}))
        return out

    def _booking(self, eid, n, room_id, start: datetime, hours: float, kind: str, fee: float, rng) -> dict:
        end = start + timedelta(hours=hours)
        if rng.random() < 0.003 and fee == 0:
            end = start - timedelta(hours=1)                     # bad data: ends before it starts (internal bookings only,
                                                                 # so the rental reconciliation shows only the planted exceptions)
        return {"booking_id": f"{eid}-{n}", "event_id": eid, "room_id": room_id, "booking_type": kind,
                "start_datetime": ts(start), "end_datetime": ts(end), "rental_fee": fee}

    @staticmethod
    def as_of(ev: dict, bookings: list[dict], facts: dict, d: date, as_of: date):
        """The event and bookings the way Diese shows them on as_of, or None if not booked yet."""
        if facts["booked"].date() > as_of:
            return None
        ev = dict(ev)
        changed = facts["booked"]
        if facts["cancelled"] and facts["cancelled"].date() <= as_of:
            ev["status"], changed = "Cancelled", facts["cancelled"]
        elif ev["status"] == "Cancelled" and facts["cancelled"] is None:
            pass                                                  # a cancelled concert, cancelled when booked
        else:
            ev["status"] = "Confirmed" if ev["status"] == "Cancelled" else ev["status"]   # not cancelled yet
            if d < as_of:
                ev["status"], changed = "Completed", datetime.combine(d + timedelta(days=1), time(6, 0))
        ev["updated_at"] = ts(changed)
        bks = [{**b, "updated_at": ts(facts["booked"])} for b in bookings]
        return ev, bks

    def snapshot(self, start: date, as_of: date):
        """Full load: every event booked by as_of, from start to the end of the current season."""
        events, bookings = [], []
        for n in range((self.last_day - start).days + 1):
            d = start + timedelta(days=n)
            for ev, bks, facts in self.day(d):
                got = self.as_of(ev, bks, facts, d, as_of)
                if got:
                    events.append(got[0])
                    bookings += got[1]
        return events, bookings

    def changes_on(self, today: date):
        """Daily load: events booked, cancelled or finished today."""
        events, bookings = [], []
        for n in range(-1, 241):
            d = today + timedelta(days=n)
            for ev, bks, facts in self.day(d):
                booked_today = facts["booked"].date() == today
                cancelled_today = facts["cancelled"] is not None and facts["cancelled"].date() == today
                finished_today = d == today - timedelta(days=1) and facts["booked"].date() < today
                if booked_today or cancelled_today or finished_today:
                    got = self.as_of(ev, bks, facts, d, today)
                    if got:
                        events.append(got[0])
                        bookings += got[1]
        return events, bookings

    def rental_revenue(self, d: date) -> list[tuple[str, float]]:
        """Rental fees invoiced on day d: rentals held that day, plus the planted ones cancelled after invoicing."""
        out = []
        for ev, bks, facts in self.day(d):
            if ev["event_type"] != "Rental":
                continue
            if ev["status"] in ("Confirmed", "Tentative") or facts["posted_then_cancelled"]:
                out.append((ev["event_id"], round(sum(b["rental_fee"] for b in bks), 2)))
        return out

    def booked_hours(self, d: date) -> float:
        return sum((datetime.fromisoformat(b["end_datetime"]) - datetime.fromisoformat(b["start_datetime"])).total_seconds() / 3600
                   for ev, bks, _ in self.day(d) if ev["status"] != "Cancelled" for b in bks
                   if b["end_datetime"] > b["start_datetime"])


# ----------------------------------------------------------------------------- MIP
class Ledger:
    """Builds balanced journals. Every journal's debits equal its credits."""

    def __init__(self, state, backfill_at: datetime | None = None):
        self.st = state
        self.rows: list[dict] = []
        # Payments and the opening balance were back-filled into MIP when finance started recording
        # them, so on the first load their updated_at is the backfill time, not the payment date.
        # That keeps them after every watermark the Copy job and Silver already hold.
        self.backfill_at = backfill_at

    def journal(self, session: str, source: str, eff: date, posted: datetime, lines: list[tuple], ref: str,
                settlement: bool = False):
        """lines: (account, fund, department, amount, description). Positive = credit, negative = debit.
        A cash (or payable) line is added to balance the journal. Settlement journals (payments,
        the opening balance) are already balanced and use their own JS/GS numbers."""
        lines = [ln for ln in lines if round(ln[3], 2) != 0]
        if not lines:
            return
        total = round(sum(ln[3] for ln in lines), 2)
        if not settlement:
            offset_acct = "1010" if source in ("TESSITURA", "DIESE") else ("2200" if source == "PAYROLL" else "2100")
            if total != 0:
                lines = lines + [(offset_acct, "GEN", "600", -total, f"{source} {ref} offset")]
            if source in PAY_LAG_DAYS and total != 0:            # owed until paid (see settle_due)
                due = (eff + timedelta(days=PAY_LAG_DAYS[source])).isoformat()
                open_items = self.st.open_payables.setdefault(due, [])
                open_items.append([source, offset_acct, round(-total, 2), ref])
        if settlement:
            self.st.settle_journals += 1
            jid = f"JS{self.st.settle_journals:06d}"
        else:
            self.st.journals += 1
            jid = f"J{self.st.journals:07d}"
        for n, (acct, fund, dept, amt, desc) in enumerate(lines, start=1):
            if settlement:
                self.st.settle_lines += 1
                line_id = f"GS{self.st.settle_lines:08d}"
            else:
                self.st.gl_lines += 1
                line_id = f"GL{self.st.gl_lines:09d}"
            amt = round(amt, 2)
            self.rows.append({
                "gl_transaction_id": line_id, "journal_id": jid, "line_number": n,
                "session_id": session, "source_module": source, "effective_date": eff.isoformat(),
                "posted_at": ts(posted), "account_code": acct, "fund_code": fund, "department_code": dept,
                "debit_amount": -amt if amt < 0 else 0.0, "credit_amount": amt if amt > 0 else 0.0,
                "description": desc, "reference": ref,
                "updated_at": ts(self.backfill_at if settlement and self.backfill_at else posted)})


def post_opening_balance(ledger: Ledger, start: date):
    """The ledger's opening position: cash on hand, held as unrestricted net assets."""
    ledger.journal("OPEN-BAL", "OPENING", start, datetime.combine(start, time(0, 5)),
                   [("1010", "GEN", "600", -OPENING_CASH, "Opening cash balance"),
                    ("3100", "GEN", "600", OPENING_CASH, "Opening net assets")],
                   "Opening balance", settlement=True)


def monthly_payroll(month_end: date) -> float:
    """The month's salaries, exactly as post_month_end books them (same seed, same draws)."""
    rng = random.Random(month_end.toordinal() * 7)
    return sum(round(amt * rng.uniform(0.97, 1.04), 2) for amt in MONTHLY_PAYROLL.values())


def _month_end(d: date) -> date:
    nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return nxt - timedelta(days=1)


def settle_due(ledger: Ledger, d: date, start: date):
    """Pay what falls due today: the biweekly payroll, and bills 30 days after month end."""
    if d >= FIRST_PAYDAY and (d - FIRST_PAYDAY).days % 14 == 0:
        first, last = d - timedelta(days=19), d - timedelta(days=6)        # Sunday to Saturday, two weeks
        wages = 0.0
        for i in range((last - first).days + 1):
            day = first + timedelta(days=i)
            if day >= start:                                                 # nothing was earned before the data starts
                eom = _month_end(day)
                wages += monthly_payroll(eom) / eom.day
        wages = round(wages, 2)
        if wages:
            ledger.journal(f"PAYRUN-{d:%Y%m%d}", "PAYROLL_PAYMENT", d, datetime.combine(d, time(9, 0)),
                           [("2200", "GEN", "600", -wages, "Biweekly payroll"), ("1010", "GEN", "600", wages, "Biweekly payroll")],
                           f"Payroll for {first:%b %d} to {last:%b %d %Y}", settlement=True)
    for due in sorted(k for k in ledger.st.open_payables if k <= d.isoformat()):
        for _source, liability, amount, ref in ledger.st.open_payables.pop(due):
            ledger.journal(f"AP_PAYMENT-{d:%Y%m%d}", "AP_PAYMENT", d, datetime.combine(d, time(15, 0)),
                           [(liability, "GEN", "600", -amount, "Suppliers and artists paid"),
                            ("1010", "GEN", "600", amount, "Suppliers and artists paid")],
                           f"Payment of {ref}", settlement=True)


def budget_rows(gl_rows: list[dict], start: date, end: date, seed: int) -> list[dict]:
    """The adopted budget for each fiscal year in the data, by month, account, fund and department.
    Amounts are positive for revenue and expense alike (account_type says which)."""
    types = {a[0]: a[2] for a in GL_ACCOUNTS}
    actual: dict = {}                                   # (fy, month, account, fund, dept) -> natural amount
    for r in gl_rows:
        kind = types.get(r["account_code"])
        if kind not in ("Revenue", "Expense"):
            continue
        eff = date.fromisoformat(r["effective_date"])
        fy = eff.year + (1 if eff.month >= 7 else 0)
        amt = r["credit_amount"] - r["debit_amount"]
        amt = amt if kind == "Revenue" else -amt
        key = (fy, eff.month, r["account_code"], r["fund_code"], r["department_code"])
        actual[key] = actual.get(key, 0.0) + amt
    first_fy = start.year + (1 if start.month >= 7 else 0)
    last_fy = end.year + (1 if end.month >= 7 else 0)
    rows, n = [], 0
    for fy in range(first_fy, last_fy + 1):
        base_fy = fy - 1 if fy > first_fy else fy           # incremental budgeting: last year's actuals
        rng = random.Random(seed * 31 + fy)
        growth = {}
        for code, kind in types.items():
            if kind == "Revenue":
                growth[code] = rng.uniform(0.94, 1.06) if fy == first_fy else rng.uniform(1.02, 1.09)
            elif kind == "Expense":
                growth[code] = rng.uniform(0.97, 1.03) if fy == first_fy else rng.uniform(1.01, 1.05)
        approved = datetime(fy - 1, 6, 15, 10, 0)
        for (bfy, month, acct, fund, dept), amt in sorted(actual.items()):
            if bfy != base_fy or amt <= 0:
                continue
            value = round(amt * growth[acct] * rng.uniform(0.97, 1.03), -2)
            n += 1
            rows.append({"budget_line_id": f"B{fy}{n:06d}", "fiscal_year": fy, "budget_version": "Adopted",
                         "period_start": date(fy - 1 if month >= 7 else fy, month, 1).isoformat(),
                         "account_code": acct, "fund_code": fund, "department_code": dept,
                         "amount": value, "approved_at": ts(approved), "updated_at": ts(approved)})
    return rows


def post_day(ledger: Ledger, diese: Diese, d: date, sales: float, returns: float, subs: float,
             gifts_by_fund: dict, start: date, skip_unposted: bool = True):
    """Post one day's Tessitura and Diese activity. Tessitura posts the next morning."""
    posted = datetime.combine(d + timedelta(days=1), time(6, 30))
    if not (skip_unposted and d == unposted_batch_day(start)):
        lines = [("4100", "GEN", "400", sales, "Ticket sales"), ("4100", "GEN", "400", -returns, "Ticket returns"),
                 ("4110", "GEN", "400", subs, "Subscription packages")]
        lines += [("4200", f, "200", amt, "Contributions") for f, amt in sorted(gifts_by_fund.items())]
        ledger.journal(f"TESS-{d:%Y%m%d}", "TESSITURA", d, posted, lines, f"Tessitura posting {d}")
    rentals = diese.rental_revenue(d)
    if rentals:
        ledger.journal(f"DIESE-{d:%Y%m%d}", "DIESE", d, posted,
                       [("4300", "GEN", "500", fee, f"Rental {eid}") for eid, fee in rentals], f"Diese invoices {d}")


def post_cutoff_gifts(ledger: Ledger, d: date, gifts_by_fund: dict):
    """Year-end cut-off: gifts received on June 30 are posted with an effective date two days later."""
    eff = d + timedelta(days=2)
    ledger.journal(f"TESS-{d:%Y%m%d}-LATE", "TESSITURA", eff, datetime.combine(eff, time(9, 0)),
                   [("4200", f, "200", amt, "Contributions received at year end") for f, amt in sorted(gifts_by_fund.items())],
                   f"Tessitura late posting {d}")


def post_month_end(ledger: Ledger, diese: Diese, month_end: date, n_perfs: int, ta_hours: float, ad_spend: float,
                   reclass_month: date | None = None):
    """Payroll and operating costs, posted on the last day of the month."""
    rng = random.Random(month_end.toordinal() * 7)
    posted = datetime.combine(month_end, time(18, 0))
    ledger.journal(f"PAY-{month_end:%Y%m}", "PAYROLL", month_end, posted,
                   [("5200", "GEN", dept, -round(amt * rng.uniform(0.97, 1.04), 2), "Monthly payroll")
                    for dept, amt in MONTHLY_PAYROLL.items()], f"Payroll {month_end:%Y-%m}")
    hours = sum(diese.booked_hours(month_end.replace(day=1) + timedelta(days=i)) for i in range(month_end.day))
    ledger.journal(f"AP-{month_end:%Y%m}", "AP", month_end, posted, [
        ("5100", "GEN", "100", -round(n_perfs * rng.uniform(32_000, 48_000), 2), "Artist fees"),
        ("5300", "GEN", "500", -round(hours * 140 + 150_000, 2), "Venue operations"),
        ("5400", "GEN", "400", -round(ad_spend + 15_000, 2), "Marketing and advertising"),
        ("5500", "EDU", "300", -round(ta_hours * 95, 2), "Teaching artists"),
        ("5600", "GEN", "600", -round(rng.uniform(180_000, 240_000), 2), "General and administrative"),
    ], f"Payables {month_end:%Y-%m}")
    if month_end == reclass_month:                                # planted: reclass between funds
        ledger.journal(f"ADJ-{month_end:%Y%m}", "MANUAL", month_end, posted,
                       [("4200", "GEN", "200", -25_000, "Reclass: gift restricted by donor letter"),
                        ("4200", "ART", "200", 25_000, "Reclass: gift restricted by donor letter")],
                       f"Manual reclass {month_end:%Y-%m}")
