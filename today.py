from __future__ import annotations

import datetime as dt
import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

USERNAME = "Nebulazer123"
ROOT = Path(__file__).resolve().parent
SVG_FILES = (ROOT / "dark_mode.svg", ROOT / "light_mode.svg")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

FALLBACK = {
    "repo_data": "9",
    "star_data": "13",
    "contrib_data": "304",
    "follower_data": "0",
    "following_data": "1",
    "since_data": "2016",
}

DOT_WIDTHS = {
    "repo_data": 11,
    "star_data": 8,
    "contrib_data": 5,
    "follower_data": 4,
    "following_data": 7,
    "since_data": 5,
    "updated_data": 25,
}

def request_json(url: str, data: dict | None = None) -> dict | list:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-profile-readme",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))

def public_profile() -> dict:
    data = request_json(f"https://api.github.com/users/{USERNAME}")
    assert isinstance(data, dict)
    return data

def owned_repositories() -> list[dict]:
    repositories: list[dict] = []
    page = 1
    while True:
        data = request_json(
            f"https://api.github.com/users/{USERNAME}/repos"
            f"?type=owner&sort=updated&per_page=100&page={page}"
        )
        assert isinstance(data, list)
        repositories.extend(data)
        if len(data) < 100:
            break
        page += 1
    return repositories

def rolling_contributions() -> int | None:
    if not TOKEN:
        return None

    now = dt.datetime.now(dt.timezone.utc)
    start = now - dt.timedelta(days=365)
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
    payload = {
        "query": query,
        "variables": {
            "login": USERNAME,
            "from": start.isoformat(),
            "to": now.isoformat(),
        },
    }
    data = request_json("https://api.github.com/graphql", payload)
    if not isinstance(data, dict) or data.get("errors"):
        return None
    return int(
        data["data"]["user"]["contributionsCollection"]
        ["contributionCalendar"]["totalContributions"]
    )

def collect_stats() -> dict[str, str]:
    values = dict(FALLBACK)
    try:
        profile = public_profile()
        repos = owned_repositories()

        values["repo_data"] = str(profile.get("public_repos", values["repo_data"]))
        values["star_data"] = str(
            sum(int(repo.get("stargazers_count", 0)) for repo in repos if not repo.get("fork"))
        )
        values["follower_data"] = str(profile.get("followers", values["follower_data"]))
        values["following_data"] = str(profile.get("following", values["following_data"]))

        created_at = str(profile.get("created_at", ""))
        if created_at:
            values["since_data"] = created_at[:4]

        contributions = rolling_contributions()
        if contributions is not None:
            values["contrib_data"] = str(contributions)
    except Exception as exc:
        print(f"Using existing fallback values: {exc}")

    values["updated_data"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d UTC")
    return values

def update_svg(path: Path, values: dict[str, str]) -> None:
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    tree = ET.parse(path)
    root = tree.getroot()

    indexed = {
        element.attrib["id"]: element
        for element in root.iter()
        if "id" in element.attrib
    }

    for element_id, value in values.items():
        if element_id in indexed:
            indexed[element_id].text = value

        dots_id = f"{element_id}_dots"
        if dots_id in indexed:
            count = max(1, DOT_WIDTHS.get(element_id, 8) - len(value) + 1)
            indexed[dots_id].text = f" {'.' * count} "

    tree.write(path, encoding="UTF-8", xml_declaration=True)

def main() -> None:
    values = collect_stats()
    for svg in SVG_FILES:
        update_svg(svg, values)
    print(json.dumps(values, indent=2))

if __name__ == "__main__":
    main()
