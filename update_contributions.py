from __future__ import annotations

import datetime as dt
import json
import os
import re
import urllib.request
from pathlib import Path

USERNAME = "Nebulazer123"
ROOT = Path(__file__).resolve().parent
TOKEN = os.environ.get("GITHUB_TOKEN", "")
FALLBACK_CONTRIBUTIONS = 358
SVG_FILES = (ROOT / "light_mode.svg", ROOT / "dark_mode.svg")


def contribution_count() -> int:
    if not TOKEN:
        return FALLBACK_CONTRIBUTIONS

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
    payload = {
        "query": query,
        "variables": {
            "login": USERNAME,
            "from": (now - dt.timedelta(days=365)).isoformat(),
            "to": now.isoformat(),
        },
    }
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": f"{USERNAME}-profile-readme",
    }
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))

    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"]))

    return int(
        result["data"]["user"]["contributionsCollection"]
        ["contributionCalendar"]["totalContributions"]
    )


def replace_contribution_value(svg: str, value: int) -> str:
    formatted = f"{value:5d}"

    id_pattern = re.compile(
        r'(<tspan[^>]*id="contrib_data"[^>]*>)(.*?)(</tspan>)',
        re.DOTALL,
    )
    updated, count = id_pattern.subn(
        lambda match: match.group(1) + formatted + match.group(3),
        svg,
        count=1,
    )
    if count == 1:
        return updated

    coordinate_pattern = re.compile(
        r'(<tspan x="669" y="454\.62"><tspan class="value">)(.*?)(</tspan></tspan>)',
        re.DOTALL,
    )
    updated, count = coordinate_pattern.subn(
        lambda match: match.group(1) + formatted + match.group(3),
        svg,
        count=1,
    )
    if count != 1:
        raise RuntimeError("Could not locate the Contributed value in the SVG")
    return updated


def main() -> None:
    try:
        count = contribution_count()
    except Exception as exc:
        print(f"Contribution query failed; using fallback {FALLBACK_CONTRIBUTIONS}: {exc}")
        count = FALLBACK_CONTRIBUTIONS

    for path in SVG_FILES:
        svg = path.read_text(encoding="utf-8")
        path.write_text(replace_contribution_value(svg, count), encoding="utf-8")

    print(f"Rolling 365-day GitHub contributions: {count}")


if __name__ == "__main__":
    main()
