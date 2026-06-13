import json
import re
from pathlib import Path

import pandas as pd

RAW_PATH = Path("data/raw/espn_2026_scoreboard.json")
OUT_DIR = Path("data/processed")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_group(alt_game_note):
    if not alt_game_note:
        return None

    match = re.search(r"Group ([A-L])", alt_game_note)
    return match.group(1) if match else None


def parse_score(score):
    try:
        return int(score)
    except (TypeError, ValueError):
        return None


def main():
    with open(RAW_PATH, "r") as f:
        raw = json.load(f)

    payload = raw["data"]
    events = payload.get("events", [])

    rows = []

    for event in events:
        event_id = event.get("id")
        event_name = event.get("name")
        event_date = event.get("date")
        season_slug = event.get("season", {}).get("slug")

        competitions = event.get("competitions", [])
        if not competitions:
            continue

        comp = competitions[0]
        status = comp.get("status", {}).get("type", {})
        status_name = status.get("name")
        status_desc = status.get("description")
        completed = status.get("completed", False)

        alt_game_note = comp.get("altGameNote")
        group = extract_group(alt_game_note)

        competitors = comp.get("competitors", [])
        if len(competitors) != 2:
            continue

        parsed_teams = []

        for c in competitors:
            team = c.get("team", {})
            parsed_teams.append(
                {
                    "team_id": team.get("id"),
                    "team": team.get("displayName"),
                    "abbrev": team.get("abbreviation"),
                    "home_away": c.get("homeAway"),
                    "score": parse_score(c.get("score")),
                    "winner": c.get("winner"),
                    "form": c.get("form"),
                }
            )

        home = next((t for t in parsed_teams if t["home_away"] == "home"), parsed_teams[0])
        away = next((t for t in parsed_teams if t["home_away"] == "away"), parsed_teams[1])

        rows.append(
            {
                "match_id": event_id,
                "date_utc": event_date,
                "name": event_name,
                "season_slug": season_slug,
                "group": group,
                "alt_game_note": alt_game_note,
                "status_name": status_name,
                "status_desc": status_desc,
                "completed": completed,
                "home_team_id": home["team_id"],
                "home_team": home["team"],
                "home_abbrev": home["abbrev"],
                "home_score": home["score"],
                "home_form": home["form"],
                "away_team_id": away["team_id"],
                "away_team": away["team"],
                "away_abbrev": away["abbrev"],
                "away_score": away["score"],
                "away_form": away["form"],
            }
        )

    df = pd.DataFrame(rows)

    df.to_csv(OUT_DIR / "matches.csv", index=False)

    group_stage = df[df["group"].notna()].copy()
    group_stage.to_csv(OUT_DIR / "group_stage_matches.csv", index=False)

    teams = pd.concat(
        [
            group_stage[["group", "home_team", "home_abbrev"]].rename(
                columns={"home_team": "team", "home_abbrev": "abbrev"}
            ),
            group_stage[["group", "away_team", "away_abbrev"]].rename(
                columns={"away_team": "team", "away_abbrev": "abbrev"}
            ),
        ]
    ).drop_duplicates()

    teams = teams.sort_values(["group", "team"])
    teams.to_csv(OUT_DIR / "teams.csv", index=False)

    print(f"Saved {OUT_DIR / 'matches.csv'}")
    print(f"Saved {OUT_DIR / 'group_stage_matches.csv'}")
    print(f"Saved {OUT_DIR / 'teams.csv'}")
    print(f"Parsed {len(df)} total matches")
    print(f"Parsed {len(group_stage)} group-stage matches")
    print(f"Parsed {len(teams)} teams")


if __name__ == "__main__":
    main()