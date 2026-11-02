#!/usr/bin/env python3
"""Fetch the TTNZ national tournament calendar and write tournaments.json
for events in the lower North Island (plus nationwide campaigns).
Safe by design: if nothing sensible is parsed, the existing file is left untouched."""
import json, re, sys, datetime as dt
import requests
from bs4 import BeautifulSoup

URL = "https://tabletennis.org.nz/tournaments/national-tournament-calendar"
OUT = "tournaments.json"
REGION = re.compile(r"wellington|petone|hutt|kapiti|kāpiti|wairarapa|masterton|palmerston|manawat|whanganui|wanganui|napier|hawke|taranaki|new plymouth|nationwide", re.I)
SKIP = re.compile(r"camp|course|coach education|hopes week|squad", re.I)
MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}

def mon(s):
    return MONTHS.get(s.strip().lower()[:3])

def parse_rows(soup):
    year, events = None, []
    month_a = None
    for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "table"]):
        if el.name != "table":
            m = re.search(r"Tournament Calendar\s*(20\d\d)", el.get_text(" ", strip=True), re.I)
            if m:
                year, month_a = int(m.group(1)), None
            continue
        if not year:
            continue
        for tr in el.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 5 or cells[0].strip().upper() == "MONTH":
                continue
            mcell, f, t, name, loc = cells[0], cells[1], cells[2], cells[3], cells[4]
            extra = cells[5:]
            second = None  # a second month (e.g. "Dec/Jan") only applies to the row that names it
            if mcell.strip():
                parts = [mon(p) for p in re.split(r"[/&]", mcell) if mon(p)]
                if parts:
                    month_a = parts[0]
                    second = parts[1] if len(parts) > 1 else None
            if not (name and f.strip().isdigit() and month_a):
                continue
            d1 = int(f)
            d2 = int(t) if t.strip().isdigit() else d1
            m1 = month_a
            m2 = second or (m1 if d2 >= d1 else (m1 % 12) + 1)
            y1 = year
            y2 = year + (1 if m2 < m1 else 0)
            try:
                start, end = dt.date(y1, m1, d1), dt.date(y2, m2, d2)
            except ValueError:
                continue
            a = tr.find("a", href=True)
            link = a["href"] if a else ""
            if link.startswith("/"):
                link = "https://tabletennis.org.nz" + link
            events.append({"name": name, "start": start, "end": end, "loc": loc, "url": link, "extra": extra})
    return events

def main():
    r = requests.get(URL, headers={"User-Agent": "SpinSquad-site-calendar/1.0 (club website; weekly check)"}, timeout=30)
    r.raise_for_status()
    rows = parse_rows(BeautifulSoup(r.text, "html.parser"))
    today = dt.date.today()
    out = []
    for e in rows:
        if e["end"] < today or not REGION.search(e["loc"]) or SKIP.search(e["name"]):
            continue
        bits = []
        if e["extra"] and e["extra"][0].strip():
            bits.append("Events: " + e["extra"][0].strip() + ".")
        if len(e["extra"]) > 1 and e["extra"][1].strip():
            bits.append("Entries close: " + e["extra"][1].strip() + ".")
        out.append({"title": e["name"], "start": e["start"].isoformat(), "end": e["end"].isoformat(),
                    "location": e["loc"], "details": " ".join(bits) or "See the TTNZ site for details and entry.",
                    "url": e["url"] or URL})
    print(f"parsed {len(rows)} calendar rows, kept {len(out)} for the lower North Island")
    if not rows:
        print("ERROR: no calendar rows parsed (page layout may have changed). Leaving tournaments.json unchanged.")
        sys.exit(1)
    out.sort(key=lambda x: x["start"])
    # keep hand-written entries (marked "manual": true) so the weekly update never removes them
    try:
        old = json.load(open(OUT, encoding="utf-8"))
    except Exception:
        old = []
    keep = [o for o in old if o.get("manual")]
    seen = {(o["title"], o["start"]) for o in out}
    out += [o for o in keep if (o["title"], o["start"]) not in seen]
    out.sort(key=lambda x: x["start"])
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    open(OUT, "a").write("\n")

if __name__ == "__main__":
    main()
