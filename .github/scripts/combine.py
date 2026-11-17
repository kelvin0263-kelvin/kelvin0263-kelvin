"""Combine the contribution calendars of several GitHub accounts into one heatmap.

Reads LOGINS (comma-separated) and GITHUB_TOKEN from the environment, fetches every
contribution year of each account, adds the frozen counts in work-history.json
(see import_snapshot.py), sums the counts per day, and writes
combined-light.svg, combined-dark.svg and combined.json to the repo root.
"""
import datetime as dt
import json
import os
import urllib.request

LOGINS = [s.strip() for s in os.environ["LOGINS"].split(",") if s.strip()]
TOKEN = os.environ["GITHUB_TOKEN"]
SNAPSHOT = "work-history.json"  # frozen daily counts of an account we can no longer query

THEMES = {
    "light": {"text": "#57606a", "cells": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]},
    "dark": {"text": "#8b949e", "cells": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]},
}
CELL, GAP = 10, 3
STEP = CELL + GAP
LEFT, MONTH_H, TITLE_H, YEAR_GAP = 28, 14, 20, 18
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.load(resp)
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]


def years_of(login):
    q = "query($l:String!){user(login:$l){contributionsCollection{contributionYears}}}"
    return gql(q, {"l": login})["user"]["contributionsCollection"]["contributionYears"]


def calendar(login, year, now):
    start = dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc)
    end = min(dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc), now)
    q = """query($l:String!,$f:DateTime!,$t:DateTime!){user(login:$l){
      contributionsCollection(from:$f,to:$t){contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""
    data = gql(q, {"l": login, "f": start.isoformat(), "t": end.isoformat()})
    weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}


def quartiles(days):
    """Cut points for levels 2-4, like GitHub: quartiles of the non-zero days."""
    vals = sorted(c for c in days.values() if c > 0) or [1]
    return [vals[len(vals) * q // 4] for q in (1, 2, 3)]


def level(count, cuts):
    if count <= 0:
        return 0
    return 1 + sum(count > c for c in cuts)


def render(days, years, theme):
    colors = THEMES[theme]
    cuts = quartiles(days)
    width = LEFT + 53 * STEP + 2
    block_h = TITLE_H + MONTH_H + 7 * STEP
    height = len(years) * (block_h + YEAR_GAP)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif">'
    ]
    for i, year in enumerate(years):
        top = i * (block_h + YEAR_GAP)
        jan1 = dt.date(year, 1, 1)
        first_sunday = jan1 - dt.timedelta(days=(jan1.weekday() + 1) % 7)
        total = sum(c for d, c in days.items() if d.startswith(str(year)))
        out.append(
            f'<text x="0" y="{top + 13}" font-size="13" font-weight="600" fill="{colors["text"]}">'
            f"{year} · {total:,} contributions</text>"
        )
        grid_top = top + TITLE_H + MONTH_H
        for m in range(12):
            first = dt.date(year, m + 1, 1)
            col = (first - first_sunday).days // 7
            out.append(
                f'<text x="{LEFT + col * STEP}" y="{grid_top - 4}" font-size="9" fill="{colors["text"]}">{MONTHS[m]}</text>'
            )
        for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
            out.append(
                f'<text x="0" y="{grid_top + row * STEP + 9}" font-size="9" fill="{colors["text"]}">{label}</text>'
            )
        day = jan1
        while day.year == year:
            col = (day - first_sunday).days // 7
            row = (day.weekday() + 1) % 7
            key = day.isoformat()
            count = days.get(key, 0)
            out.append(
                f'<rect x="{LEFT + col * STEP}" y="{grid_top + row * STEP}" width="{CELL}" height="{CELL}" rx="2" '
                f'fill="{colors["cells"][level(count, cuts)]}"><title>{key}: {count}</title></rect>'
            )
            day += dt.timedelta(days=1)
    out.append("</svg>")
    return "\n".join(out)


def main():
    now = dt.datetime.now(dt.timezone.utc)
    days, per_account = {}, {}
    for login in LOGINS:
        per_account[login] = {}
        for year in years_of(login):
            for date, count in calendar(login, year, now).items():
                if count:
                    per_account[login][date] = count
                    days[date] = days.get(date, 0) + count
    if os.path.exists(SNAPSHOT):
        snap = json.load(open(SNAPSHOT))
        per_account[snap["login"]] = snap["days"]
        for date, count in snap["days"].items():
            days[date] = days.get(date, 0) + count
    years = sorted({int(d[:4]) for d in days} or {now.year}, reverse=True)
    for theme in THEMES:
        with open(f"combined-{theme}.svg", "w") as f:
            f.write(render(days, years, theme))
    with open("combined.json", "w") as f:
        json.dump({"accounts": LOGINS, "total": sum(days.values()), "days": dict(sorted(days.items())),
                   "perAccount": per_account}, f, indent=1)
    print(f"{len(days)} active days, {sum(days.values())} contributions across {list(per_account)}")


if __name__ == "__main__":
    main()
