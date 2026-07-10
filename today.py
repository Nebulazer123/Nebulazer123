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
    "repo_data": "22",
    "star_data": "13",
    "contrib_data": "319",
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
        f'<tspan x="505" y="{y}" class="cc">. </tspan>'
        f'<tspan class="key">{escape(label)}</tspan>:'
        f'<tspan class="cc"> {"." * dots} </tspan>'
        f'<tspan class="value">{escape(value)}</tspan>'
    )


def stat(y: int, left: tuple[str, str, int], right: tuple[str, str, int], values: dict[str, str]) -> str:
    left_label, left_id, left_dots = left
    right_label, right_id, right_dots = right
    return (
        f'<tspan x="505" y="{y}" class="cc">. </tspan>'
        f'<tspan class="key">{left_label}</tspan>:'
        f'<tspan class="cc" id="{left_id}_dots"> {"." * left_dots} </tspan>'
        f'<tspan class="value" id="{left_id}">{values[left_id]}</tspan>'
        f'<tspan> | </tspan>'
        f'<tspan class="key">{right_label}</tspan>:'
        f'<tspan class="cc" id="{right_id}_dots"> {"." * right_dots} </tspan>'
        f'<tspan class="value" id="{right_id}">{values[right_id]}</tspan>'
    )


def build_svg(theme: dict[str, str], values: dict[str, str]) -> str:
    portrait = (ROOT / "portrait.txt").read_text().splitlines()
    if len(portrait) != 47 or max(map(len, portrait)) != 87:
        raise ValueError("portrait.txt must remain exactly 47 rows with an 87-character maximum")

    portrait_rows = "".join(
        f'<tspan x="10" y="{18 + index * 14.45:.2f}">{escape(line)}</tspan>'
        for index, line in enumerate(portrait)
    )

    details = [
        '<tspan x="505" y="27">corbin@nebulazer  ─────────────────────────────</tspan>',
        field(55, "OS", "macOS · Windows", 11),
        field(82, "Mac", 'MacBook Pro 16" · M4 Pro · 24 GB', 5),
        field(109, "PC", "i7-9700 · RTX 2080 Super · 32 GB", 6),
        field(136, "Title", "AI fellow · researcher · builder", 10),
        field(163, "Editor", "Codex · VS Code", 8),
        '<tspan x="505" y="198">- Work  ─────────────────────────────────────</tspan>',
        field(226, "Languages.Programming", "Python · C++", 1),
        field(253, "Tools", "Codex · Git · GitHub · APIs · MCP", 7),
        field(280, "Focus", "Multi-agent orchestration", 7),
        field(307, "Building", "Skill development · research automation", 4),
        field(334, "Evaluation", "Models · data analysis", 2),
        '<tspan x="505" y="369">- Hobbies  ──────────────────────────────────</tspan>',
        field(397, "Hobbies.Software", "AI systems · automation · PKM", 1),
        field(424, "Hobbies.Hardware", "PC building · display tuning", 1),
        field(451, "Hobbies.Active", "Strength training · boxing", 1),
        '<tspan x="505" y="486">- Contact  ──────────────────────────────────</tspan>',
        field(514, "Website", "corbinfloyd.com", 5),
        field(541, "GitHub", USERNAME, 7),
        field(568, "Location", "Pensacola, Florida", 4),
        '<tspan x="505" y="603">- GitHub Stats  ─────────────────────────────</tspan>',
        stat(631, ("Repos", "repo_data", 4), ("Stars", "star_data", 3), values),
        stat(658, ("Contribs", "contrib_data", 2), ("Followers", "follower_data", 1), values),
        stat(685, ("Following", "following_data", 2), ("Since", "since_data", 1), values),
    ]

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="896" height="710" viewBox="0 0 896 710" preserveAspectRatio="xMinYMin meet" role="img" aria-labelledby="title desc">
<title id="title">Corbin Floyd GitHub profile</title>
<desc id="desc">ASCII portrait and terminal-style profile information for Corbin Floyd.</desc>
<style>.key{{fill:{theme["key"]}}}.value{{fill:{theme["value"]}}}.cc{{fill:{theme["muted"]}}}text,tspan{{white-space:pre}}</style>
<rect x=".5" y=".5" width="895" height="709" rx="15" fill="{theme["bg"]}" stroke="{theme["border"]}"/>
<text fill="{theme["text"]}" font-family="Consolas,'Liberation Mono',Menlo,monospace" font-size="9px" xml:space="preserve">{portrait_rows}</text>
<text fill="{theme["text"]}" font-family="Consolas,'Liberation Mono',Menlo,monospace" font-size="11.4px" xml:space="preserve">{"".join(details)}</text>
</svg>'''


def main() -> None:
    values = collect_stats()
    for filename, theme in THEMES.items():
        (ROOT / filename).write_text(build_svg(theme, values))
    print(json.dumps(values, indent=2))


if __name__ == "__main__":
    main()
