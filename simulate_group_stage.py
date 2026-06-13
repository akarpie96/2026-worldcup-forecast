import math
from pathlib import Path

import numpy as np
import pandas as pd

MATCHES_PATH = Path("data/processed/group_stage_matches.csv")
RATINGS_PATH = Path("data/processed/team_ratings.csv")
OUT_DIR = Path("data/processed")
OUT_DIR.mkdir(parents=True, exist_ok=True)

N_SIMS = 1000
RANDOM_SEED = 42


def expected_score(rating_a, rating_b):
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def win_draw_loss_probs(rating_a, rating_b):
    """
    Simple Elo-based soccer result model.
    Draw probability is highest when teams are close and shrinks as rating gap grows.
    """
    p_a_no_draw = expected_score(rating_a, rating_b)

    rating_gap = abs(rating_a - rating_b)
    draw_prob = max(0.16, 0.30 - rating_gap / 2000)

    remaining = 1 - draw_prob
    p_a_win = remaining * p_a_no_draw
    p_b_win = remaining * (1 - p_a_no_draw)

    return p_a_win, draw_prob, p_b_win


def simulate_score_from_result(result, rng):
    """
    Lightweight score generator for table tiebreakers.
    Not perfect, but good enough for MVP.
    """
    if result == "draw":
        goals = rng.choice([0, 1, 2], p=[0.25, 0.55, 0.20])
        return goals, goals

    margin = rng.choice([1, 2, 3, 4], p=[0.62, 0.25, 0.10, 0.03])
    loser_goals = rng.choice([0, 1, 2], p=[0.55, 0.35, 0.10])
    winner_goals = loser_goals + margin

    if result == "home":
        return winner_goals, loser_goals

    return loser_goals, winner_goals


def init_table(teams):
    table = {}

    for team in teams:
        table[team] = {
            "team": team,
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "gf": 0,
            "ga": 0,
            "gd": 0,
            "points": 0,
        }

    return table


def apply_match(table, home, away, home_goals, away_goals):
    table[home]["played"] += 1
    table[away]["played"] += 1

    table[home]["gf"] += home_goals
    table[home]["ga"] += away_goals
    table[away]["gf"] += away_goals
    table[away]["ga"] += home_goals

    table[home]["gd"] = table[home]["gf"] - table[home]["ga"]
    table[away]["gd"] = table[away]["gf"] - table[away]["ga"]

    if home_goals > away_goals:
        table[home]["wins"] += 1
        table[away]["losses"] += 1
        table[home]["points"] += 3
    elif home_goals < away_goals:
        table[away]["wins"] += 1
        table[home]["losses"] += 1
        table[away]["points"] += 3
    else:
        table[home]["draws"] += 1
        table[away]["draws"] += 1
        table[home]["points"] += 1
        table[away]["points"] += 1


def table_to_df(table, rng):
    df = pd.DataFrame(table.values())

    # Random is used as final tiebreaker where real FIFA tie rules are more complex.
    df["random_tiebreaker"] = rng.random(len(df))

    df = df.sort_values(
        ["points", "gd", "gf", "random_tiebreaker"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)

    df["place"] = np.arange(1, len(df) + 1)

    return df


def main():
    rng = np.random.default_rng(RANDOM_SEED)

    matches = pd.read_csv(MATCHES_PATH)
    ratings = pd.read_csv(RATINGS_PATH)

    rating_map = dict(zip(ratings["team"], ratings["rating"]))

    # Only actual group-stage matches between real teams.
    matches = matches[matches["group"].notna()].copy()
    matches = matches[~matches["home_team"].str.contains("Group", na=False)]
    matches = matches[~matches["away_team"].str.contains("Group", na=False)]

    teams_by_group = {}

    for group, group_matches in matches.groupby("group"):
        teams = sorted(
            set(group_matches["home_team"].dropna()).union(
                set(group_matches["away_team"].dropna())
            )
        )
        teams_by_group[group] = teams

    all_teams = sorted(set(matches["home_team"]).union(set(matches["away_team"])))

    counters = {
        team: {
            "sims": 0,
            "win_group": 0,
            "top_2": 0,
            "third": 0,
            "advance": 0,
            "avg_points_total": 0,
        }
        for team in all_teams
    }

    for sim in range(N_SIMS):
        group_tables = {}

        for group, teams in teams_by_group.items():
            table = init_table(teams)
            group_matches = matches[matches["group"] == group]

            for _, row in group_matches.iterrows():
                home = row["home_team"]
                away = row["away_team"]

                completed = bool(row["completed"])

                if completed and not pd.isna(row["home_score"]) and not pd.isna(row["away_score"]):
                    home_goals = int(row["home_score"])
                    away_goals = int(row["away_score"])
                else:
                    home_rating = rating_map.get(home, 1700)
                    away_rating = rating_map.get(away, 1700)

                    p_home, p_draw, p_away = win_draw_loss_probs(home_rating, away_rating)

                    result = rng.choice(
                        ["home", "draw", "away"],
                        p=[p_home, p_draw, p_away],
                    )

                    home_goals, away_goals = simulate_score_from_result(result, rng)

                apply_match(table, home, away, home_goals, away_goals)

            group_df = table_to_df(table, rng)
            group_df["group"] = group
            group_tables[group] = group_df

        third_place_rows = []

        for group, group_df in group_tables.items():
            for _, team_row in group_df.iterrows():
                team = team_row["team"]
                place = int(team_row["place"])

                counters[team]["sims"] += 1
                counters[team]["avg_points_total"] += team_row["points"]

                if place == 1:
                    counters[team]["win_group"] += 1
                    counters[team]["top_2"] += 1
                    counters[team]["advance"] += 1
                elif place == 2:
                    counters[team]["top_2"] += 1
                    counters[team]["advance"] += 1
                elif place == 3:
                    counters[team]["third"] += 1
                    third_place_rows.append(team_row)

        third_df = pd.DataFrame(third_place_rows)

        if not third_df.empty:
            third_df["random_tiebreaker"] = rng.random(len(third_df))
            third_df = third_df.sort_values(
                ["points", "gd", "gf", "random_tiebreaker"],
                ascending=[False, False, False, False],
            )

            advancing_thirds = third_df.head(8)

            for _, row in advancing_thirds.iterrows():
                counters[row["team"]]["advance"] += 1

    rows = []

    for team, c in counters.items():
        sims = c["sims"]

        rows.append(
            {
                "team": team,
                "sims": sims,
                "avg_points": c["avg_points_total"] / sims,
                "win_group_pct": c["win_group"] / sims,
                "top_2_pct": c["top_2"] / sims,
                "third_place_pct": c["third"] / sims,
                "advance_pct": c["advance"] / sims,
            }
        )

    results = pd.DataFrame(rows)
    results = results.sort_values("advance_pct", ascending=False)

    out_path = OUT_DIR / "group_stage_forecast.csv"
    results.to_csv(out_path, index=False)

    print(f"Saved {out_path}")
    print(results.head(20).to_string(index=False))


if __name__ == "__main__":
    main()