from __future__ import annotations

import datetime as dt
import json
import os
import urllib.request
from html import escape
from pathlib import Path

USERNAME = "Nebulazer123"
ROOT = Path(__file__).resolve().parent
TOKEN = os.environ.get("GITHUB_TOKEN", "")
DETAIL_X = 430

FALLBACK = {
    "repos": "11",
    "starred": "13",
    "contribs": "331",
    "since": "2016",
    "pinned": "2",
}

THEMES = {
    "dark_mode.svg": {
        "bg": "#161b22",
        "text": "#c9d1d9",
        "key": "#ffa657",
        "value": "#a5d6ff",
        "add": "#3fb950",
        "delete": "#f85149",
        "muted": "#616e7f",
    },
    "light_mode.svg": {
        "bg": "#f6f8fa",
        "text": "#24292f",
        "key": "#953800",
        "value": "#0a3069",
        "add": "#1a7f37",
        "delete": "#cf222e",
        "muted": "#c2cfde",
    },
}


def request_json(url: str, payload: dict | None = None) -> dict | list:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-profile-readme",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def count_paginated(url: str) -> int:
    total = 0
    page = 1
    while True:
        separator = "&" if "?" in url else "?"
        result = request_json(f"{url}{separator}per_page=100&page={page}")
        if not isinstance(result, list):
            return total
        total += len(result)
        if len(result) < 100:
            return total
        page += 1


def collect_stats() -> dict[str, str]:
    values = dict(FALLBACK)
    try:
        profile = request_json(f"https://api.github.com/users/{USERNAME}")
        if isinstance(profile, dict):
            values["repos"] = str(profile.get("public_repos", values["repos"]))
            created = str(profile.get("created_at", ""))
            if created:
                values["since"] = created[:4]

        values["starred"] = str(
            count_paginated(f"https://api.github.com/users/{USERNAME}/starred")
        )

        if TOKEN:
            now = dt.datetime.now(dt.timezone.utc)
            query = """
            query($login:String!,$from:DateTime!,$to:DateTime!){
              user(login:$login){
                contributionsCollection(from:$from,to:$to){
                  contributionCalendar{totalContributions}
                }
              }
            }
            """
            result = request_json(
                "https://api.github.com/graphql",
                {
                    "query": query,
                    "variables": {
                        "login": USERNAME,
                        "from": (now - dt.timedelta(days=365)).isoformat(),
                        "to": now.isoformat(),
                    },
                },
            )
            if isinstance(result, dict) and not result.get("errors"):
                values["contribs"] = str(
                    result["data"]["user"]["contributionsCollection"]
                    ["contributionCalendar"]["totalContributions"]
                )
    except Exception as exc:
        print(f"Using fallback profile statistics: {exc}")
    values["updated"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    return values


def field(y: int, label: str, value: str, dots: int) -> str:
    return (
        f'<tspan x="{DETAIL_X}" y="{y}" class="cc">. </tspan>'
        f'<tspan class="key">{escape(label)}</tspan>:'
        f'<tspan class="cc"> {"." * dots} </tspan>'
        f'<tspan class="value">{escape(value)}</tspan>'
    )


def header(y: int, label: str, dashes: int) -> str:
    return f'<tspan x="{DETAIL_X}" y="{y}">- {escape(label)} -{"—" * dashes}-</tspan>'


def build_svg(theme: dict[str, str], values: dict[str, str]) -> str:
    portrait = (ROOT / "portrait.txt").read_text(encoding="utf-8").splitlines()
    if len(portrait) != 24 or max(map(len, portrait)) != 43:
        raise ValueError("portrait.txt must remain 24 rows with a 43-character maximum")

    row_step = 480 / (len(portrait) - 1)
    portrait_rows = "".join(
        f'<tspan x="15" y="{30 + index * row_step:.2f}">{escape(line)}</tspan>'
        for index, line in enumerate(portrait)
    )

    details = [
        f'<tspan x="{DETAIL_X}" y="30">corbin@nebulazer -{"—" * 36}-</tspan>',
        field(50, "OS", "macOS, Windows", 14),
        field(70, "Host.Mac", "M4 Pro, 24 GB", 10),
        field(90, "Host.PC", "i7-9700, RTX 2080S, 32 GB", 7),
        field(110, "Title", "AI fellow, researcher, builder", 8),
        field(130, "IDE", "Codex, VS Code", 13),
        f'<tspan x="{DETAIL_X}" y="150" class="cc">. </tspan>',
        field(170, "Languages.Programming", "Python, C++", 3),
        field(190, "Tools", "Codex, Git, GitHub, APIs, MCP", 8),
        field(210, "Focus", "Multi-agent orchestration", 8),
        field(230, "Building", "Skills, research automation", 5),
        field(250, "Hobbies.Software", "AI systems, automation, PKM", 2),
        field(270, "Hobbies.Hardware", "PC building, display tuning", 2),
        field(290, "Hobbies.Active", "Strength training, boxing", 3),
        header(310, "Contact", 34),
        field(330, "Website", "corbinfloyd.com", 12),
        field(350, "Email", "nebulazer2003@gmail.com", 11),
        field(370, "LinkedIn", "corbin-floyd-000b22275", 8),
        field(390, "Projects", "Agentelligence, skill-finder", 8),
        f'<tspan x="{DETAIL_X}" y="410" class="cc">. </tspan>',
        header(450, "GitHub Stats", 30),
        (
            f'<tspan x="{DETAIL_X}" y="470" class="cc">. </tspan>'
            f'<tspan class="key">Repos</tspan>:<tspan class="cc"> .... </tspan>'
            f'<tspan class="value" id="repo_data">{escape(values["repos"])}</tspan>'
            f'<tspan> | </tspan><tspan class="key">Starred</tspan>:'
            f'<tspan class="cc"> .... </tspan>'
            f'<tspan class="value" id="starred_data">{escape(values["starred"])}</tspan>'
        ),
        (
            f'<tspan x="{DETAIL_X}" y="490" class="cc">. </tspan>'
            f'<tspan class="key">Contribs</tspan>:<tspan class="cc"> ........ </tspan>'
            f'<tspan class="value" id="contrib_data">{escape(values["contribs"])}</tspan>'
            f'<tspan> | </tspan><tspan class="key">Since</tspan>:'
            f'<tspan class="cc"> .... </tspan>'
            f'<tspan class="value" id="since_data">{escape(values["since"])}</tspan>'
        ),
        (
            f'<tspan x="{DETAIL_X}" y="510" class="cc">. </tspan>'
            f'<tspan class="key">Pinned</tspan>:<tspan class="cc"> ......... </tspan>'
            f'<tspan class="value" id="pinned_data">{escape(values["pinned"])}</tspan>'
            f'<tspan> | </tspan><tspan class="key">Updated</tspan>:'
            f'<tspan class="cc"> .. </tspan>'
            f'<tspan class="value" id="updated_data">{escape(values["updated"])}</tspan>'
        ),
    ]

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,monospace" width="985px" height="530px" font-size="16px" role="img" aria-labelledby="title desc">
<title id="title">Corbin Floyd GitHub profile</title>
<desc id="desc">ASCII portrait and terminal-style profile details.</desc>
<style>
@font-face {{
  src: local('Consolas'), local('Consolas Bold');
  font-family: 'ConsolasFallback';
  font-display: swap;
  -webkit-size-adjust: 109%;
  size-adjust: 109%;
}}
.key {{fill:{theme["key"]};}}
.value {{fill:{theme["value"]};}}
.addColor {{fill:{theme["add"]};}}
.delColor {{fill:{theme["delete"]};}}
.cc {{fill:{theme["muted"]};}}
text, tspan {{white-space:pre;font-variant-ligatures:none;}}
</style>
<rect width="985px" height="530px" fill="{theme["bg"]}" rx="15"/>
<text x="15" y="30" fill="{theme["text"]}" class="ascii" xml:space="preserve">{portrait_rows}</text>
<text x="{DETAIL_X}" y="30" fill="{theme["text"]}" xml:space="preserve">{"".join(details)}</text>
</svg>'''


def main() -> None:
    values = collect_stats()
    for filename, theme in THEMES.items():
        (ROOT / filename).write_text(build_svg(theme, values), encoding="utf-8")
    print(json.dumps(values, indent=2))


if __name__ == "__main__":
    main()
