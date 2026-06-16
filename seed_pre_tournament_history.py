import subprocess
from pathlib import Path

import pandas as pd

COMMIT = "e088d9f"
BASELINE_TIMESTAMP = "2026-06-11T18:00:00+00:00"

HISTORY_PATH = Path("data/processed/forecast_history.csv")


def load_forecast_from_git(commit):
    csv_text = subprocess.check_output(
        ["git", "show", f"{commit}:data/processed/tournament_forecast.csv"],
        text=True,
    )

    temp_path = Path("/tmp/pre_tournament_forecast.csv")
    temp_path.write_text(csv_text)

    return pd.read_csv(temp_path)


def main():
    baseline = load_forecast_from_git(COMMIT)
    baseline["timestamp_utc"] = BASELINE_TIMESTAMP

    if "win_group_pct" not in baseline.columns:
        baseline["win_group_pct"] = pd.NA

    cols = [
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

    baseline = baseline[cols]

    history = pd.read_csv(HISTORY_PATH)

    combined = pd.concat([baseline, history], ignore_index=True)
    combined = combined.drop_duplicates(
        subset=["timestamp_utc", "team"],
        keep="last",
    )

    combined["timestamp_sort"] = pd.to_datetime(
    combined["timestamp_utc"],
    utc=True,
    format="mixed",
    )   
    combined = combined.sort_values(["timestamp_sort", "team"])
    combined = combined.drop(columns=["timestamp_sort"])

    combined.to_csv(HISTORY_PATH, index=False)

    print(f"Seeded pre-tournament baseline from {COMMIT}")
    print(f"Saved {HISTORY_PATH}")
    print(combined.head(10).to_string(index=False))


if __name__ == "__main__":
    main()