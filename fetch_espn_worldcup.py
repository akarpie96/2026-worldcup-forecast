import json
from pathlib import Path
from datetime import datetime, timezone

import requests

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
DATE_RANGE = "20260611-20260719"

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def fetch_espn_world_cup():
    response = requests.get(
        BASE_URL,
        params={
            "limit": 1000,
            "dates": DATE_RANGE,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def save_json(filename, payload):
    fetched_at_utc = datetime.now(timezone.utc).isoformat()

    output = {
        "fetched_at_utc": fetched_at_utc,
        "source": "espn_public_scoreboard",
        "data": payload,
    }

    raw_path = RAW_DIR / filename

    with open(raw_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Saved {raw_path}")

    metadata_path = PROCESSED_DIR / "metadata.json"

    with open(metadata_path, "w") as f:
        json.dump(
            {
                "last_updated_utc": fetched_at_utc,
                "source": "espn_public_scoreboard",
            },
            f,
            indent=2,
        )

    print(f"Saved {metadata_path}")


def summarize_events(payload):
    events = payload.get("events", [])
    print(f"\nFetched {len(events)} matches")

    for event in events:
        event_id = event.get("id")
        name = event.get("name")
        date = event.get("date")
        status = event.get("status", {}).get("type", {}).get("description")

        competitions = event.get("competitions", [])
        competition = competitions[0] if competitions else {}

        competitors = competition.get("competitors", [])

        teams = []
        for competitor in competitors:
            team = competitor.get("team", {})
            display_name = team.get("displayName")
            score = competitor.get("score")
            teams.append(f"{display_name} {score}")

        print(f"{event_id} | {date} | {name} | {status} | {' vs '.join(teams)}")


def main():
    payload = fetch_espn_world_cup()
    save_json("espn_2026_scoreboard.json", payload)
    summarize_events(payload)
    print("\nDone.")


if __name__ == "__main__":
    main()