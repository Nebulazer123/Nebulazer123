#!/usr/bin/env python3
"""Generate light/dark SVG cards for the Nebulazer123 profile README."""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import html
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
W, H = 985, 530
ASCII_W, ASCII_H = 44, 25
TEXT_X = 420

THEMES = {
    "dark": {
        "bg": "#161b22", "text": "#c9d1d9", "key": "#ffa657",
        "value": "#a5d6ff", "muted": "#616e7f", "accent": "#d2a8ff",
        "portrait": ["#484f58", "#6e7681", "#8c959f", "#b1bac4", "#d0d7de", "#f0f6fc"],
        "ramp": ".^~!7?JY5PGB#&@",
    },
    "light": {
        "bg": "#f6f8fa", "text": "#24292f", "key": "#953800",
        "value": "#0a3069", "muted": "#c2cfde", "accent": "#8250df",
        "portrait": ["#d0d7de", "#afb8c1", "#818b98", "#636c76", "#424a53", "#24292f"],
        "ramp": ".^~!7?JY5PGB#&@",
    },
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def load_json() -> dict:
    return json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))


def load_ascii(mode: str) -> list[str]:
    rows = (ROOT / "ascii" / f"{mode}.txt").read_text(encoding="utf-8").splitlines()
    if len(rows) != ASCII_H:
        raise ValueError(f"ascii/{mode}.txt must contain exactly {ASCII_H} lines, found {len(rows)}")
    longest = max(map(len, rows))
    if longest > ASCII_W:
        raise ValueError(f"ascii/{mode}.txt must be no wider than {ASCII_W} characters, found {longest}")
    return [line.ljust(ASCII_W) for line in rows]


def age_on(date_string: str) -> str:
    born = dt.date.fromisoformat(date_string)
    today = dt.datetime.now(dt.timezone.utc).date()
    years = today.year - born.year
    if (today.month, today.day) < (born.month, born.day):
        years -= 1
    anchor_year = born.year + years
    anchor_day = min(born.day, calendar.monthrange(anchor_year, born.month)[1])
    anchor = dt.date(anchor_year, born.month, anchor_day)
    months = 0
    cursor = anchor
    while True:
        month = cursor.month + 1
        year = cursor.year + (month > 12)
        month = 1 if month > 12 else month
        day = min(born.day, calendar.monthrange(year, month)[1])
        nxt = dt.date(year, month, day)
        if nxt > today:
            break
        cursor = nxt
        months += 1
    return f"{years} years, {months} months, {(today - cursor).days} days"


def api_json(url: str, token: str | None = None) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Nebulazer123-profile-readme",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def get_stats(profile: dict, offline: bool) -> dict[str, int]:
    stats = dict(profile["fallback_stats"])
    if offline:
        return stats
    username = profile["username"]
    token = os.getenv("PROFILE_TOKEN") or os.getenv("GITHUB_TOKEN")
    try:
        user = api_json(f"https://api.github.com/users/{username}", token)
        stats["public_repos"] = int(user.get("public_repos", stats["public_repos"]))
        stats["followers"] = int(user.get("followers", stats["followers"]))
        stars, page = 0, 1
        while True:
            repos = api_json(
                f"https://api.github.com/users/{username}/repos?type=owner&per_page=100&page={page}", token
            )
            stars += sum(int(repo.get("stargazers_count", 0)) for repo in repos)
            if len(repos) < 100:
                break
            page += 1
        stats["stars"] = stars
    except Exception as error:
        print(f"Could not refresh public stats; using fallback values: {error}")
    return stats


def dots(label: str, value: object, target: int = 58) -> str:
    return " " + "." * max(2, target - len(label) - len(str(value))) + " "


def detail(y: int, label: str, value: object, target: int = 58) -> str:
    return (
        f'<tspan x="{TEXT_X}" y="{y}" class="muted">. </tspan>'
        f'<tspan class="key">{esc(label)}</tspan>:'
        f'<tspan class="muted">{dots(label, value, target)}</tspan>'
        f'<tspan class="value">{esc(value)}</tspan>'
    )


def stats_row(y: int, a: str, av: object, b: str, bv: object) -> str:
    return (
        f'<tspan x="{TEXT_X}" y="{y}" class="muted">. </tspan>'
        f'<tspan class="key">{esc(a)}</tspan>:'
        f'<tspan class="muted">{dots(a, av, 29)}</tspan><tspan class="value">{esc(av)}</tspan>'
        f' <tspan class="muted">| </tspan><tspan class="key">{esc(b)}</tspan>:'
        f'<tspan class="muted">{dots(b, bv, 22)}</tspan><tspan class="value">{esc(bv)}</tspan>'
    )


def portrait_svg(rows: list[str], mode: str) -> str:
    ramp = THEMES[mode]["ramp"]
    rank = {char: i for i, char in enumerate(ramp)}
    output = []
    for row_no, row in enumerate(rows):
        pieces, current, text = [], None, ""
        for char in row:
            bucket = -1 if char == " " else min(5, rank.get(char, 7) * 6 // len(ramp))
            if bucket != current:
                if text:
                    pieces.append(esc(text) if current == -1 else f'<tspan class="p{current}">{esc(text)}</tspan>')
                current, text = bucket, char
            else:
                text += char
        if text:
            pieces.append(esc(text) if current == -1 else f'<tspan class="p{current}">{esc(text)}</tspan>')
        output.append(f'<tspan x="15" y="{30 + row_no * 20}">{"".join(pieces)}</tspan>')
    return "\n".join(output)


def render(mode: str, profile: dict, stats: dict[str, int]) -> str:
    t = THEMES[mode]
    year = dt.datetime.now(dt.timezone.utc).year
    updated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d UTC")
    rows = [
        f'<tspan x="{TEXT_X}" y="30">{esc(profile["header"])}</tspan> <tspan class="muted">-————————————————————————————————————-</tspan>',
        detail(50, "OS", profile["os"]),
        detail(70, "Uptime", age_on(profile["birthday"])),
        detail(90, "Host", profile["host"]),
        detail(110, "Kernel", profile["kernel"]),
        detail(130, "IDE", profile["ide"]),
        f'<tspan x="{TEXT_X}" y="150" class="muted">. </tspan>',
        detail(170, "Languages.Programming", profile["languages_programming"]),
        detail(190, "Languages.Computer", profile["languages_computer"]),
        detail(210, "Tools", profile["tools"]),
        detail(230, "Focus", profile["focus"]),
        f'<tspan x="{TEXT_X}" y="250" class="muted">. </tspan>',
        detail(270, "Building", profile["building"]),
        detail(290, "Researching", profile["researching"]),
        f'<tspan x="{TEXT_X}" y="310">- Contact</tspan> <tspan class="muted">-——————————————————————————————-</tspan>',
        detail(330, "Website", profile["website"]),
        detail(350, "GitHub", profile["github"]),
        detail(370, "Location", profile["location"]),
        f'<tspan x="{TEXT_X}" y="390" class="muted">. </tspan>',
        f'<tspan x="{TEXT_X}" y="410">- GitHub Stats</tspan> <tspan class="muted">-——————————————————————————-</tspan>',
        stats_row(430, "Public Repos", stats["public_repos"], "Stars", stats["stars"]),
        stats_row(450, "Contributed", stats["contributed_repos"], "Followers", stats["followers"]),
        detail(470, f"Contributions.{year}", stats["contributions"]),
        detail(490, "Updated", updated),
        f'<tspan x="{TEXT_X}" y="510" class="accent" font-size="12px">Superpowers upgrades the worker. AgentIntelligence upgrades the workplace.</tspan>',
    ]
    portrait_classes = "\n".join(f'.p{i} {{fill: {color};}}' for i, color in enumerate(t["portrait"]))
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" font-family="Consolas, 'Liberation Mono', monospace" width="{W}px" height="{H}px" font-size="16px">
<style>
.key {{fill: {t['key']};}} .value {{fill: {t['value']};}} .muted {{fill: {t['muted']};}}
.accent {{fill: {t['accent']};}} text, tspan {{white-space: pre;}}
{portrait_classes}
</style>
<rect width="{W}" height="{H}" fill="{t['bg']}" rx="15"/>
<text x="15" y="30" fill="{t['text']}">
{portrait_svg(load_ascii(mode), mode)}
</text>
<text x="{TEXT_X}" y="30" fill="{t['text']}">
{chr(10).join(rows)}
</text>
</svg>
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="Use fallback statistics from profile.json")
    args = parser.parse_args()
    profile = load_json()
    stats = get_stats(profile, args.offline)
    for mode in ("light", "dark"):
        (ROOT / f"{mode}_mode.svg").write_text(render(mode, profile, stats), encoding="utf-8")
        print(f"wrote {mode}_mode.svg")


if __name__ == "__main__":
    main()
