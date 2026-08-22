#!/usr/bin/env python3

import os
import json
import html
import urllib.request
import datetime
from pathlib import Path

USERNAME = os.getenv("PROFILE_USERNAME", "Sayandeepghosh")
TOKEN = os.environ["GITHUB_TOKEN"]

OUT = Path("assets")
OUT.mkdir(exist_ok=True)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "Sayandeepghosh-profile-generator",
}


def github_api(path):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers=HEADERS,
    )

    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())


def graphql(query, variables):
    payload = json.dumps(
        {
            "query": query,
            "variables": variables,
        }
    ).encode()

    headers = dict(HEADERS)
    headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers=headers,
        method="POST",
    )

    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode())

    if result.get("errors"):
        raise RuntimeError(result["errors"])

    return result["data"]


def esc(value):
    return html.escape(str(value))


def write_svg(filename, content):
    (OUT / filename).write_text(content, encoding="utf-8")


# ---------------------------------------------------------
# GitHub profile + repository statistics
# ---------------------------------------------------------

profile = github_api(f"/users/{USERNAME}")

repos = github_api(
    f"/users/{USERNAME}/repos?per_page=100&type=owner&sort=updated"
)

original_repos = [
    repo
    for repo in repos
    if not repo.get("fork", False)
    and not repo.get("archived", False)
]

stars = sum(repo.get("stargazers_count", 0) for repo in original_repos)
forks = sum(repo.get("forks_count", 0) for repo in original_repos)

public_repos = profile.get("public_repos", 0)
followers = profile.get("followers", 0)
following = profile.get("following", 0)

# ---------------------------------------------------------
# Languages
# ---------------------------------------------------------

languages = {}

for repo in original_repos:
    try:
        data = github_api(
            f"/repos/{USERNAME}/{repo['name']}/languages"
        )
    except Exception:
        continue

    for language, count in data.items():
        languages[language] = languages.get(language, 0) + count

language_total = sum(languages.values())

top_languages = sorted(
    languages.items(),
    key=lambda item: item[1],
    reverse=True,
)[:6]

LANGUAGE_COLORS = {
    "Python": "#3572A5",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "C++": "#f34b7d",
    "C": "#555555",
    "Java": "#b07219",
    "Kotlin": "#A97BFF",
    "Shell": "#89e051",
    "Jupyter Notebook": "#DA5B0B",
    "Dart": "#00B4AB",
    "Go": "#00ADD8",
    "Rust": "#dea584",
}

# ---------------------------------------------------------
# Contribution calendar / streaks
# ---------------------------------------------------------

current_streak = None
longest_streak = None
year_contributions = None

try:
    data = graphql(
        """
        query($login: String!) {
          user(login: $login) {
            contributionsCollection {
              contributionCalendar {
                totalContributions
                weeks {
                  contributionDays {
                    date
                    contributionCount
                  }
                }
              }
            }
          }
        }
        """,
        {"login": USERNAME},
    )

    calendar = (
        data["user"]["contributionsCollection"]["contributionCalendar"]
    )

    year_contributions = calendar["totalContributions"]

    days = []

    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            days.append(
                (
                    datetime.date.fromisoformat(day["date"]),
                    day["contributionCount"],
                )
            )

    days.sort()

    today = datetime.datetime.now(
        datetime.timezone.utc
    ).date()

    # Ignore an unfinished zero-contribution current day.
    if days and days[-1][0] == today and days[-1][1] == 0:
        days = days[:-1]

    current_streak = 0

    for _, count in reversed(days):
        if count > 0:
            current_streak += 1
        else:
            break

    longest_streak = 0
    running = 0

    for _, count in days:
        if count > 0:
            running += 1
            longest_streak = max(longest_streak, running)
        else:
            running = 0

except Exception as error:
    print("Contribution calendar unavailable:", error)

# ---------------------------------------------------------
# Main statistics SVG
# ---------------------------------------------------------

stats_svg = f'''<svg
  xmlns="http://www.w3.org/2000/svg"
  width="500"
  height="210"
  viewBox="0 0 500 210"
  role="img"
  aria-label="GitHub statistics"
>
<style>
  .title {{
    font: 600 20px -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;
    fill: #58a6ff;
  }}
  .label {{
    font: 500 13px -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;
    fill: #8b949e;
  }}
  .number {{
    font: 700 23px -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;
    fill: #c9d1d9;
  }}
  .footer {{
    font: 400 11px -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;
    fill: #6e7681;
  }}
</style>

<rect
  x="1"
  y="1"
  rx="10"
  width="498"
  height="208"
  fill="#0d1117"
  stroke="#30363d"
/>

<text x="24" y="36" class="title">
  {esc(USERNAME)} · GitHub Stats
</text>

<text x="35" y="86" class="number">{public_repos}</text>
<text x="35" y="108" class="label">Public repositories</text>

<text x="270" y="86" class="number">{stars}</text>
<text x="270" y="108" class="label">Stars earned</text>

<text x="35" y="153" class="number">{followers}</text>
<text x="35" y="175" class="label">Followers</text>

<text x="270" y="153" class="number">{forks}</text>
<text x="270" y="175" class="label">Repository forks</text>

<text x="24" y="198" class="footer">
  Generated daily from the GitHub API
</text>
</svg>
'''

write_svg("github-stats.svg", stats_svg)

# ---------------------------------------------------------
# Language SVG
# ---------------------------------------------------------

segments = []
legend = []

x = 25
bar_width = 450

for language, count in top_languages:
    percentage = (
        (count / language_total) * 100
        if language_total
        else 0
    )

    width = (percentage / 100) * bar_width

    color = LANGUAGE_COLORS.get(language, "#8b949e")

    segments.append(
        f'<rect x="{x:.2f}" y="55" '
        f'width="{width:.2f}" height="11" '
        f'fill="{color}" />'
    )

    x += width

for index, (language, count) in enumerate(top_languages):
    percentage = (
        (count / language_total) * 100
        if language_total
        else 0
    )

    column = index % 2
    row = index // 2

    lx = 30 + column * 235
    ly = 100 + row * 35

    color = LANGUAGE_COLORS.get(language, "#8b949e")

    legend.append(
        f'<circle cx="{lx}" cy="{ly - 4}" r="5" fill="{color}" />'
    )

    legend.append(
        f'<text x="{lx + 12}" y="{ly}" class="lang">'
        f'{esc(language)}</text>'
    )

    legend.append(
        f'<text x="{lx + 190}" y="{ly}" '
        f'class="pct" text-anchor="end">'
        f'{percentage:.1f}%</text>'
    )

languages_svg = f'''<svg
  xmlns="http://www.w3.org/2000/svg"
  width="500"
  height="210"
  viewBox="0 0 500 210"
  role="img"
  aria-label="Top programming languages"
>
<style>
  .title {{
    font: 600 20px -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;
    fill: #58a6ff;
  }}
  .lang {{
    font: 500 13px -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;
    fill: #c9d1d9;
  }}
  .pct {{
    font: 400 12px -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;
    fill: #8b949e;
  }}
  .footer {{
    font: 400 11px -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;
    fill: #6e7681;
  }}
</style>

<rect
  x="1"
  y="1"
  rx="10"
  width="498"
  height="208"
  fill="#0d1117"
  stroke="#30363d"
/>

<text x="24" y="36" class="title">Top Languages</text>

<clipPath id="barClip">
  <rect x="25" y="55" width="450" height="11" rx="5"/>
</clipPath>

<g clip-path="url(#barClip)">
  {''.join(segments)}
</g>

{''.join(legend)}

<text x="24" y="198" class="footer">
  Calculated from original public repositories
</text>
</svg>
'''

write_svg("top-languages.svg", languages_svg)

# ---------------------------------------------------------
# Streak SVG
# ---------------------------------------------------------

current_text = (
    str(current_streak)
    if current_streak is not None
    else "—"
)

longest_text = (
    str(longest_streak)
    if longest_streak is not None
    else "—"
)

contribution_text = (
    str(year_contributions)
    if year_contributions is not None
    else "—"
)

streak_svg = f'''<svg
  xmlns="http://www.w3.org/2000/svg"
  width="650"
  height="175"
  viewBox="0 0 650 175"
  role="img"
  aria-label="GitHub contribution streak"
>
<style>
  .title {{
    font: 600 20px -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;
    fill: #58a6ff;
  }}
  .value {{
    font: 700 28px -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;
    fill: #c9d1d9;
  }}
  .label {{
    font: 500 13px -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;
    fill: #8b949e;
  }}
  .footer {{
    font: 400 11px -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;
    fill: #6e7681;
  }}
</style>

<rect
  x="1"
  y="1"
  rx="10"
  width="648"
  height="173"
  fill="#0d1117"
  stroke="#30363d"
/>

<text x="24" y="36" class="title">
  Contribution Activity
</text>

<text x="75" y="94" class="value"
      text-anchor="middle">{current_text}</text>
<text x="75" y="119" class="label"
      text-anchor="middle">Current streak</text>

<text x="325" y="94" class="value"
      text-anchor="middle">{longest_text}</text>
<text x="325" y="119" class="label"
      text-anchor="middle">Longest streak</text>

<text x="560" y="94" class="value"
      text-anchor="middle">{contribution_text}</text>
<text x="560" y="119" class="label"
      text-anchor="middle">Last 12 months</text>

<text x="24" y="157" class="footer">
  Public contribution data · regenerated daily
</text>
</svg>
'''

write_svg("streak.svg", streak_svg)

print("Generated:")
for file in sorted(OUT.glob("*.svg")):
    print(" -", file)
