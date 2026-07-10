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

FALLBACK = {
    "repo_data": "11",
    "star_data": "0",
    "contrib_data": "328",
    "follower_data": "0",
    "following_data": "1",
    "since_data": "2016",
}

THEMES = {
    "dark_mode.svg": {
        "bg": "#161b22", "border": "#30363d", "text": "#c9d1d9",
        "key": "#ffa657", "value": "#a5d6ff", "muted": "#6e7681",
    },
    "light_mode.svg": {
        "bg": "#f6f8fa", "border": "#d0d7de", "text": "#24292f",
        "key": "#953800", "value": "#0a3069", "muted": "#8c959f",
    },
}

DETAIL_X = 630


def request_json(url: str, data: dict | None = None) -> dict | list:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-profile-readme",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    body = None if data is None else json.dumps(data).encode()
    if body:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def collect_stats() -> dict[str, str]:
    values = dict(FALLBACK)
    try:
        profile = request_json(f"https://api.github.com/users/{USERNAME}")
        repos = request_json(
            f"https://api.github.com/users/{USERNAME}/repos?type=owner&per_page=100"
        )
        assert isinstance(profile, dict) and isinstance(repos, list)
        values["repo_data"] = str(profile.get("public_repos", values["repo_data"]))
        values["star_data"] = str(sum(
            int(repo.get("stargazers_count", 0))
            for repo in repos if not repo.get("fork")
        ))
        values["follower_data"] = str(profile.get("followers", values["follower_data"]))
        values["following_data"] = str(profile.get("following", values["following_data"]))
        created = str(profile.get("created_at", ""))
        if created:
            values["since_data"] = created[:4]

        if TOKEN:
            now = dt.datetime.now(dt.timezone.utc)
            query = """
            query($login:String!,$from:DateTime!,$to:DateTime!){
              user(login:$login){contributionsCollection(from:$from,to:$to){
                contributionCalendar{totalContributions}}}}
            """
            result = request_json("https://api.github.com/graphql", {
                "query": query,
                "variables": {
                    "login": USERNAME,
                    "from": (now - dt.timedelta(days=365)).isoformat(),
                    "to": now.isoformat(),
                },
            })
            if isinstance(result, dict) and not result.get("errors"):
                values["contrib_data"] = str(
                    result["data"]["user"]["contributionsCollection"]
                    ["contributionCalendar"]["totalContributions"]
                )
    except Exception as exc:
        print(f"Using fallback values: {exc}")
    return values


def field(y: int, label: str, value: str, dots: int) -> str:
    return (
        f'<tspan x="{DETAIL_X}" y="{y}" class="cc">. </tspan>'
        f'<tspan class="key">{escape(label)}</tspan>:'
        f'<tspan class="cc"> {"." * dots} </tspan>'
        f'<tspan class="value">{escape(value)}</tspan>'
    )


def stat(y: int, label: str, element_id: str, value: str, dots: int) -> str:
    return (
        f'<tspan x="{DETAIL_X}" y="{y}" class="cc">. </tspan>'
        f'<tspan class="key">{escape(label)}</tspan>:'
        f'<tspan class="cc" id="{element_id}_dots"> {"." * dots} </tspan>'
        f'<tspan class="value" id="{element_id}">{escape(value)}</tspan>'
    )


def build_svg(theme: dict[str, str], values: dict[str, str]) -> str:
    portrait = (ROOT / "portrait.txt").read_text().splitlines()
    if len(portrait) != 47 or max(map(len, portrait)) != 87:
        raise ValueError("portrait.txt must remain exactly 47 rows with an 87-character maximum")

    # The source portrait is already vertically compressed for monospace output.
    # Menlo/Consolas cells are still narrower in-browser than TextEdit's display,
    # so the SVG widens only the rendered cells; the source characters stay exact.
    portrait_rows = "".join(
        f'<tspan x="0" y="{18 + index * 13.6:.2f}">{escape(line)}</tspan>'
        for index, line in enumerate(portrait)
    )

    details = [
        f'<tspan x="{DETAIL_X}" y="27">corbin@nebulazer  ──────────────────────</tspan>',
        field(54, "OS", "macOS · Windows", 5),
        field(79, "Mac", "M4 Pro · 24 GB", 5),
        field(104, "PC", "i7-9700 · RTX 2080S · 32 GB", 4),
        field(129, "Title", "AI fellow · researcher · builder", 3),
        field(154, "Editor", "Codex · VS Code", 4),
        f'<tspan x="{DETAIL_X}" y="188">- Work  ──────────────────────────────</tspan>',
        field(214, "Languages", "Python · C++", 2),
        field(239, "Tools", "Codex · Git · APIs · MCP", 3),
        field(264, "Focus", "Multi-agent orchestration", 3),
        field(289, "Building", "Skills · research automation", 2),
        field(314, "Evaluation", "Models · data analysis", 1),
        f'<tspan x="{DETAIL_X}" y="348">- Hobbies  ───────────────────────────</tspan>',
        field(374, "Software", "AI systems · automation · PKM", 2),
        field(399, "Hardware", "PC building · display tuning", 2),
        field(424, "Active", "Strength training · boxing", 3),
        f'<tspan x="{DETAIL_X}" y="458">- GitHub  ────────────────────────────</tspan>',
        stat(484, "Repos", "repo_data", values["repo_data"], 3),
        stat(509, "Stars", "star_data", values["star_data"], 3),
        stat(534, "Contribs", "contrib_data", values["contrib_data"], 2),
        stat(559, "Since", "since_data", values["since_data"], 3),
    ]

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="896" height="680" viewBox="0 0 896 680" preserveAspectRatio="xMinYMin meet" role="img" aria-labelledby="title desc">
<title id="title">Corbin Floyd GitHub profile</title>
<desc id="desc">ASCII portrait and terminal-style profile information for Corbin Floyd.</desc>
<style>.key{{fill:{theme["key"]}}}.value{{fill:{theme["value"]}}}.cc{{fill:{theme["muted"]}}}text,tspan{{white-space:pre;font-variant-ligatures:none}}</style>
<rect x=".5" y=".5" width="895" height="679" rx="15" fill="{theme["bg"]}" stroke="{theme["border"]}"/>
<g transform="translate(8 0) scale(1.31 1)">
<text fill="{theme["text"]}" font-family="Menlo,Monaco,Consolas,'Liberation Mono',monospace" font-size="9px" xml:space="preserve">{portrait_rows}</text>
</g>
<text fill="{theme["text"]}" font-family="Menlo,Monaco,Consolas,'Liberation Mono',monospace" font-size="9.4px" xml:space="preserve">{"".join(details)}</text>
</svg>'''


def main() -> None:
    values = collect_stats()
    for filename, theme in THEMES.items():
        (ROOT / filename).write_text(build_svg(theme, values))
    print(json.dumps(values, indent=2))


if __name__ == "__main__":
    main()
