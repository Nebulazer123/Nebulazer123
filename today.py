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
BIRTH_TIME = dt.datetime(2003, 7, 21, 3, 0, tzinfo=ZoneInfo("America/Chicago"))
DETAIL_X = 410

THEMES = {
    "light_mode.svg": {
        "mode": "light",
        "portrait": "portrait_light.txt",
        "bg": "#f6f8fa",
        "border": "#d0d7de",
        "text": "#24292f",
        "portrait_text": "#4f5660",
        "portrait_stroke": "#4f5660",
        "portrait_stroke_width": "0.16",
        "key": "#d46a00",
        "value": "#0969da",
        "add": "#1a7f37",
        "delete": "#cf222e",
        "muted": "#8c959f",
    },
    "dark_mode.svg": {
        "mode": "dark",
        "portrait": "portrait_dark.txt",
        "bg": "#161b22",
        "border": "#30363d",
        "text": "#d6d9df",
        "portrait_text": "#d6d9df",
        "portrait_stroke": "#d6d9df",
        "portrait_stroke_width": "0.18",
        "key": "#ffa657",
        "value": "#a5d6ff",
        "add": "#3fb950",
        "delete": "#f85149",
        "muted": "#6e7681",
    },
}

FALLBACK = {
    "repos": 12,
    "contributed": 12,
    "stars": 0,
    "commits": 233,
    "followers": 0,
    "loc_add": 288353,
    "loc_del": 68804,
    "loc_net": 219549,
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
    result = request_json(
        "https://api.github.com/graphql",
        {"query": query, "variables": variables},
    )
    if not isinstance(result, dict):
        raise RuntimeError("GitHub GraphQL returned a non-object response")
    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"]))
    return result["data"]


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
    return f"{years}yrs, {months} months, {days}days"


def repository_overview() -> tuple[str, str, list[dict], int]:
    query = """
    query($login: String!) {
      user(login: $login) {
        id
        createdAt
        repositories(
          first: 100
          ownerAffiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER]
          privacy: PUBLIC
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
    user = graphql(query, {"login": USERNAME})["user"]
    repos = user["repositories"]
    return user["id"], user["createdAt"], repos["nodes"], int(repos["totalCount"])


def annual_contributions() -> int | None:
    if not TOKEN:
        return None
    now = dt.datetime.now(dt.timezone.utc)
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar { totalContributions }
        }
      }
    }
    """
    data = graphql(
        query,
        {
            "login": USERNAME,
            "from": (now - dt.timedelta(days=365)).isoformat(),
            "to": now.isoformat(),
        },
    )
    return int(
        data["user"]["contributionsCollection"]
        ["contributionCalendar"]["totalContributions"]
    )


def commit_and_loc_for_repo(owner: str, name: str, user_id: str) -> tuple[int, int, int]:
    query = """
    query($owner: String!, $name: String!, $cursor: String, $author: ID!) {
      repository(owner: $owner, name: $name) {
        defaultBranchRef {
          target {
            ... on Commit {
              history(first: 100, after: $cursor, author: {id: $author}) {
                nodes { additions deletions }
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
        repo = graphql(
            query,
            {"owner": owner, "name": name, "cursor": cursor, "author": user_id},
        )["repository"]
        if not repo or not repo.get("defaultBranchRef"):
            return commits, additions, deletions
        history = repo["defaultBranchRef"]["target"]["history"]
        for node in history["nodes"]:
            commits += 1
            additions += int(node.get("additions") or 0)
            deletions += int(node.get("deletions") or 0)
        if not history["pageInfo"]["hasNextPage"]:
            return commits, additions, deletions
        cursor = history["pageInfo"]["endCursor"]


def collect_stats() -> dict[str, int | str | None]:
    values: dict[str, int | str | None] = dict(FALLBACK)
    values["annual_contributions"] = None

    try:
        profile = request_json(f"https://api.github.com/users/{USERNAME}")
        if isinstance(profile, dict):
            values["repos"] = int(profile.get("public_repos", values["repos"]))
            values["followers"] = int(profile.get("followers", values["followers"]))
            created_at = str(profile.get("created_at", ""))
            if created_at:
                values["since"] = created_at[:4]
    except Exception as exc:
        print(f"Public profile lookup failed: {exc}")

    try:
        user_id, created_at, repositories, affiliated_count = repository_overview()
        values["contributed"] = affiliated_count
        values["stars"] = sum(int(repo.get("stargazerCount") or 0) for repo in repositories)
        values["since"] = created_at[:4]

        commit_total = addition_total = deletion_total = 0
        for repo in repositories:
            if not repo.get("defaultBranchRef"):
                continue
            try:
                commits, additions, deletions = commit_and_loc_for_repo(
                    repo["owner"]["login"], repo["name"], user_id
                )
            except Exception as exc:
                print(f"Skipping {repo['owner']['login']}/{repo['name']}: {exc}")
                continue
            commit_total += commits
            addition_total += additions
            deletion_total += deletions

        if commit_total or addition_total or deletion_total:
            values["commits"] = commit_total
            values["loc_add"] = addition_total
            values["loc_del"] = deletion_total
            values["loc_net"] = addition_total - deletion_total
    except Exception as exc:
        print(f"Repository statistics lookup failed: {exc}")

    try:
        values["annual_contributions"] = annual_contributions()
    except Exception as exc:
        print(f"Annual contribution lookup failed: {exc}")

    values["uptime"] = uptime_string()
    values["updated"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    return values


def tspan(x: int | str, y: str, content: str) -> str:
    return f'<tspan x="{x}" y="{y}">{content}</tspan>'


def cls(name: str, text: str) -> str:
    return f'<tspan class="{name}">{escape(text)}</tspan>'


def build_portrait(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) != 36 or max(map(len, lines)) > 51:
        raise ValueError(f"{path.name} must remain 36 rows and at most 51 characters wide")
    step = 480 / (len(lines) - 1)
    return "".join(
        f'<tspan x="18" y="{30 + index * step:.2f}">{escape(line)}</tspan>'
        for index, line in enumerate(lines)
    )


def build_panel(values: dict[str, int | str | None]) -> str:
    rows: list[str] = []
    rows.append(tspan(410, "30.00", "corbin@nebulazer " + "─" * 44))
    rows.append(tspan(410, "48.46", f'{cls("cc", ". ")}{cls("key", "OS")}: {cls("cc", "." * 35 + " ")}{cls("value", "macOS, Windows, iOS")}'))
    rows.append(tspan(410, "66.92", f'{cls("cc", ". ")}{cls("key", "Uptime")}: {cls("cc", "." * 26 + " ")}{cls("value", str(values["uptime"]))}'))
    rows.append(tspan(410, "85.38", f'{cls("cc", ". ")}{cls("key", "Host")}: {cls("cc", "." * 40 + " ")}{cls("value", "Handshake AI")}'))
    rows.append(tspan(410, "103.85", f'{cls("cc", ". ")}{cls("key", "Title")}: {cls("cc", "." * 21 + " ")}{cls("value", "AI Fellow, Researcher, builder")}'))
    rows.append(tspan(410, "122.31", f'{cls("cc", ". ")}{cls("key", "IDE")}: {cls("cc", "." * 33)}{cls("value", "Codex, VS Code, Xcode")}'))
    rows.append(tspan(410, "140.77", cls("cc", ". ")) + " " + "–" * 57)
    rows.append(tspan(410, "159.23", f'{cls("cc", ". ")}{cls("key", "Aspiring Role")}: {cls("cc", "." * 15 + " ")}{cls("value", "Forward Development Engineer")}'))
    rows.append(tspan(410, "177.69", f'{cls("cc", ". ")}{cls("key", "Languages.Programming")}: {cls("cc", "." * 24 + " ")}{cls("value", "Python, C++")}'))
    rows.append(tspan(410, "196.15", f'{cls("cc", ". ")}{cls("key", "Tools")}: {cls("cc", "." * 22 + " ")}{cls("value", "Codex, Git, GitHub, APIs, MCP")}'))
    rows.append(tspan(410, "214.62", cls("cc", ". ")) + " " + "–" * 57)
    rows.append(tspan(410, "233.08", f'{cls("cc", ". ")}{cls("key", "Projects")}: {cls("cc", "." * 20 + " ")}{cls("value", "Agentelligence, Skill-Finder")}'))
    rows.append(tspan(410, "251.54", f'{cls("cc", ". ")}{cls("key", "Focus")}: {cls("cc", "." * 26 + " ")}{cls("value", "Multi-agent orchestration")}'))
    rows.append(tspan(410, "270.00", f'{cls("cc", ". ")}{cls("key", "Building")}: {cls("cc", "." * 15 + " ")}{cls("value", "SKILLS.md, Methodology Frameworks")}'))
    rows.append(tspan(410, "288.46", f'{cls("cc", ". ")}{cls("key", "Hobbies.Software")}: {cls("cc", "." * 17 + " ")}{cls("value", "AI systems, coding, PKM")}'))
    rows.append(tspan(410, "306.92", f'{cls("cc", ". ")}{cls("key", "Hobbies.Hardware")}: {cls("cc", "." * 15)}{cls("value", "PC building, engine tuning")}'))
    rows.append(tspan(410, "325.38", f'{cls("cc", ". ")}{cls("key", "Lifestyle Hobbies")}: {cls("cc", "." * 10 + " ")}{cls("value", "Strength training, kickboxing")}'))
    rows.append(tspan(410, "343.85", cls("cc", ". ")))
    rows.append(tspan(410, "362.31", "- Contact " + "─" * 36 + "–" * 12 + "─" * 3))
    rows.append(tspan(410, "380.77", f'{cls("cc", ". ")}{cls("key", "Work Email")}: {cls("cc", "." * 22 + " ")}{cls("value", "thecorbinfloyd@gmail.com")}'))
    rows.append(tspan(410, "399.23", f'{cls("cc", ". ")}{cls("key", "LinkedIn")}: {cls("cc", "." * 26 + " ")}{cls("value", "corbin-floyd-000b22275")}'))
    rows.append(tspan(410, "417.69", cls("cc", ". ")))
    rows.append(tspan(410, "436.15", "- GitHub Stats " + "─" * 34 + "–" * 12))

    rows.append(
        tspan(410, "454.62", f'{cls("cc", ". ")}{cls("key", "Repos")}:')
        + tspan(472, "454.62", cls("cc", " .... "))
        + tspan(510, "454.62", cls("value", str(values["repos"])))
        + tspan(545, "454.62", f'    {{{cls("key", "Contributed")}:')
        + tspan(669, "454.62", cls("value", f'{int(values["contributed"]):5d}'))
        + tspan(710, "454.62", "}")
        + tspan(720, "454.62", "|")
        + tspan(744, "454.62", f'{cls("key", "Stars")}:')
        + tspan(802, "454.62", cls("cc", "." * 14))
        + tspan(925, "454.62", cls("value", str(values["stars"])))
    )
    rows.append(
        tspan(410, "473.08", f'{cls("cc", ". ")}{cls("key", "Commits")}:')
        + tspan(488, "473.08", cls("cc", "." * 21))
        + tspan(675, "473.08", cls("value", f'{int(values["commits"]):5d}'))
        + tspan(720, "473.08", "|")
        + tspan(744, "473.08", f'{cls("key", "Followers")}:')
        + tspan(838, "473.08", cls("cc", "." * 10))
        + tspan(925, "473.08", cls("value", str(values["followers"])))
    )
    rows.append(
        tspan(410, "491.54", f'{cls("cc", ". ")}{cls("key", "Lines of Code on GitHub")}:')
        + tspan(642, "491.54", cls("value", f'  {int(values["loc_net"]):,} '))
        + tspan(711, "491.54", " | ")
        + tspan(730, "491.54", cls("addColor", f' ({int(values["loc_add"]):,}++'))
        + tspan(812, "491.54", "  ,")
        + tspan(829, "491.54", cls("delColor", f'  {int(values["loc_del"]):,}--'))
        + tspan(899, "491.54", "  )")
    )
    rows.append(
        tspan(410, "510.00", f'{cls("cc", ". ")}{cls("key", "Updated")}:')
        + tspan(500, "510.00", cls("cc", "." * 17))
        + tspan(650, "510.00", cls("value", str(values["updated"])))
        + tspan(720, "510.00", "|")
        + tspan(744, "510.00", f'{cls("key", "Since")}:')
        + tspan(805, "510.00", cls("cc", "." * 9))
        + tspan(905, "510.00", cls("value", str(values["since"])))
    )
    return "".join(rows)


def build_svg(filename: str, theme: dict[str, str], values: dict[str, int | str | None]) -> str:
    portrait_rows = build_portrait(ROOT / theme["portrait"])
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="985" height="530" viewBox="0 0 985 530" role="img" aria-labelledby="title desc">
<title id="title">Corbin Floyd GitHub profile card - {theme["mode"]} mode</title>
<desc id="desc">{theme["mode"].capitalize()}-mode ASCII portrait and aligned terminal-style profile details.</desc>
<style>
@font-face {{ src: local("SF Mono"), local("SFMono-Regular"), local("Menlo"), local("Consolas"); font-family: "ProfileMono"; font-display: swap; }}
text, tspan {{ white-space: pre; font-variant-ligatures: none; }}
.key {{ fill: {theme["key"]}; }}
.value {{ fill: {theme["value"]}; }}
.addColor {{ fill: {theme["add"]}; }}
.delColor {{ fill: {theme["delete"]}; }}
.cc {{ fill: {theme["muted"]}; }}
</style>
<rect x="0.5" y="0.5" width="984" height="529" rx="15" fill="{theme["bg"]}" stroke="{theme["border"]}"/>
<text x="18" y="30" fill="{theme["portrait_text"]}" xml:space="preserve" font-family="ProfileMono, SFMono-Regular, SF Mono, Menlo, Monaco, Consolas, Liberation Mono, monospace" font-size="12.9px" font-weight="500" font-variant-ligatures="none" text-rendering="geometricPrecision" stroke="{theme["portrait_stroke"]}" stroke-width="{theme["portrait_stroke_width"]}" paint-order="stroke fill">{portrait_rows}</text>
<text x="410" y="30" fill="{theme["text"]}" xml:space="preserve" font-family="ProfileMono, SFMono-Regular, SF Mono, Menlo, Monaco, Consolas, Liberation Mono, monospace" font-size="14.2px" font-weight="500">{build_panel(values)}</text>
</svg>'''


def main() -> None:
    values = collect_stats()
    for filename, theme in THEMES.items():
        (ROOT / filename).write_text(build_svg(filename, theme, values), encoding="utf-8")
    print(json.dumps(values, indent=2))
    print(
        "Note: 'Contributed' is the Andrew-style count of public affiliated "
        "repositories; annual_contributions is the rolling 365-day activity count."
    )


if __name__ == "__main__":
    main()
