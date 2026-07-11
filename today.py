from __future__ import annotations

import calendar
import datetime as dt
import json
import os
import re
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

USERNAME = "Nebulazer123"
ROOT = Path(__file__).resolve().parent
TOKEN = os.environ.get("GITHUB_TOKEN", "")
BIRTH_TIME = dt.datetime(2003, 7, 21, 3, 0, tzinfo=ZoneInfo("America/Chicago"))
SVG_FILES = (ROOT / "light_mode.svg", ROOT / "dark_mode.svg")


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


def existing_value(element_id: str, default: int | str) -> int | str:
    pattern = re.compile(
        rf'<tspan[^>]*id="{re.escape(element_id)}"[^>]*>(.*?)</tspan>',
        re.DOTALL,
    )
    for path in SVG_FILES:
        if not path.exists():
            continue
        match = pattern.search(path.read_text(encoding="utf-8"))
        if not match:
            continue
        raw = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        number = re.sub(r"[^0-9-]", "", raw)
        if isinstance(default, int) and number:
            return int(number)
        return raw or default
    return default


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
    values: dict[str, int | str | None] = {
        "repos": existing_value("repo_data", 12),
        "contributed": existing_value("contrib_data", 12),
        "stars": existing_value("star_data", 0),
        "commits": existing_value("commit_data", 233),
        "followers": existing_value("follower_data", 0),
        "loc_add": existing_value("loc_add", 288353),
        "loc_del": existing_value("loc_del", 68804),
        "loc_net": existing_value("loc_data", 219549),
        "since": existing_value("since_data", "2016"),
        "annual_contributions": None,
    }

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


def replace_id(text: str, element_id: str, value: str) -> str:
    pattern = re.compile(
        rf'(<tspan[^>]*id="{re.escape(element_id)}"[^>]*>)(.*?)(</tspan>)',
        re.DOTALL,
    )
    updated, count = pattern.subn(rf"\g<1>{value}\g<3>", text, count=1)
    if count != 1:
        raise RuntimeError(f"Expected exactly one {element_id} element")
    return updated


def update_svg(path: Path, values: dict[str, int | str | None]) -> None:
    text = path.read_text(encoding="utf-8")
    replacements = {
        "uptime_data": str(values["uptime"]),
        "repo_data": f"{int(values['repos']):d}",
        "contrib_data": f"{int(values['contributed']):5d}",
        "star_data": f"{int(values['stars']):d}",
        "commit_data": f"{int(values['commits']):5d}",
        "follower_data": f"{int(values['followers']):d}",
        "loc_data": f"  {int(values['loc_net']):,} ",
        "loc_add": f" ({int(values['loc_add']):,}++",
        "loc_del": f"  {int(values['loc_del']):,}--",
        "updated_data": str(values["updated"]),
        "since_data": str(values["since"]),
    }
    for element_id, value in replacements.items():
        text = replace_id(text, element_id, value)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    values = collect_stats()
    for svg in SVG_FILES:
        update_svg(svg, values)
    print(json.dumps(values, indent=2))
    print(
        "Note: 'Contributed' is the Andrew-style count of public affiliated "
        "repositories. annual_contributions is the rolling 365-day activity count."
    )


if __name__ == "__main__":
    main()
