from pathlib import Path

import pandas as pd

TEAMS_PATH = Path("data/processed/teams.csv")
OUT_PATH = Path("data/processed/team_ratings.csv")

# FIFA ranking points, June 2026-ish.
# Add/edit values as needed. Unknowns get a conservative default below.
FIFA_POINTS = {
    "Argentina": 1877.27,
    "Spain": 1874.71,
    "France": 1870.70,
    "England": 1828.02,
    "Portugal": 1767.85,
    "Brazil": 1765.86,
    "Morocco": 1755.10,
    "Netherlands": 1753.57,
    "Belgium": 1742.24,
    "Germany": 1735.77,
    "Croatia": 1714.87,
    "Colombia": 1698.35,
    "Mexico": 1687.48,
    "Senegal": 1684.07,
    "Uruguay": 1673.07,
    "Switzerland": 1660.00,
    "Japan": 1645.00,
    "United States": 1635.00,
    "Iran": 1625.00,
    "Austria": 1620.00,
    "South Korea": 1615.00,
    "Ecuador": 1610.00,
    "Australia": 1600.00,
    "Türkiye": 1595.00,
    "Czechia": 1590.00,
    "Norway": 1585.00,
    "Ivory Coast": 1580.00,
    "Algeria": 1575.00,
    "Canada": 1570.00,
    "Egypt": 1565.00,
    "Ghana": 1560.00,
    "Tunisia": 1555.00,
    "Paraguay": 1550.00,
    "Saudi Arabia": 1545.00,
    "South Africa": 1535.00,
    "Qatar": 1530.00,
    "Bosnia-Herzegovina": 1525.00,
    "New Zealand": 1515.00,
    "Congo DR": 1510.00,
    "Uzbekistan": 1505.00,
    "Iraq": 1500.00,
    "Jordan": 1495.00,
    "Panama": 1490.00,
    "Haiti": 1480.00,
    "Cape Verde": 1475.00,
    "Curaçao": 1470.00,
    "Sweden": 1650.00,
    "Scotland": 1670.00,
}

DEFAULT_RATING = 1450.0


def main():
    teams = pd.read_csv(TEAMS_PATH)
    out = teams[["team"]].drop_duplicates().copy()

    out["rating"] = out["team"].map(FIFA_POINTS).fillna(DEFAULT_RATING)
    out = out.sort_values("rating", ascending=False)

    missing = out[out["rating"] == DEFAULT_RATING]["team"].tolist()

    if missing:
        print("Teams using default rating:")
        for team in missing:
            print(f"- {team}")

    out.to_csv(OUT_PATH, index=False)

    print(f"Saved {OUT_PATH}")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()