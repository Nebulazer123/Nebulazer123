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
    "contrib_data": "331",
    "since_data": "2016",
    "pinned_data": "2",
}

THEMES = {
    "dark_mode.svg": {
        "bg": "#161b22",
        "text": "#c9d1d9",
        "key": "#ffa657",
        "value": "#a5d6ff",
        "add": "#3fb950",
        "delete": "#f85149",
        "cc": "#616e7f",
    },
    "light_mode.svg": {
        "bg": "#f6f8fa",
        "text": "#24292f",
        "key": "#953800",
        "value": "#0a3069",
        "add": "#1a7f37",
        "delete": "#cf222e",
        "cc": "#c2cfde",
    },
}

DETAIL_X = 445
FIELD_WIDTH = 54


def request_json(url: str, data: dict | None = None) -> dict | list:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-profile-readme",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    body = None if data is None else json.dumps(data).encode("utf-8")
    if body is not None:
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def collect_stats() -> dict[str, str]:
    values = dict(FALLBACK)

    try:
        profile = request_json(f"https://api.github.com/users/{USERNAME}")
        repos = request_json(
            f"https://api.github.com/users/{USERNAME}/repos?type=owner&per_page=100"
        )
        assert isinstance(profile, dict)
        assert isinstance(repos, list)

        values["repo_data"] = str(
            profile.get("public_repos", values["repo_data"])
        )
        values["star_data"] = str(
            sum(
                int(repo.get("stargazers_count", 0))
                for repo in repos
                if not repo.get("fork")
            )
        )

        created_at = str(profile.get("created_at", ""))
        if created_at:
            values["since_data"] = created_at[:4]

        if TOKEN:
            now = dt.datetime.now(dt.timezone.utc)
            query = """
            query($login: String!, $from: DateTime!, $to: DateTime!) {
              user(login: $login) {
                contributionsCollection(from: $from, to: $to) {
                  contributionCalendar {
                    totalContributions
                  }
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
                values["contrib_data"] = str(
                    result["data"]["user"]["contributionsCollection"]
                    ["contributionCalendar"]["totalContributions"]
                )
    except Exception as exc:
        print(f"Using fallback values: {exc}")

    values["updated_data"] = dt.datetime.now(
        dt.timezone.utc
    ).strftime("%Y-%m-%d")
    return values


def field(y: int, label: str, value: str, total: int = FIELD_WIDTH) -> str:
    prefix_length = len(". ") + len(label) + len(": ") + 2
    dots = max(1, total - prefix_length - len(value))
    return (
        f'<tspan x="{DETAIL_X}" y="{y}" class="cc">. </tspan>'
        f'<tspan class="key">{escape(label)}</tspan>:'
        f'<tspan class="cc"> {"." * dots} </tspan>'
        f'<tspan class="value">{escape(value)}</tspan>'
    )


def stat_pair(
    y: int,
    left_label: str,
    left_id: str,
    right_label: str,
    right_id: str,
    values: dict[str, str],
    left_dots: int,
    right_dots: int,
) -> str:
    return (
        f'<tspan x="{DETAIL_X}" y="{y}" class="cc">. </tspan>'
        f'<tspan class="key">{escape(left_label)}</tspan>:'
        f'<tspan class="cc" id="{left_id}_dots"> {"." * left_dots} </tspan>'
        f'<tspan class="value" id="{left_id}">{escape(values[left_id])}</tspan>'
        f' | <tspan class="key">{escape(right_label)}</tspan>:'
        f'<tspan class="cc" id="{right_id}_dots"> {"." * right_dots} </tspan>'
        f'<tspan class="value" id="{right_id}">{escape(values[right_id])}</tspan>'
    )


def build_svg(theme: dict[str, str], values: dict[str, str]) -> str:
    portrait = (ROOT / "portrait.txt").read_text(
        encoding="utf-8"
    ).splitlines()

    if len(portrait) != 24 or max(map(len, portrait)) != 43:
        raise ValueError(
            "portrait.txt must remain exactly 24 rows "
            "with a 43-character maximum"
        )

    row_step = 480 / (len(portrait) - 1)
    portrait_rows = "\n".join(
        f'<tspan x="15" y="{30 + index * row_step:.2f}">'
        f'{escape(line)}</tspan>'
        for index, line in enumerate(portrait)
    )

    details = [
        f'<tspan x="{DETAIL_X}" y="30">corbin@nebulazer</tspan> '
        '-———————————————————————————————-—-',
        field(50, "OS", "macOS, Windows"),
        field(70, "Host.Mac", 'MacBook Pro 16", M4 Pro, 24 GB'),
        field(90, "Host.PC", "i7-9700, RTX 2080 Super, 32 GB"),
        field(110, "Title", "AI fellow, researcher, builder"),
        field(130, "IDE", "Codex, VS Code"),
        f'<tspan x="{DETAIL_X}" y="150" class="cc">. </tspan>',
        field(170, "Languages.Programming", "Python, C++"),
        field(190, "Tools", "Codex, Git, GitHub, APIs, MCP"),
        field(210, "Focus", "Multi-agent orchestration"),
        f'<tspan x="{DETAIL_X}" y="230" class="cc">. </tspan>',
        field(250, "Hobbies.Software", "AI systems, automation, PKM"),
        field(270, "Hobbies.Hardware", "PC building, display tuning"),
        field(290, "Hobbies.Active", "Strength training, boxing"),
        f'<tspan x="{DETAIL_X}" y="310">- Contact</tspan> '
        '-———————————————————————————————-—-',
        field(330, "Website", "corbinfloyd.com"),
        field(350, "Email", "nebulazer2003@gmail.com"),
        field(370, "LinkedIn", "corbin-floyd-000b22275"),
        field(390, "GitHub", USERNAME),
        field(410, "Location", "Pensacola, Florida"),
        f'<tspan x="{DETAIL_X}" y="430" class="cc">. </tspan>',
        f'<tspan x="{DETAIL_X}" y="450">- GitHub Stats</tspan> '
        '-—————————————————————————-—-',
        stat_pair(
            470, "Repos", "repo_data", "Stars", "star_data",
            values, 4, 8,
        ),
        stat_pair(
            490, "Contributions", "contrib_data",
            "Since", "since_data", values, 2, 4,
        ),
        stat_pair(
            510, "Pinned", "pinned_data",
            "Updated", "updated_data", values, 5, 1,
        ),
    ]

    return f"""<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,monospace" width="985px" height="530px" font-size="16px">
<style>
@font-face {{
src: local('Consolas'), local('Consolas Bold');
font-family: 'ConsolasFallback';
font-display: swap;
-webkit-size-adjust: 109%;
size-adjust: 109%;
}}
.key {{fill: {theme["key"]};}}
.value {{fill: {theme["value"]};}}
.addColor {{fill: {theme["add"]};}}
.delColor {{fill: {theme["delete"]};}}
.cc {{fill: {theme["cc"]};}}
text, tspan {{white-space: pre;}}
</style>
<rect width="985px" height="530px" fill="{theme["bg"]}" rx="15"/>
<text x="15" y="30" fill="{theme["text"]}" class="ascii">
{portrait_rows}
</text>
<text x="{DETAIL_X}" y="30" fill="{theme["text"]}">
{chr(10).join(details)}
</text>
</svg>
"""


def main() -> None:
    values = collect_stats()
    for filename, theme in THEMES.items():
        (ROOT / filename).write_text(
            build_svg(theme, values),
            encoding="utf-8",
        )
    print(json.dumps(values, indent=2))


if __name__ == "__main__":
    main()
