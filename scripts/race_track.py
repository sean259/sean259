#!/usr/bin/env python3
"""Turn a GitHub contribution calendar into an animated "race track" SVG.

A car drives a serpentine lap through every day of the past year.
Days with contributions are fuel cells that light up and get collected
as the car passes. The dashboard shows the year's total and current streak.

Usage:
  GITHUB_TOKEN=... python scripts/race_track.py <username> dist/race-track.svg
  python scripts/race_track.py --demo dist/race-track.svg   # fake data, no network
"""
import json
import os
import random
import sys
import urllib.request

CELL, GAP = 11, 4
STEP = CELL + GAP
PAD_X, PAD_TOP = 30, 70
LAP_SECONDS = 24

# fuel colour per contribution level (GitHub's quartiles)
LEVEL_COLORS = {
    "NONE": "#1e1b2e",
    "FIRST_QUARTILE": "#5b1f4a",
    "SECOND_QUARTILE": "#a3245a",
    "THIRD_QUARTILE": "#ff5e7e",
    "FOURTH_QUARTILE": "#ffd36b",
}

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
  }
}"""


def fetch(login, token):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if "errors" in data:
        sys.exit(f"GitHub API error: {data['errors']}")
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = [w["contributionDays"] for w in cal["weeks"]]
    return weeks, cal["totalContributions"]


def demo():
    levels = list(LEVEL_COLORS)
    rnd = random.Random(7)
    weeks, total = [], 0
    for _ in range(53):
        week = []
        for _ in range(7):
            n = rnd.choice([0, 0, 0, 1, 2, 3, 5, 8, 12])
            lvl = levels[min(4, (n + 2) // 3)] if n else "NONE"
            week.append({"contributionCount": n, "contributionLevel": lvl, "date": ""})
            total += n
        weeks.append(week)
    return weeks, total


def streak(weeks):
    days = [d["contributionCount"] for w in weeks for d in w]
    # today may have no commits yet; don't break the streak for that
    if days and days[-1] == 0:
        days = days[:-1]
    s = 0
    for n in reversed(days):
        if n == 0:
            break
        s += 1
    return s


def cell_xy(col, row):
    return PAD_X + col * STEP, PAD_TOP + row * STEP


def build(weeks, total):
    cols = len(weeks)
    width = PAD_X * 2 + cols * STEP - GAP
    height = PAD_TOP + 7 * STEP + 38

    # serpentine order: down column 0, up column 1, down column 2...
    order = []
    for c, week in enumerate(weeks):
        # the first week can be partial; push its days down to the right weekday row
        offset = 7 - len(week) if c == 0 else 0
        idx = range(len(week)) if c % 2 == 0 else reversed(range(len(week)))
        for i in idx:
            order.append((c, i + offset, week[i]))

    centers = [(x + CELL / 2, y + CELL / 2) for c, r, _ in order for x, y in [cell_xy(c, r)]]
    path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in centers)
    n = len(order)
    drive = LAP_SECONDS * 0.85  # rest of the lap is a pause at the finish

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
        "<style>text{font-family:'Segoe UI',Verdana,sans-serif}</style>",
        f'<rect width="{width}" height="{height}" rx="14" fill="#0f0d1a"/>',
        f'<text x="{PAD_X}" y="34" font-size="18" font-weight="800" fill="#fff">🏁 CONTRIBUTION GRAND PRIX</text>',
        f'<text x="{PAD_X}" y="54" font-size="12" fill="#a99bd6">{total} commits fuelled this season · {streak(weeks)}-day streak</text>',
        # faint track line
        f'<path d="{path}" fill="none" stroke="#2b2640" stroke-width="3" stroke-linejoin="round"/>',
    ]

    for i, (c, r, day) in enumerate(order):
        x, y = cell_xy(c, r)
        color = LEVEL_COLORS.get(day["contributionLevel"], LEVEL_COLORS["NONE"])
        t = i / (n - 1) * drive / LAP_SECONDS  # fraction of lap when car arrives
        out.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{LEVEL_COLORS["NONE"]}"/>')
        if day["contributionCount"] > 0:
            # fuel cell: visible, then collected (flash white + fade) when car passes,
            # then respawns at the start of the next lap
            t2 = min(t + 0.01, 0.999)
            out.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{color}">'
                f'<animate attributeName="opacity" values="1;1;0.15;0.15" keyTimes="0;{t:.4f};{t2:.4f};1" '
                f'dur="{LAP_SECONDS}s" repeatCount="indefinite"/>'
                f'<animate attributeName="fill" values="{color};{color};#ffffff;{color}" keyTimes="0;{t:.4f};{t2:.4f};1" '
                f'dur="{LAP_SECONDS}s" repeatCount="indefinite"/>'
                "</rect>"
            )

    # checkered start/finish flags
    sx, sy = cell_xy(order[0][0], order[0][1])
    fx, fy = cell_xy(order[-1][0], order[-1][1])
    for (fx_, fy_) in [(sx - 18, sy), (fx + CELL + 6, fy)]:
        out.append(f'<g transform="translate({fx_} {fy_})">'
                   '<rect width="12" height="12" fill="#fff"/><rect width="6" height="6" fill="#000"/>'
                   '<rect x="6" y="6" width="6" height="6" fill="#000"/></g>')

    # the car (points along +x so rotate="auto" faces the direction of travel)
    out.append(
        '<g>'
        '<g transform="translate(-9 -6)">'
        '<rect x="1" y="2" width="16" height="8" rx="3" fill="#ff3b3b"/>'
        '<rect x="9" y="3" width="5" height="6" rx="1" fill="#8fd3ff"/>'
        '<rect x="0" y="0" width="4" height="3" rx="1" fill="#111"/><rect x="12" y="0" width="4" height="3" rx="1" fill="#111"/>'
        '<rect x="0" y="9" width="4" height="3" rx="1" fill="#111"/><rect x="12" y="9" width="4" height="3" rx="1" fill="#111"/>'
        '<rect x="16" y="3" width="2" height="2" fill="#fff6c2"/><rect x="16" y="7" width="2" height="2" fill="#fff6c2"/>'
        '</g>'
        f'<animateMotion dur="{LAP_SECONDS}s" repeatCount="indefinite" rotate="auto" '
        f'keyPoints="0;1;1" keyTimes="0;{drive / LAP_SECONDS:.3f};1" calcMode="linear" path="{path}"/>'
        '</g>'
    )

    # legend
    ly = height - 22
    out.append(f'<text x="{PAD_X}" y="{ly + 9}" font-size="11" fill="#a99bd6">Fuel:</text>')
    for k, color in enumerate(LEVEL_COLORS.values()):
        out.append(f'<rect x="{PAD_X + 38 + k * 16}" y="{ly}" width="{CELL}" height="{CELL}" rx="2" fill="{color}"/>')
    out.append(f'<text x="{width - PAD_X}" y="{ly + 9}" font-size="11" fill="#6f6597" text-anchor="end">refuelled daily by GitHub Actions</text>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    args = sys.argv[1:]
    if len(args) != 2:
        sys.exit(__doc__)
    who, dest = args
    if who == "--demo":
        weeks, total = demo()
    else:
        token = os.environ.get("GITHUB_TOKEN") or sys.exit("GITHUB_TOKEN is not set")
        weeks, total = fetch(who, token)
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(build(weeks, total))
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
