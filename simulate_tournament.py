import re
from pathlib import Path

import numpy as np
import pandas as pd

MATCHES_PATH = Path("data/processed/matches.csv")
RATINGS_PATH = Path("data/processed/team_ratings.csv")
OUT_PATH = Path("data/processed/tournament_forecast.csv")

N_SIMS = 10000
RANDOM_SEED = 42


def win_prob(rating_a, rating_b):
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def simulate_knockout_winner(team_a, team_b, ratings, rng):
    ra = ratings.get(team_a, 1500)
    rb = ratings.get(team_b, 1500)
    return team_a if rng.random() < win_prob(ra, rb) else team_b


def wdl_probs(rating_a, rating_b):
    p_a_no_draw = win_prob(rating_a, rating_b)
    gap = abs(rating_a - rating_b)
    p_draw = max(0.16, 0.30 - gap / 2000)
    remaining = 1 - p_draw
    return remaining * p_a_no_draw, p_draw, remaining * (1 - p_a_no_draw)


def simulate_score(result, rng):
    if result == "draw":
        g = rng.choice([0, 1, 2], p=[0.25, 0.55, 0.20])
        return g, g

    margin = rng.choice([1, 2, 3, 4], p=[0.62, 0.25, 0.10, 0.03])
    loser = rng.choice([0, 1, 2], p=[0.55, 0.35, 0.10])
    winner = loser + margin

    return (winner, loser) if result == "home" else (loser, winner)


def init_table(teams):
    return {
        t: {
            "team": t,
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "gf": 0,
            "ga": 0,
            "gd": 0,
            "points": 0,
        }
        for t in teams
    }


def apply_match(table, home, away, hg, ag):
    table[home]["played"] += 1
    table[away]["played"] += 1

    table[home]["gf"] += hg
    table[home]["ga"] += ag
    table[away]["gf"] += ag
    table[away]["ga"] += hg

    table[home]["gd"] = table[home]["gf"] - table[home]["ga"]
    table[away]["gd"] = table[away]["gf"] - table[away]["ga"]

    if hg > ag:
        table[home]["wins"] += 1
        table[away]["losses"] += 1
        table[home]["points"] += 3
    elif hg < ag:
        table[away]["wins"] += 1
        table[home]["losses"] += 1
        table[away]["points"] += 3
    else:
        table[home]["draws"] += 1
        table[away]["draws"] += 1
        table[home]["points"] += 1
        table[away]["points"] += 1


def rank_table(table, rng):
    df = pd.DataFrame(table.values())
    df["random_tiebreaker"] = rng.random(len(df))

    df = df.sort_values(
        ["points", "gd", "gf", "random_tiebreaker"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)

    df["place"] = np.arange(1, len(df) + 1)
    return df


def simulate_group_stage(group_matches, ratings, rng):
    group_results = {}
    third_rows = []

    for group, gm in group_matches.groupby("group"):
        teams = sorted(set(gm["home_team"]).union(set(gm["away_team"])))
        table = init_table(teams)

        for _, row in gm.iterrows():
            home = row["home_team"]
            away = row["away_team"]

            if bool(row["completed"]):
                hg = int(row["home_score"])
                ag = int(row["away_score"])
            else:
                rh = ratings.get(home, 1500)
                ra = ratings.get(away, 1500)
                p_home, p_draw, p_away = wdl_probs(rh, ra)

                result = rng.choice(
                    ["home", "draw", "away"],
                    p=[p_home, p_draw, p_away],
                )
                hg, ag = simulate_score(result, rng)

            apply_match(table, home, away, hg, ag)

        ranked = rank_table(table, rng)
        group_results[group] = ranked

        third = ranked[ranked["place"] == 3].copy()
        third["group"] = group
        third_rows.append(third)

    third_df = pd.concat(third_rows, ignore_index=True)
    third_df["random_tiebreaker"] = rng.random(len(third_df))

    third_df = third_df.sort_values(
        ["points", "gd", "gf", "random_tiebreaker"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)

    advancing_thirds = third_df.head(8).copy()

    slots = {}

    for group, table in group_results.items():
        slots[f"Group {group} Winner"] = table.loc[table["place"] == 1, "team"].iloc[0]
        slots[f"Group {group} 2nd Place"] = table.loc[table["place"] == 2, "team"].iloc[0]

    third_by_group = {
        row["group"]: row["team"]
        for _, row in advancing_thirds.iterrows()
    }

    return group_results, slots, third_by_group


def resolve_placeholder(name, slots, third_by_group):
    name = str(name)

    if name in slots:
        return slots[name]

    match = re.match(r"Third Place Group ([A-L/]+)", name)
    if match:
        allowed_groups = match.group(1).split("/")
        candidates = [
            third_by_group[group]
            for group in allowed_groups
            if group in third_by_group
        ]

        if not candidates:
            return None

        return candidates[0]

    return name


def simulate_stage(stage_matches, source_winners, output_prefix, counters_key, counters, ratings, rng):
    winners = {}

    stage_matches = stage_matches.sort_values("date_utc").reset_index(drop=True)

    for i, row in stage_matches.iterrows():
        match_num = i + 1

        home = source_winners.get(row["home_team"])
        away = source_winners.get(row["away_team"])

        if home is None or away is None:
            continue

        winner = simulate_knockout_winner(home, away, ratings, rng)

        winners[f"{output_prefix} {match_num} Winner"] = winner
        counters[winner][counters_key] += 1

    return winners


def main():
    rng = np.random.default_rng(RANDOM_SEED)

    matches = pd.read_csv(MATCHES_PATH)
    ratings_df = pd.read_csv(RATINGS_PATH)
    ratings = dict(zip(ratings_df["team"], ratings_df["rating"]))

    group_matches = matches[matches["group"].notna()].copy()
    group_matches = group_matches[~group_matches["home_team"].str.contains("Group", na=False)]
    group_matches = group_matches[~group_matches["away_team"].str.contains("Group", na=False)]

    knockout_matches = matches[
        matches["season_slug"].isin(
            [
                "round-of-32",
                "round-of-16",
                "quarterfinals",
                "semifinals",
                "3rd-place-match",
                "final",
            ]
        )
    ].copy()

    all_teams = sorted(set(group_matches["home_team"]).union(set(group_matches["away_team"])))

    counters = {
        team: {
            "sims": 0,
            "advance": 0,
            "round_16": 0,
            "quarterfinal": 0,
            "semifinal": 0,
            "final": 0,
            "champion": 0,
        }
        for team in all_teams
    }

    for _ in range(N_SIMS):
        group_results, slots, third_by_group = simulate_group_stage(
            group_matches,
            ratings,
            rng,
        )

        for _, table in group_results.items():
            for _, row in table.iterrows():
                team = row["team"]
                counters[team]["sims"] += 1

                if row["place"] in [1, 2]:
                    counters[team]["advance"] += 1

        for team in third_by_group.values():
            counters[team]["advance"] += 1

        # Round of 32
        r32_source = {}

        r32 = knockout_matches[knockout_matches["season_slug"] == "round-of-32"].copy()
        r32 = r32.sort_values("date_utc").reset_index(drop=True)

        r32_winners = {}

        for i, row in r32.iterrows():
            match_num = i + 1

            home = resolve_placeholder(row["home_team"], slots, third_by_group)
            away = resolve_placeholder(row["away_team"], slots, third_by_group)

            if home is None or away is None:
                continue

            winner = simulate_knockout_winner(home, away, ratings, rng)
            r32_winners[f"Round of 32 {match_num} Winner"] = winner
            counters[winner]["round_16"] += 1

        # Round of 16
        r16 = knockout_matches[knockout_matches["season_slug"] == "round-of-16"].copy()
        r16_winners = simulate_stage(
            r16,
            r32_winners,
            "Round of 16",
            "quarterfinal",
            counters,
            ratings,
            rng,
        )

        # Quarterfinals
        qf = knockout_matches[knockout_matches["season_slug"] == "quarterfinals"].copy()
        qf_winners = simulate_stage(
            qf,
            r16_winners,
            "Quarterfinal",
            "semifinal",
            counters,
            ratings,
            rng,
        )

        # Semifinals
        sf = knockout_matches[knockout_matches["season_slug"] == "semifinals"].copy()
        sf_winners = simulate_stage(
            sf,
            qf_winners,
            "Semifinal",
            "final",
            counters,
            ratings,
            rng,
        )

        # Final
        final = knockout_matches[knockout_matches["season_slug"] == "final"].copy()

        if not final.empty:
            row = final.sort_values("date_utc").iloc[0]

            home = sf_winners.get(row["home_team"])
            away = sf_winners.get(row["away_team"])

            if home is not None and away is not None:
                champion = simulate_knockout_winner(home, away, ratings, rng)
                counters[champion]["champion"] += 1

    rows = []

    for team, c in counters.items():
        sims = c["sims"]

        rows.append(
            {
                "team": team,
                "sims": sims,
                "advance_pct": c["advance"] / sims,
                "round_16_pct": c["round_16"] / sims,
                "quarterfinal_pct": c["quarterfinal"] / sims,
                "semifinal_pct": c["semifinal"] / sims,
                "final_pct": c["final"] / sims,
                "champion_pct": c["champion"] / sims,
            }
        )

    out = pd.DataFrame(rows).sort_values("champion_pct", ascending=False)
    out.to_csv(OUT_PATH, index=False)

    print(f"Saved {OUT_PATH}")
    print(out.head(30).to_string(index=False))


if __name__ == "__main__":
    main()