from __future__ import annotations

import calendar
import datetime as dt
import json
import os
import urllib.request
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

USERNAME = "Nebulazer123"
ROOT = Path(__file__).resolve().parent
TOKEN = os.environ.get("GITHUB_TOKEN", "")
DETAIL_X = 410
BIRTH_TIME = dt.datetime(2003, 7, 21, 3, 0, tzinfo=ZoneInfo("America/Chicago"))

FALLBACK = {
    "repos": 12,
    "contributed": 12,
    "stars": 0,
    "commits": 343,
    "loc_add": 0,
    "loc_del": 0,
    "loc_net": 0,
    "since": "2016",
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
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def graphql(query: str, variables: dict) -> dict:
    data = request_json(
        "https://api.github.com/graphql",
        {"query": query, "variables": variables},
    )
    if not isinstance(data, dict):
        raise RuntimeError("GitHub GraphQL returned a non-object response")
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"]))
    return data["data"]


def add_months(value: dt.datetime, months: int) -> dt.datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def uptime_string(now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now(BIRTH_TIME.tzinfo)
    years = now.year - BIRTH_TIME.year
    cursor = BIRTH_TIME.replace(year=BIRTH_TIME.year + years)
    if cursor > now:
        years -= 1
        cursor = BIRTH_TIME.replace(year=BIRTH_TIME.year + years)

    months = 0
    while add_months(cursor, months + 1) <= now:
        months += 1
    cursor = add_months(cursor, months)

    days = (now - cursor).days
    return f"{years} years, {months} months, {days} days"


def repository_overview() -> tuple[str, str, list[dict]]:
    query = """
    query($login: String!) {
      user(login: $login) {
        id
        createdAt
        repositories(
          first: 100
          ownerAffiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER]
        ) {
          totalCount
          nodes {
            name
            owner { login }
            stargazerCount
            defaultBranchRef { name }
          }
        }
      }
    }
    """
    data = graphql(query, {"login": USERNAME})["user"]
    return data["id"], data["createdAt"], data["repositories"]["nodes"]


def commit_and_loc_for_repo(owner: str, name: str, user_id: str) -> tuple[int, int, int]:
    query = """
    query($owner: String!, $name: String!, $cursor: String, $author: ID!) {
      repository(owner: $owner, name: $name) {
        defaultBranchRef {
          target {
            ... on Commit {
              history(first: 100, after: $cursor, author: {id: $author}) {
                nodes {
                  additions
                  deletions
                }
                pageInfo { hasNextPage endCursor }
              }
            }
          }
        }
      }
    }
    """
    cursor = None
    commits = additions = deletions = 0
    while True:
        data = graphql(
            query,
            {"owner": owner, "name": name, "cursor": cursor, "author": user_id},
        )["repository"]
        if not data or not data.get("defaultBranchRef"):
            return commits, additions, deletions
        history = data["defaultBranchRef"]["target"]["history"]
        for node in history["nodes"]:
            commits += 1
            additions += int(node.get("additions") or 0)
            deletions += int(node.get("deletions") or 0)
        if not history["pageInfo"]["hasNextPage"]:
            return commits, additions, deletions
        cursor = history["pageInfo"]["endCursor"]


def collect_stats() -> dict[str, int | str]:
    values: dict[str, int | str] = dict(FALLBACK)
    try:
        user_id, created_at, repositories = repository_overview()
        owned = [
            repo for repo in repositories
            if repo["owner"]["login"].casefold() == USERNAME.casefold()
        ]
        values["repos"] = len(owned)
        values["contributed"] = len(repositories)
        values["stars"] = sum(int(repo["stargazerCount"]) for repo in owned)
        values["since"] = created_at[:4]

        commit_total = addition_total = deletion_total = 0
        for repo in repositories:
            if not repo.get("defaultBranchRef"):
                continue
            commits, additions, deletions = commit_and_loc_for_repo(
                repo["owner"]["login"], repo["name"], user_id
            )
            commit_total += commits
            addition_total += additions
            deletion_total += deletions

        values["commits"] = commit_total
        values["loc_add"] = addition_total
        values["loc_del"] = deletion_total
        values["loc_net"] = addition_total - deletion_total
    except Exception as exc:
        print(f"Using fallback GitHub statistics: {exc}")

    values["uptime"] = uptime_string()
    values["updated"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    return values


def fmt(value: int | str) -> str:
    return f"{value:,}" if isinstance(value, int) else str(value)


def field(y: int, label: str, value: str, dots: int) -> str:
    return (
        f'<tspan x="{DETAIL_X}" y="{y}" class="cc">. </tspan>'
        f'<tspan class="key">{escape(label)}</tspan>:'
        f'<tspan class="cc"> {"." * dots} </tspan>'
        f'<tspan class="value">{escape(value)}</tspan>'
    )


def build_light_svg(values: dict[str, int | str]) -> str:
    portrait = (ROOT / "portrait_light.txt").read_text(encoding="utf-8").splitlines()
    if len(portrait) != 36 or max(map(len, portrait)) != 50:
        raise ValueError("portrait_light.txt must remain 36 rows with a 50-character maximum")

    row_step = 480 / (len(portrait) - 1)
    portrait_rows = "".join(
        f'<tspan x="18" y="{30 + index * row_step:.2f}">{escape(line)}</tspan>'
        for index, line in enumerate(portrait)
    )

    details = [
        f'<tspan x="{DETAIL_X}" y="30">corbin@nebulazer -{"—" * 35}-</tspan>',
        field(50, "OS", "macOS, Windows", 15),
        field(70, "Uptime", str(values["uptime"]), 4),
        field(90, "Host", "Handshake AI", 18),
        field(110, "Title", "AI fellow, Researcher, builder", 8),
        field(130, "IDE", "Codex, VS Code", 14),
        f'<tspan x="{DETAIL_X}" y="150" class="cc">. </tspan>',
        field(170, "Aspiring Role", "Forward Development Engineer", 2),
        field(190, "Languages.Programming", "Python, C++", 4),
        field(210, "Tools", "Codex, Git, GitHub, APIs, MCP", 8),
        f'<tspan x="{DETAIL_X}" y="230" class="cc">. </tspan>',
        field(250, "Focus", "Multi-agent orchestration", 9),
        field(270, "Building", "SKILLS.md, Methodology Frameworks", 2),
        field(290, "Hobbies.Software", "AI systems, automation, PKM", 3),
        field(310, "Hobbies.Hardware", "PC building, engine tuning", 3),
        field(330, "Lifestyle Hobbies", "Strength training, kickboxing", 2),
        f'<tspan x="{DETAIL_X}" y="350">- Contact -{"—" * 32}-</tspan>',
        field(370, "Email.Work", "thecorbinfloyd@gmail.com", 6),
        field(390, "LinkedIn", "corbin-floyd-000b22275", 9),
        f'<tspan x="{DETAIL_X}" y="410">- GitHub Stats -{"—" * 27}-</tspan>',
        (
            f'<tspan x="{DETAIL_X}" y="430" class="cc">. </tspan>'
            f'<tspan class="key">Repos</tspan>:<tspan class="cc"> ... </tspan>'
            f'<tspan class="value" id="repo_data">{fmt(values["repos"])}</tspan> '
            f'{{<tspan class="key">Contributed</tspan>: '
            f'<tspan class="value" id="contrib_data">{fmt(values["contributed"])}</tspan>}} '
            f'| <tspan class="key">Stars</tspan>:<tspan class="cc"> ... </tspan>'
            f'<tspan class="value" id="star_data">{fmt(values["stars"])}</tspan>'
        ),
        (
            f'<tspan x="{DETAIL_X}" y="450" class="cc">. </tspan>'
            f'<tspan class="key">Commits</tspan>:<tspan class="cc"> .......... </tspan>'
            f'<tspan class="value" id="commit_data">{fmt(values["commits"])}</tspan> '
            f'| <tspan class="key">Since</tspan>:<tspan class="cc"> ... </tspan>'
            f'<tspan class="value" id="since_data">{fmt(values["since"])}</tspan>'
        ),
        (
            f'<tspan x="{DETAIL_X}" y="470" class="cc">. </tspan>'
            f'<tspan class="key">Lines of Code on GitHub</tspan>:'
            f'<tspan class="cc">. </tspan>'
            f'<tspan class="value" id="loc_data">{fmt(values["loc_net"])}</tspan> '
            f'( <tspan class="addColor" id="loc_add">{fmt(values["loc_add"])}</tspan>'
            f'<tspan class="addColor">++</tspan>, '
            f'<tspan class="delColor" id="loc_del">{fmt(values["loc_del"])}</tspan>'
            f'<tspan class="delColor">--</tspan> )'
        ),
        field(490, "Projects", "Agentelligence, Skill-Finder", 8),
        field(510, "Updated", str(values["updated"]), 19),
    ]

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="985" height="530" viewBox="0 0 985 530" role="img" aria-labelledby="title desc">
<title id="title">Corbin Floyd GitHub profile card - light mode</title>
<desc id="desc">Light-mode ASCII portrait and terminal-style profile details.</desc>
<style>
@font-face {{
  src: local('SF Mono'), local('Menlo'), local('Consolas');
  font-family: 'ProfileMono';
  font-display: swap;
}}
.key {{fill:#953800;}}
.value {{fill:#0a3069;}}
.addColor {{fill:#1a7f37;}}
.delColor {{fill:#cf222e;}}
.cc {{fill:#a8b2bf;}}
text,tspan {{white-space:pre;font-variant-ligatures:none;}}
</style>
<rect x="0.5" y="0.5" width="984" height="529" fill="#f6f8fa" stroke="#d0d7de" rx="15"/>
<text x="18" y="30" fill="#24292f" xml:space="preserve" font-family="ProfileMono,'SF Mono',Menlo,Monaco,Consolas,'Liberation Mono',monospace" font-size="12.9px" font-weight="500" stroke="#24292f" stroke-width="0.20" paint-order="stroke fill" text-rendering="geometricPrecision">{portrait_rows}</text>
<text x="{DETAIL_X}" y="30" fill="#24292f" xml:space="preserve" font-family="ProfileMono,'SF Mono',Menlo,Monaco,Consolas,'Liberation Mono',monospace" font-size="15px" font-weight="500">{"".join(details)}</text>
</svg>'''


def main() -> None:
    values = collect_stats()
    (ROOT / "light_mode.svg").write_text(build_light_svg(values), encoding="utf-8")
    print(json.dumps(values, indent=2))


if __name__ == "__main__":
    main()
