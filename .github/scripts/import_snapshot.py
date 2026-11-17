"""Turn a saved GitHub contributions page into work-history.json.

Usage: python .github/scripts/import_snapshot.py <saved contributions.html> [login]

Save the page while logged in as the account (https://github.com/users/<login>/contributions,
Cmd+S as Page Source) so private contributions are included. Days already in
work-history.json are kept; days in the new page overwrite them.
"""
import html
import json
import os
import re
import sys

src = sys.argv[1]
login = sys.argv[2] if len(sys.argv) > 2 else "chunkeat-tan"
page = open(src, encoding="utf-8").read()

dates = dict(re.findall(r'data-date="(\d{4}-\d{2}-\d{2})"\s+id="(contribution-day-component-\d+-\d+)"', page))
dates = {cell: date for date, cell in dates.items()}
counts = {}
for cell, text in re.findall(r'<tool-tip[^>]*for="(contribution-day-component-\d+-\d+)"[^>]*>([^<]+)', page):
    m = re.match(r"(\d[\d,]*) contributions?", html.unescape(text).strip())
    if m and cell in dates:
        counts[dates[cell]] = int(m.group(1).replace(",", ""))

header = re.search(r"([\d,]+)\s+contributions?\s+in the last year", page)
expected = int(header.group(1).replace(",", "")) if header else None
if expected is not None and sum(counts.values()) != expected:
    sys.exit(f"parsed {sum(counts.values())} but page says {expected}; not writing")

out = "work-history.json"
existing = json.load(open(out)) if os.path.exists(out) else {"login": login, "days": {}}
existing["days"].update(counts)
existing["days"] = dict(sorted((d, c) for d, c in existing["days"].items() if c))
existing["snapshotThrough"] = max(dates.values())
json.dump(existing, open(out, "w"), indent=1)
print(f"{len(counts)} active days, {sum(counts.values())} contributions; snapshot through {existing['snapshotThrough']}")
