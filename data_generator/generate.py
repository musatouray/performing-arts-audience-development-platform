"""Generates fake source data for the platform.

It imitates four source systems. Each one ends up somewhere different,
the same way it would in real life (see docs/adr/ADR-003-ingestion-tools.md):

  data/ticketing_db/        CSV extracts that scripts/11_load_ticketing_db.py loads
                            into your SQL Server database (the mock Tessitura).
                            A Fabric Copy job then copies changes into Bronze.
  data/fundraising_api/     A read-only JSON API with paging. Publish this folder
                            on GitHub Pages; the nb_05 notebook calls it.
  data/education_sharepoint/ Excel workbooks. Upload them to a SharePoint
                            document library; a Dataflow Gen2 reads them.
  data/marketing_adls/      CSV exports. Upload them to an ADLS Gen2 container;
                            a OneLake shortcut makes them visible in lh_bronze.

Folder-based outputs keep one folder per day (load_date=YYYY-MM-DD) and a
_manifests/ file with row counts, used to check nothing went missing.

Modes:
  full         about three years of history in one load
  incremental  one day of new and changed rows

Some bad data is added on purpose so the data quality checks have something to
catch: duplicate patrons, bad emails and zip codes, unknown performances,
negative prices, gifts dated in the future, sessions with no participants,
clicks sent twice, overlapping API pages and negative ad spend.

Run: uv run python -m data_generator.generate full
(the Excel files need openpyxl, which uv installs with the project)
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path

from data_generator import reference as ref
from data_generator.writers import write_all

DEFAULT_OUT = Path("data")
STATE_FILE = Path("data/state.json")


# ----------------------------------------------------------------------------- helpers
def fiscal_year(d: date) -> int:
    """Fiscal year runs July to June. FY2026 is July 2025 to June 2026."""
    return d.year + 1 if d.month >= 7 else d.year


def weighted(rng: random.Random, pairs):
    """Pick a value at random, using the weights."""
    values, weights = zip(*pairs)
    return rng.choices(values, weights=weights, k=1)[0]


def ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def daterange(start: date, end: date):
    for n in range((end - start).days + 1):
        yield start + timedelta(days=n)


@dataclass
class State:
    """Saved between runs so new IDs don't clash with ones already generated."""
    seed: int = 42
    start: str = "2023-07-01"
    end: str = "2026-09-27"
    customers: int = 0
    donors: int = 0
    orders: int = 0
    order_lines: int = 0
    gifts: int = 0
    subscriptions: int = 0
    enrollments: int = 0
    last_load_date: str = ""
    recent_campaigns: dict = field(default_factory=dict)  # recent email campaigns and the list size when sent

    def save(self, path: Path = STATE_FILE):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.__dict__, indent=2))

    @classmethod
    def load(cls, path: Path = STATE_FILE) -> "State":
        saved = json.loads(path.read_text())
        return cls(**{k: v for k, v in saved.items() if k in cls.__dataclass_fields__})


# ----------------------------------------------------------------------------- entities
class Universe:
    """The fixed "world" the data comes from: seasons, venues, shows, programs and people.

    A person can be rebuilt from their ID alone, so a daily run can send an
    updated record for an existing customer without keeping a copy of them all.
    """

    def __init__(self, seed: int, start: date, end: date):
        self.seed, self.start, self.end = seed, start, end
        self.rng = random.Random(seed)
        self.seasons = self._seasons()
        self.performances = self._performances()
        self.perf_by_id = {p["performance_id"]: p for p in self.performances}

    # -- reference -----------------------------------------------------------
    def _seasons(self):
        out = []
        for fy in range(fiscal_year(self.start), fiscal_year(self.end) + 1):   # up to the season on sale now
            out.append({
                "season_id": f"S{fy}", "season_name": f"{fy - 1}-{str(fy)[2:]} Season", "fiscal_year": fy,
                "start_date": date(fy - 1, 9, 15).isoformat(), "end_date": date(fy, 6, 15).isoformat(),
            })
        return out

    def venues(self):
        return [{"venue_id": v[0], "venue_name": v[1], "capacity": v[2]} for v in ref.VENUES]

    def _performances(self):
        rng = random.Random(self.seed + 7)
        venue_cap = {v[0]: v[2] for v in ref.VENUES}
        perfs, n = [], 0
        for s in self.seasons:
            d0, d1 = date.fromisoformat(s["start_date"]), date.fromisoformat(s["end_date"])
            for d in daterange(d0, d1):
                if d.month in (7, 8):
                    continue
                for _ in range(rng.choices([0, 1, 2], [40, 48, 12])[0]):   # about 0.7 shows a day
                    n += 1
                    series = rng.choice(list(ref.SERIES))
                    genre, venues, pop_rng, _ = ref.SERIES[series]
                    venue = rng.choice(venues)
                    hour = 14 if series == "Family Concerts" else rng.choice([19, 20])
                    perfs.append({
                        "performance_id": f"P{n:06d}", "season_id": s["season_id"], "venue_id": venue,
                        "title": f"{rng.choice(ref.ARTISTS)}: {rng.choice(ref.WORKS)}",
                        "series": series, "genre": genre,
                        "performance_datetime": ts(datetime.combine(d, time(hour, rng.choice([0, 30])))),
                        "capacity": int(venue_cap[venue] * rng.choice([1, 1, 1, 0.92])),
                        "status": "Cancelled" if rng.random() < 0.01 else "Scheduled",
                        "_popularity": round(rng.uniform(*pop_rng), 3),
                    })
        return perfs

    def performances_snapshot(self, as_of: date):
        out = []
        for p in self.performances:
            row = {k: v for k, v in p.items() if not k.startswith("_")}
            if row["status"] != "Cancelled" and datetime.fromisoformat(row["performance_datetime"]).date() < as_of:
                row["status"] = "Completed"
            row["updated_at"] = ts(datetime.combine(as_of, time(1, 0)))
            out.append(row)
        return out

    def campaigns(self):
        out = []
        for s in self.seasons:
            for i, (name, ctype, goal) in enumerate(ref.CAMPAIGNS, start=1):
                out.append({"campaign_id": f"C{s['fiscal_year']}{i}", "campaign_name": f"FY{s['fiscal_year']} {name}",
                            "campaign_type": ctype, "fiscal_year": s["fiscal_year"], "goal_amount": goal})
        return out

    def funds(self):
        return [{"fund_id": f[0], "fund_name": f[1], "is_restricted": f[2]} for f in ref.FUNDS]

    def programs(self):
        return [{"program_id": p[0], "program_name": p[1], "program_type": p[2], "audience": p[3]} for p in ref.PROGRAMS]

    def schools(self):
        rng = random.Random(self.seed + 11)
        kinds = ["P.S.", "I.S.", "M.S.", "High School for", "Academy of"]
        themes = ["the Arts", "Music & Media", "Leadership", "Science", "Humanities", "Global Studies"]
        out = []
        for i in range(1, 151):
            kind = rng.choice(kinds)
            name = f"{kind} {rng.randint(1, 499)}" if kind in ("P.S.", "I.S.", "M.S.") else f"{kind} {rng.choice(themes)}"
            out.append({"school_id": f"SCH{i:03d}", "school_name": name,
                        "borough": weighted(rng, ref.BOROUGHS), "is_title_i": rng.random() < 0.7})
        return out

    # -- people ----------------------------------------------------------------
    def _person(self, pid: int, salt: int):
        rng = random.Random(self.seed * 1_000_003 + pid * 31 + salt)
        first, last = rng.choice(ref.FIRST_NAMES), rng.choice(ref.LAST_NAMES)
        city, state, zip3, _ = rng.choices(ref.CITIES, weights=[c[3] for c in ref.CITIES])[0]
        email = f"{first}.{last}{rng.randint(1, 999)}@{rng.choice(ref.EMAIL_DOMAINS)}".lower()
        return rng, {
            "first_name": first, "last_name": last, "email": email,
            "phone": f"({rng.randint(201, 989)}) {rng.randint(200, 999)}-{rng.randint(1000, 9999)}",
            "address_line1": f"{rng.randint(1, 999)} {rng.choice(ref.STREETS)}",
            "city": city, "state": state, "postal_code": f"{zip3}{rng.randint(1, 99):02d}", "country": "USA",
        }

    def customer(self, cid: int, created: date, version: int = 0):
        """A ticket buyer. About 3% are the same person as an earlier buyer, under a new ID."""
        rng, p = self._person(cid, salt=1)
        if cid > 60 and rng.random() < 0.03:                        # bad data: same person, new ID
            _, p = self._person(cid - rng.randint(1, 50), salt=1)
            p["email"] = rng.choice([p["email"].upper(), f"  {p['email']} ", p["email"].title()])
        if rng.random() < 0.01:
            p["email"] = ""                                          # bad data: missing email
        if rng.random() < 0.005:
            p["postal_code"] = rng.choice(["N/A", p["postal_code"][:4]])  # bad data: invalid zip code
        if version:                                                  # the patron moved (creates address history)
            vr = random.Random(self.seed + cid * 97 + version)
            city, state, zip3, _ = vr.choices(ref.CITIES, weights=[c[3] for c in ref.CITIES])[0]
            p.update(address_line1=f"{vr.randint(1, 999)} {vr.choice(ref.STREETS)}", city=city, state=state,
                     postal_code=f"{zip3}{vr.randint(1, 99):02d}")
        created_dt = datetime.combine(created, time(rng.randint(8, 21), rng.randint(0, 59)))
        return {"customer_id": f"T{cid:07d}", **p,
                "customer_type": weighted(rng, [("Individual", 90), ("Household", 8), ("Organization", 2)]),
                "email_opt_in": rng.random() < 0.65,
                "created_at": ts(created_dt), "updated_at": ts(created_dt)}

    def donor(self, did: int, since: date, max_customer: int):
        """A donor. About 60% also buy tickets, but have a different ID in the fundraising system."""
        rng = random.Random(self.seed * 7_919 + did)
        if max_customer > 0 and rng.random() < 0.6:
            c = self.customer(rng.randint(1, max_customer), since)
            p = {k: c[k] for k in ("first_name", "last_name", "email", "city", "state", "postal_code")}
            if rng.random() < 0.15:
                p["email"] = ""                                      # no email, so matching has to use name and zip
            elif rng.random() < 0.3:
                p["email"] = p["email"].upper()
        else:
            _, full = self._person(900_000 + did, salt=2)
            p = {k: full[k] for k in ("first_name", "last_name", "email", "city", "state", "postal_code")}
        return {"donor_id": f"D{did:06d}", **p, "donor_since": since.isoformat(),
                "updated_at": ts(datetime.combine(since, time(9, 0)))}


# ----------------------------------------------------------------------------- generator
class Generator:
    def __init__(self, state: State):
        self.st = state
        self.u = Universe(state.seed, date.fromisoformat(state.start), date.fromisoformat(state.end))
        self.sold: dict[str, int] = {}          # seats sold per show, so no show is oversold

    # -- ticket sales ---------------------------------------------------------
    # Each show has a popularity score that sets how full it gets. Tickets go on
    # sale 120 days before the show, and most sell in the last few weeks.
    SALES_WINDOW = 120
    AVG_TICKETS_PER_ORDER = 2.4

    def _target_tickets(self, perf) -> int:
        return int(perf["capacity"] * min(0.99, perf["_popularity"]))

    def _sell(self, perf, order_dt: datetime, rng: random.Random, orders, lines):
        """Create one order, with one or two lines, for a show."""
        if self.sold.get(perf["performance_id"], 0) >= perf["capacity"]:
            return 0                                                  # sold out
        if self.st.customers < 50 or rng.random() < 0.30:            # about 30% of orders come from new buyers
            self.st.customers += 1
            cust_id = self.st.customers
            self._new_customers.append(self.u.customer(cust_id, order_dt.date()))
        else:
            cust_id = rng.randint(1, self.st.customers)
        self.st.orders += 1
        returned = rng.random() < 0.02
        orders.append({
            "order_id": f"O{self.st.orders:08d}", "customer_id": f"T{cust_id:07d}", "order_datetime": ts(order_dt),
            "channel": weighted(rng, ref.CHANNELS), "status": "Returned" if returned else "Complete",
            "updated_at": ts(order_dt + timedelta(days=rng.randint(1, 5)) if returned else order_dt),
        })
        zones = next(v[3] for v in ref.VENUES if v[0] == perf["venue_id"])
        mult = ref.SERIES[perf["series"]][3]
        sold = 0
        for zone in rng.sample(list(zones), k=min(len(zones), rng.choices([1, 2], [85, 15])[0])):
            self.st.order_lines += 1
            seats_left = perf["capacity"] - self.sold.get(perf["performance_id"], 0)
            qty = min(seats_left, rng.choices([1, 2, 3, 4, 6], [20, 50, 10, 15, 5])[0])
            if qty <= 0:
                break
            self.sold[perf["performance_id"]] = self.sold.get(perf["performance_id"], 0) + qty
            sold += qty
            is_comp = rng.random() < 0.03
            price = 0 if is_comp else round(zones[zone] * mult * rng.uniform(0.9, 1.15), 2)
            perf_id = perf["performance_id"]
            if rng.random() < 0.002:
                perf_id = "P999999"                                   # bad data: performance that doesn't exist
            if rng.random() < 0.001:
                price = -price                                        # bad data: negative price
            lines.append({
                "order_line_id": f"L{self.st.order_lines:09d}", "order_id": f"O{self.st.orders:08d}",
                "performance_id": perf_id, "price_zone": zone, "quantity": qty, "unit_price": price,
                "discount_amount": round(price * qty * rng.choice([0.1, 0.15, 0.2]), 2) if rng.random() < 0.1 and price > 0 else 0,
                "is_comp": is_comp, "updated_at": ts(order_dt),
            })
        return sold

    def _history_sales(self, start: date, end: date, rng: random.Random, orders, lines):
        """Full load: create every order for every show in the date range, in time order."""
        events = []
        for perf in self.u.performances:
            if perf["status"] == "Cancelled":
                continue
            show = datetime.fromisoformat(perf["performance_datetime"])
            if show.date() - timedelta(days=self.SALES_WINDOW) > end:
                continue
            remaining = self._target_tickets(perf)
            while remaining > 0:
                days_out = int(self.SALES_WINDOW * rng.betavariate(1.1, 2.6))   # most sales close to show date
                day = show.date() - timedelta(days=max(1, days_out))
                remaining -= self.AVG_TICKETS_PER_ORDER
                if start <= day <= end:
                    events.append((datetime.combine(day, time(rng.randint(7, 23), rng.randint(0, 59), rng.randint(0, 59))), perf))
        events.sort(key=lambda e: e[0])
        for order_dt, perf in events:
            self._sell(perf, order_dt, rng, orders, lines)

    def _orders_for_day(self, d: date, rng: random.Random, orders, lines):
        """Daily load: today's orders for each show on sale."""
        for perf in self.u.performances:
            if perf["status"] == "Cancelled":
                continue
            days_out = (datetime.fromisoformat(perf["performance_datetime"]).date() - d).days
            if not 0 < days_out <= self.SALES_WINDOW:
                continue
            x = days_out / self.SALES_WINDOW
            share = (1 - x) ** 1.6 * 2.6 / self.SALES_WINDOW               # share of a show's sales that happen today
            expected = self._target_tickets(perf) / self.AVG_TICKETS_PER_ORDER * share
            for _ in range(int(expected) + (rng.random() < expected % 1)):
                self._sell(perf, datetime.combine(d, time(rng.randint(7, 23), rng.randint(0, 59))), rng, orders, lines)

    # -- subscriptions for one season -----------------------------------------
    def _subscriptions(self, season, prev_subscribers: set, rng, window: tuple[date, date]):
        subs, current = [], set()
        n_new = rng.randint(900, 1300)
        renewers = [c for c in prev_subscribers if rng.random() < 0.68]   # about 68% renew
        new = [rng.randint(1, max(1, self.st.customers)) for _ in range(n_new)]
        for cust, is_renewal in [(c, True) for c in renewers] + [(c, False) for c in new]:
            if cust in current:
                continue
            current.add(cust)
            pkg, seats_per, amount = rng.choice(ref.SUBSCRIPTION_PACKAGES)
            seats = rng.choice([1, 2, 2, 2, 4])
            day = window[0] + timedelta(days=rng.randint(0, (window[1] - window[0]).days))
            self.st.subscriptions += 1
            subs.append({
                "subscription_id": f"SUB{self.st.subscriptions:07d}", "customer_id": f"T{cust:07d}",
                "season_id": season["season_id"], "package_name": pkg, "seats": seats,
                "package_amount": round(amount * seats * rng.uniform(0.95, 1.05), 2), "is_renewal": is_renewal,
                "purchased_at": ts(datetime.combine(day, time(rng.randint(8, 22), rng.randint(0, 59)))),
            })
        return subs, current

    # -- gifts ----------------------------------------------------------------
    def _gift(self, donor_num: int, gdate: date, rng: random.Random, campaigns_by_fy, as_of: date):
        self.st.gifts += 1
        fy = fiscal_year(gdate)
        camp = rng.choice(campaigns_by_fy.get(fy, campaigns_by_fy[max(campaigns_by_fy)]))
        if "Gala" in camp["campaign_name"]:
            amount = rng.choice([1_500, 2_500, 5_000, 10_000, 25_000])
        else:
            amount = round(min(math.exp(rng.gauss(5.0, 1.3)), 250_000), 2)   # most gifts are $50-$500, a few are much larger
        gift_type = weighted(rng, ref.GIFT_TYPES)
        if rng.random() < 0.004:
            gift_type, amount = "Reversal", -amount                   # a real refund, not an error
        donor_id = f"D{donor_num:06d}"
        if rng.random() < 0.002:
            donor_id = "D999999"                                      # bad data: donor that doesn't exist
        if rng.random() < 0.003:
            gdate = as_of + timedelta(days=30)                        # bad data: gift dated in the future
        fund = "F02" if "Education" in camp["campaign_name"] else "F04" if "Endowment" in camp["campaign_name"] else rng.choice(["F01", "F01", "F03", "F05"])
        return {"gift_id": f"G{self.st.gifts:08d}", "donor_id": donor_id, "gift_date": gdate.isoformat(),
                "amount": amount, "gift_type": gift_type, "campaign_id": camp["campaign_id"], "fund_id": fund,
                "is_anonymous": rng.random() < 0.02, "updated_at": ts(datetime.combine(min(gdate, as_of), time(12, 0)))}

    def _enrollments_for_day(self, d: date, rng, schools):
        rows = []
        if d.weekday() >= 5 or d.month in (7, 8):
            return rows
        for _ in range(rng.randint(2, 7)):
            self.st.enrollments += 1
            prog = rng.choice(ref.PROGRAMS)
            in_school = prog[2] == "In-School"
            participants = rng.randint(18, 120) if in_school else rng.randint(8, 60)
            if rng.random() < 0.003:
                participants = 0                                      # bad data: session with no participants
            rows.append({"enrollment_id": f"EN{self.st.enrollments:07d}", "program_id": prog[0],
                         "school_id": rng.choice(schools)["school_id"] if in_school else "",
                         "session_date": d.isoformat(), "participants": participants,
                         "teaching_artist_hours": rng.choice([1.0, 1.5, 2.0, 3.0])})
        return rows

    # -- marketing --------------------------------------------------------------
    def _email_campaigns_on(self, d: date) -> list[dict]:
        """Emails go out on Tuesdays and Thursdays in season, Tuesdays only in summer."""
        summer = d.month in (7, 8)
        if d.weekday() != 1 and (summer or d.weekday() != 3):
            return []
        rng = random.Random(self.st.seed * 13 + d.toordinal())
        out = []
        for k in range(1 if summer else rng.choice([1, 1, 2])):
            ctype, segment, share, has_series = rng.choice(ref.EMAIL_CAMPAIGN_TYPES)
            series = ("Family Concerts" if ctype == "Family Programs" else rng.choice(list(ref.SERIES))) if has_series else ""
            out.append({"email_campaign_id": f"EM{d:%Y%m%d}{k + 1}",
                        "campaign_name": f"{ctype}: {series}" if series else ctype,
                        "campaign_type": ctype, "series_promoted": series, "audience_segment": segment,
                        "send_datetime": ts(datetime.combine(d, time(rng.choice([9, 10, 11, 16]), 0))), "_share": share})
        return out

    def _campaign_numbers(self, camp, list_size: int):
        rng = random.Random(int(camp["email_campaign_id"][2:]))
        recipients = max(1, int(list_size * 0.65 * camp["_share"]))       # about 65% of buyers opted in to email
        bounces = int(recipients * rng.uniform(0.005, 0.02))
        delivered = recipients - bounces
        return rng, recipients, bounces, delivered, rng.uniform(0.22, 0.38), rng.uniform(0.015, 0.045), rng.uniform(0.001, 0.004)

    def _campaign_stats(self, camp, list_size: int, as_of: date) -> dict:
        """Campaign totals as the email platform reports them on as_of. Most opens happen in the first two days."""
        _, recipients, bounces, delivered, open_rate, click_rate, unsub_rate = self._campaign_numbers(camp, list_size)
        days = (as_of - datetime.fromisoformat(camp["send_datetime"]).date()).days
        progress = 1 - 0.45 ** (days + 1)
        row = {k: v for k, v in camp.items() if not k.startswith("_")}
        row.update(recipients=recipients, delivered=delivered, bounces=bounces,
                   unique_opens=int(delivered * open_rate * progress), unique_clicks=int(delivered * click_rate * progress),
                   unsubscribes=int(delivered * unsub_rate * progress), updated_at=ts(datetime.combine(as_of, time(23, 0))))
        return row

    def _clicks(self, camp, list_size: int) -> list[dict]:
        """Every click a campaign will ever get. Callers keep the ones that happened by the export date."""
        rng, _, _, delivered, _, click_rate, _ = self._campaign_numbers(camp, list_size)
        sent = datetime.fromisoformat(camp["send_datetime"])
        slug = (camp["series_promoted"] or "season").lower().replace(" ", "-")
        out = []
        for i in range(int(delivered * click_rate)):
            for _ in range(5):                                        # find someone who opted in and has an email
                c = self.u.customer(rng.randint(1, list_size), sent.date())
                if c["email_opt_in"] and c["email"]:
                    break
            hours = min(rng.expovariate(1 / 18), 7 * 24 - 1)          # most clicks come within a day
            out.append({"click_id": f"{camp['email_campaign_id']}-{i + 1:05d}", "email_campaign_id": camp["email_campaign_id"],
                        "email": c["email"], "clicked_at": ts(sent + timedelta(hours=hours)),
                        "link_url": f"https://harmoniahall.org/events/{slug}?utm_source=email&utm_medium=email"
                                    f"&utm_campaign={camp['email_campaign_id'].lower()}"})
        return out

    @staticmethod
    def _messy_clicks(clicks: list[dict], rng: random.Random) -> list[dict]:
        """Bad data: some emails in capitals, a few clicks for a campaign that doesn't exist, some rows exported twice."""
        for c in clicks:
            r = rng.random()
            if r < 0.02:
                c["email"] = c["email"].upper()
            elif r < 0.022:
                c["email_campaign_id"] = "EM000000000"
        return clicks + rng.sample(clicks, k=len(clicks) // 200)

    def _ad_rows(self, d: date, as_of: date) -> list[dict]:
        """Daily paid-ad results. Ads run from mid-August to mid-June. The last two days are still partial."""
        if d.month == 7 or (d.month == 8 and d.day < 15) or (d.month == 6 and d.day > 15):
            return []
        fy = fiscal_year(d)
        season_rng = random.Random(self.st.seed * 23 + fy)
        series_on = season_rng.sample(sorted(ref.SERIES), k=4)             # four series get paid ads each season
        lag = {0: 0.6, 1: 0.93}.get((as_of - d).days, 1.0)
        rows = []
        for p, (platform, code, cpm, ctr) in enumerate(ref.AD_PLATFORMS):
            for s, series in enumerate(series_on):
                rng = random.Random(self.st.seed * 29 + d.toordinal() * 31 + p * 7 + s)
                impressions = rng.uniform(4_000, 25_000) * (1.3 if d.weekday() >= 4 else 1.0)
                clicks = impressions * ctr * rng.uniform(0.7, 1.3)
                spend = impressions / 1000 * cpm * rng.uniform(0.85, 1.15)
                if rng.random() < 0.002:
                    spend = -spend                                    # bad data: negative spend
                slug = series.lower().replace(" ", "-")
                rows.append({"ad_date": d.isoformat(), "platform": platform, "ad_campaign_id": f"{code}-{fy}-{slug}",
                             "ad_campaign_name": f"FY{fy} {series} ({platform})", "utm_campaign": f"{slug}-fy{fy}",
                             "series_promoted": series, "impressions": int(impressions * lag), "clicks": int(clicks * lag),
                             "spend": round(spend * lag, 2), "currency": "USD",
                             "updated_at": ts(datetime.combine(as_of, time(6, 0)))})
        return rows

    # -- modes ------------------------------------------------------------------
    def full(self):
        """First load: all history from start to end, in one batch."""
        start, end = date.fromisoformat(self.st.start), date.fromisoformat(self.st.end)
        rng = random.Random(self.st.seed + 101)
        self._new_customers, orders, lines, gifts, enrollments, subs = [], [], [], [], [], []
        schools = self.u.schools()
        campaigns = self.u.campaigns()
        campaigns_by_fy = {}
        for c in campaigns:
            campaigns_by_fy.setdefault(c["fiscal_year"], []).append(c)

        self._history_sales(start, end, rng, orders, lines)
        for d in daterange(start, end):
            enrollments += self._enrollments_for_day(d, rng, schools)

        prev = set()
        for s in self.u.seasons:
            win = (date(s["fiscal_year"] - 1, 3, 1), date(s["fiscal_year"] - 1, 8, 31))
            if win[0] > end:
                break
            win = (max(win[0], start), min(win[1], end))
            if win[0] > win[1]:
                continue
            new_subs, prev = self._subscriptions(s, prev, rng, win)
            subs += new_subs

        # Each donor has a chance of giving again the next year, which creates lapsed donors.
        donors = []
        n_donors = 8000
        for i in range(1, n_donors + 1):
            drng = random.Random(self.st.seed * 17 + i)
            since = start + timedelta(days=drng.randint(0, max(1, (end - start).days - 30)))
            self.st.donors += 1
            donors.append(self.u.donor(i, since, self.st.customers))
            loyalty, fy = drng.uniform(0.35, 0.85), fiscal_year(since)
            active = True
            while fy <= fiscal_year(end):
                if active:
                    fy_start, fy_end = max(date(fy - 1, 7, 1), since), min(date(fy, 6, 30), end)
                    if fy_start <= fy_end:
                        for _ in range(drng.choices([1, 2, 3], [65, 25, 10])[0]):
                            gdate = fy_start + timedelta(days=drng.randint(0, (fy_end - fy_start).days))
                            gifts.append(self._gift(i, gdate, drng, campaigns_by_fy, end))
                active = drng.random() < loyalty
                fy += 1

        created = [datetime.fromisoformat(c["created_at"]).date() for c in self._new_customers]
        campaigns_sent, clicks = [], []
        for d in daterange(start, end):
            for camp in self._email_campaigns_on(d):
                list_size = bisect.bisect_right(created, d)
                if list_size < 50:
                    continue
                campaigns_sent.append(self._campaign_stats(camp, list_size, end))
                clicks += [c for c in self._clicks(camp, list_size) if c["clicked_at"] <= ts(datetime.combine(end, time(23, 59)))]
                if (end - d).days <= 7:
                    self.st.recent_campaigns[camp["email_campaign_id"]] = list_size
        ad_spend = [r for d in daterange(start, end) for r in self._ad_rows(d, end)]

        batch = {
            ("ticketing", "customers"): self._new_customers,
            ("ticketing", "seasons"): self.u.seasons,
            ("ticketing", "venues"): self.u.venues(),
            ("ticketing", "performances"): self.u.performances_snapshot(end),
            ("ticketing", "orders"): orders,
            ("ticketing", "order_lines"): lines,
            ("ticketing", "subscriptions"): subs,
            ("fundraising", "donors"): donors,
            ("fundraising", "campaigns"): campaigns,
            ("fundraising", "funds"): self.u.funds(),
            ("fundraising", "gifts"): gifts,
            ("education", "programs"): self.u.programs(),
            ("education", "schools"): schools,
            ("education", "enrollments"): enrollments,
            ("marketing", "email_campaigns"): campaigns_sent,
            ("marketing", "email_clicks"): self._messy_clicks(clicks, rng),
            ("marketing", "ad_spend_daily"): ad_spend,
        }
        self.st.last_load_date = end.isoformat()
        return end, batch

    def incremental(self, d: date):
        """One day's extract: new and changed rows, plus a full copy of the small lookup tables."""
        rng = random.Random(self.st.seed + d.toordinal())
        self._new_customers, orders, lines = [], [], []
        self._orders_for_day(d, rng, orders, lines)

        # About 0.2% of patrons change address today.
        changed = [self.u.customer(c, date.fromisoformat(self.st.start), version=d.toordinal())
                   for c in rng.sample(range(1, self.st.customers + 1), k=max(1, self.st.customers // 500))]
        for c in changed:
            c["updated_at"] = ts(datetime.combine(d, time(3, 0)))

        # A few recent orders are returned: same order ID, newer updated_at.
        returns = []
        for oid in rng.sample(range(max(1, self.st.orders - 2000), self.st.orders + 1), k=5):
            returns.append({"order_id": f"O{oid:08d}", "customer_id": f"T{rng.randint(1, self.st.customers):07d}",
                            "order_datetime": ts(datetime.combine(d - timedelta(days=rng.randint(1, 20)), time(12, 0))),
                            "channel": "Web", "status": "Returned", "updated_at": ts(datetime.combine(d, time(4, 0)))})
        # Silver keeps the latest version of each order, so the return replaces the original.

        campaigns = self.u.campaigns()
        campaigns_by_fy = {}
        for c in campaigns:
            campaigns_by_fy.setdefault(c["fiscal_year"], []).append(c)
        gifts = [self._gift(rng.randint(1, self.st.donors), d, rng, campaigns_by_fy, d) for _ in range(rng.randint(10, 30))]
        new_donors = []
        for _ in range(rng.randint(1, 4)):
            self.st.donors += 1
            new_donors.append(self.u.donor(self.st.donors, d, self.st.customers))

        # Email stats keep growing for a week after a send, so the export repeats
        # the last 7 days of campaigns with their latest numbers.
        campaigns_sent, clicks = [], []
        for back in range(7, -1, -1):
            day = d - timedelta(days=back)
            for camp in self._email_campaigns_on(day):
                list_size = self.st.recent_campaigns.setdefault(camp["email_campaign_id"], self.st.customers)
                campaigns_sent.append(self._campaign_stats(camp, list_size, d))
                clicks += [c for c in self._clicks(camp, list_size) if c["clicked_at"][:10] == d.isoformat()]
        self.st.recent_campaigns = {k: v for k, v in self.st.recent_campaigns.items()
                                    if date.fromisoformat(f"{k[2:6]}-{k[6:8]}-{k[8:10]}") >= d - timedelta(days=7)}
        # Ad platforms restate the last two days, so each export covers three days.
        ad_spend = [r for back in (2, 1, 0) for r in self._ad_rows(d - timedelta(days=back), d)]

        batch = {
            ("ticketing", "customers"): self._new_customers + changed,
            ("ticketing", "seasons"): self.u.seasons,
            ("ticketing", "venues"): self.u.venues(),
            ("ticketing", "performances"): self.u.performances_snapshot(d),
            ("ticketing", "orders"): orders + returns,
            ("ticketing", "order_lines"): lines,
            ("ticketing", "subscriptions"): [],
            ("fundraising", "donors"): new_donors,
            ("fundraising", "campaigns"): campaigns,
            ("fundraising", "funds"): self.u.funds(),
            ("fundraising", "gifts"): gifts,
            ("education", "programs"): self.u.programs(),
            ("education", "schools"): self.u.schools(),
            ("education", "enrollments"): self._enrollments_for_day(d, rng, self.u.schools()),
            ("marketing", "email_campaigns"): campaigns_sent,
            ("marketing", "email_clicks"): self._messy_clicks(clicks, rng),
            ("marketing", "ad_spend_daily"): ad_spend,
        }
        self.st.last_load_date = d.isoformat()
        return d, batch


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    f = sub.add_parser("full", help="initial historical load")
    f.add_argument("--start", default="2023-07-01")
    f.add_argument("--end", default=(date.today() - timedelta(days=1)).isoformat())
    f.add_argument("--seed", type=int, default=42)
    i = sub.add_parser("incremental", help="one day of new and changed rows (run after full)")
    i.add_argument("--date", default=None, help="YYYY-MM-DD (default: day after last load)")
    i.add_argument("--days", type=int, default=1, help="generate N consecutive days")
    for p in (f, i):
        p.add_argument("--out", type=Path, default=DEFAULT_OUT)
        p.add_argument("--state", type=Path, default=STATE_FILE)
    a = ap.parse_args(argv)

    if a.mode == "full":
        st = State(seed=a.seed, start=a.start, end=a.end)
        load_date, batch = Generator(st).full()
        results = [write_all(load_date, batch, a.out, full=True)]
    else:
        st = State.load(a.state)
        d = date.fromisoformat(a.date) if a.date else date.fromisoformat(st.last_load_date) + timedelta(days=1)
        results = []
        for n in range(a.days):
            load_date, batch = Generator(st).incremental(d + timedelta(days=n))
            results.append(write_all(load_date, batch, a.out, full=False))
    st.save(a.state)
    for m in results:
        total = sum(x["rows"] for x in m["files"])
        print(f"load_date={m['load_date']}: {total:,} rows")
        for x in m["files"]:
            print(f"   {x['source']:<12}{x['entity']:<16}{x['rows']:>9,}   -> {x['where']}")
    print(f"\nNext: see docs/01-runbook.md, Phase 8, for where each folder under {a.out}/ goes.")


if __name__ == "__main__":
    main()
