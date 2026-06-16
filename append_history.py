import json
from pathlib import Path

import pandas as pd

FORECAST_PATH = Path("data/processed/tournament_forecast.csv")
BRACKET_PATH = Path("data/processed/bracket_forecast.csv")
METADATA_PATH = Path("data/processed/metadata.json")

FORECAST_HISTORY_PATH = Path("data/processed/forecast_history.csv")
BRACKET_HISTORY_PATH = Path("data/processed/bracket_history.csv")


def get_timestamp():
    with open(METADATA_PATH, "r") as f:
        metadata = json.load(f)

    return metadata["last_updated_utc"]


def append_csv(new_rows, history_path, subset_cols):
    if history_path.exists():
        existing = pd.read_csv(history_path)
        combined = pd.concat([existing, new_rows], ignore_index=True)
    else:
        combined = new_rows.copy()

    combined = combined.drop_duplicates(subset=subset_cols, keep="last")
    combined.to_csv(history_path, index=False)

    print(f"Saved {history_path}")


def main():
    timestamp = get_timestamp()

    forecast = pd.read_csv(FORECAST_PATH)
    forecast["timestamp_utc"] = timestamp

    forecast_cols = [
        "timestamp_utc",
        "team",
        "win_group_pct",
        "advance_pct",
        "round_16_pct",
        "quarterfinal_pct",
        "semifinal_pct",
        "final_pct",
        "champion_pct",
    ]

    append_csv(
        forecast[forecast_cols],
        FORECAST_HISTORY_PATH,
        subset_cols=["timestamp_utc", "team"],
    )

    bracket = pd.read_csv(BRACKET_PATH)
    bracket["timestamp_utc"] = timestamp

    bracket_cols = [
        "timestamp_utc",
        "slot",
        "team",
        "probability",
    ]

    append_csv(
        bracket[bracket_cols],
        BRACKET_HISTORY_PATH,
        subset_cols=["timestamp_utc", "slot", "team"],
    )


if __name__ == "__main__":
    main()