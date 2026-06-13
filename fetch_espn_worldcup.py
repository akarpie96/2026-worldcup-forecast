import json
from pathlib import Path
from datetime import datetime, timezone

import requests

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
DATE_RANGE = "20260611-20260719"

DATA_DIR = Path("data/raw")
DATA_DIR.mkdir(parents=True, exist_ok=True)


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
    output = {
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "espn_public_scoreboard",
        "data": payload,
    }

    path = DATA_DIR / filename

    with open(path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Saved {path}")


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


def inspect_forecast_variables(payload):
    events = payload.get("events", [])

    if not events:
        print("\nNo events found to inspect.")
        return

    first_event = events[0]

    print("\nTop-level event keys:")
    print(list(first_event.keys()))

    competitions = first_event.get("competitions", [])
    competition = competitions[0] if competitions else {}
    
    print("\nODDS OBJECT:")
    print(json.dumps(competition.get("odds"), indent=2))
    print("\nCompetition keys:")
    print(list(competition.keys()))

    possible_forecast_keys = [
        "odds",
        "predictor",
        "probabilities",
        "probability",
        "winProbability",
        "pickcenter",
        "againstTheSpread",
    ]

    print("\nSearching for forecast/odds-like keys...")

    found = []

    def recursive_find(obj, path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key

                if key in possible_forecast_keys:
                    found.append(current_path)

                recursive_find(value, current_path)

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                recursive_find(item, f"{path}[{i}]")

    recursive_find(first_event)

    if found:
        print("Found possible forecast/odds fields:")
        for item in found:
            print(f"- {item}")
    else:
        print("No obvious odds/probability fields found in first event.")

    print("\nFirst event preview:")
    print(json.dumps(first_event, indent=2)[:15000])


def main():
    payload = fetch_espn_world_cup()

    save_json("espn_2026_scoreboard.json", payload)
    summarize_events(payload)
    inspect_forecast_variables(payload)

    print("\nDone.")


if __name__ == "__main__":
    main()