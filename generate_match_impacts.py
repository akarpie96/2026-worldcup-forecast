import re
from pathlib import Path

import numpy as np
import pandas as pd

MATCHES_PATH = Path("data/processed/matches.csv")
RATINGS_PATH = Path("data/processed/team_ratings.csv")
FORECAST_PATH = Path("data/processed/tournament_forecast.csv")
MATCH_IMPACTS_OUT_PATH = Path("data/processed/match_impacts.csv")

IMPACT_SIMS = 1000
RANDOM_SEED = 123
MAX_MATCHES = 12


def make_match_key(row):
    return f"{row['date_utc']}|{row['home_team']}|{row['away_team']}"


def add_match_keys(matches):
    matches = matches.copy()
    matches["match_key"] = matches.apply(make_match_key, axis=1)
    return matches


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


def forced_score(result):
    if result == "home_win":
        return 1, 0
    if result == "draw":
        return 1, 1
    if result == "away_win":
        return 0, 1
    raise ValueError(f"Unknown forced result: {result}")


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


def simulate_group_stage(
    group_matches,
    ratings,
    rng,
    forced_match_key=None,
    forced_result=None,
):
    group_results = {}
    third_rows = []

    for group, gm in group_matches.groupby("group"):
        teams = sorted(set(gm["home_team"]).union(set(gm["away_team"])))
        table = init_table(teams)

        for _, row in gm.iterrows():
            home = row["home_team"]
            away = row["away_team"]
            match_key = row["match_key"]

            if forced_match_key is not None and match_key == forced_match_key:
                hg, ag = forced_score(forced_result)
            elif bool(row["completed"]):
                hg = int(row["home_score"])
                ag = int(row["away_score"])
            else:
                rh = ratings.get(home, 1500)
                ra = ratings.get(away, 1500)
                p_home, p_draw, p_away = wdl_probs(rh, ra)
                result = rng.choice(["home", "draw", "away"], p=[p_home, p_draw, p_away])
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
        candidates = [third_by_group[g] for g in allowed_groups if g in third_by_group]
        return candidates[0] if candidates else None

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
        slot = f"{output_prefix} {match_num} Winner"

        winners[slot] = winner
        counters[winner][counters_key] += 1

    return winners


def run_forecast_scenario(
    matches,
    ratings,
    n_sims,
    seed,
    forced_match_key=None,
    forced_result=None,
):
    rng = np.random.default_rng(seed)

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
            "win_group": 0,
            "advance": 0,
            "round_16": 0,
            "quarterfinal": 0,
            "semifinal": 0,
            "final": 0,
            "champion": 0,
        }
        for team in all_teams
    }

    for _ in range(n_sims):
        group_results, slots, third_by_group = simulate_group_stage(
            group_matches,
            ratings,
            rng,
            forced_match_key=forced_match_key,
            forced_result=forced_result,
        )

        for _, table in group_results.items():
            for _, row in table.iterrows():
                team = row["team"]
                counters[team]["sims"] += 1

                if row["place"] == 1:
                    counters[team]["win_group"] += 1
                    counters[team]["advance"] += 1
                elif row["place"] == 2:
                    counters[team]["advance"] += 1

        for team in third_by_group.values():
            counters[team]["advance"] += 1

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
            slot = f"Round of 32 {match_num} Winner"

            r32_winners[slot] = winner
            counters[winner]["round_16"] += 1

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
                "win_group_pct": c["win_group"] / sims,
                "advance_pct": c["advance"] / sims,
                "round_16_pct": c["round_16"] / sims,
                "quarterfinal_pct": c["quarterfinal"] / sims,
                "semifinal_pct": c["semifinal"] / sims,
                "final_pct": c["final"] / sims,
                "champion_pct": c["champion"] / sims,
            }
        )

    return pd.DataFrame(rows)


def get_team_metric(forecast_df, team, metric):
    vals = forecast_df.loc[forecast_df["team"] == team, metric]
    return float(vals.iloc[0]) if not vals.empty else 0.0


def concrete_upcoming_matches(matches):
    placeholder_pattern = "Winner|Loser|Group|Place|Semifinal|Quarterfinal|Round of 16|Round of 32"

    upcoming = matches[matches["completed"] == False].copy()

    upcoming = upcoming[
        ~upcoming["home_team"].astype(str).str.contains(placeholder_pattern, na=False)
    ]
    upcoming = upcoming[
        ~upcoming["away_team"].astype(str).str.contains(placeholder_pattern, na=False)
    ]

    upcoming["date_parsed"] = pd.to_datetime(upcoming["date_utc"], utc=True)
    upcoming = upcoming.sort_values("date_parsed").head(MAX_MATCHES)

    return upcoming


def main():
    matches = pd.read_csv(MATCHES_PATH)
    matches = add_match_keys(matches)

    ratings_df = pd.read_csv(RATINGS_PATH)
    ratings = dict(zip(ratings_df["team"], ratings_df["rating"]))

    baseline = pd.read_csv(FORECAST_PATH)
    upcoming = concrete_upcoming_matches(matches)

    impact_rows = []

    for idx, row in upcoming.iterrows():
        match_key = row["match_key"]
        home = row["home_team"]
        away = row["away_team"]

        print(f"Calculating impacts for {home} vs {away}")

        scenario_results = {}

        for scenario_name, forced_result in [
            ("home_win", "home_win"),
            ("draw", "draw"),
            ("away_win", "away_win"),
        ]:
            scenario_forecast = run_forecast_scenario(
                matches=matches,
                ratings=ratings,
                n_sims=IMPACT_SIMS,
                seed=RANDOM_SEED + int(idx) + len(scenario_results) * 1000,
                forced_match_key=match_key,
                forced_result=forced_result,
            )

            scenario_results[scenario_name] = scenario_forecast

        baseline_home_advance = get_team_metric(baseline, home, "advance_pct")
        baseline_away_advance = get_team_metric(baseline, away, "advance_pct")
        baseline_home_champion = get_team_metric(baseline, home, "champion_pct")
        baseline_away_champion = get_team_metric(baseline, away, "champion_pct")

        row_out = {
            "match_key": match_key,
            "date_utc": row["date_utc"],
            "season_slug": row["season_slug"],
            "home_team": home,
            "away_team": away,
            "baseline_home_advance_pct": baseline_home_advance,
            "baseline_away_advance_pct": baseline_away_advance,
            "baseline_home_champion_pct": baseline_home_champion,
            "baseline_away_champion_pct": baseline_away_champion,
        }

        for scenario_name, scenario_forecast in scenario_results.items():
            home_adv = get_team_metric(scenario_forecast, home, "advance_pct")
            away_adv = get_team_metric(scenario_forecast, away, "advance_pct")
            home_champ = get_team_metric(scenario_forecast, home, "champion_pct")
            away_champ = get_team_metric(scenario_forecast, away, "champion_pct")

            row_out[f"{scenario_name}_home_advance_pct"] = home_adv
            row_out[f"{scenario_name}_away_advance_pct"] = away_adv
            row_out[f"{scenario_name}_home_champion_pct"] = home_champ
            row_out[f"{scenario_name}_away_champion_pct"] = away_champ

            row_out[f"{scenario_name}_home_advance_change_pts"] = (
                home_adv - baseline_home_advance
            ) * 100
            row_out[f"{scenario_name}_away_advance_change_pts"] = (
                away_adv - baseline_away_advance
            ) * 100
            row_out[f"{scenario_name}_home_champion_change_pts"] = (
                home_champ - baseline_home_champion
            ) * 100
            row_out[f"{scenario_name}_away_champion_change_pts"] = (
                away_champ - baseline_away_champion
            ) * 100

        home_adv_values = [
            row_out["home_win_home_advance_pct"],
            row_out["draw_home_advance_pct"],
            row_out["away_win_home_advance_pct"],
        ]
        away_adv_values = [
            row_out["home_win_away_advance_pct"],
            row_out["draw_away_advance_pct"],
            row_out["away_win_away_advance_pct"],
        ]

        home_champ_values = [
            row_out["home_win_home_champion_pct"],
            row_out["draw_home_champion_pct"],
            row_out["away_win_home_champion_pct"],
        ]
        away_champ_values = [
            row_out["home_win_away_champion_pct"],
            row_out["draw_away_champion_pct"],
            row_out["away_win_away_champion_pct"],
        ]

        advance_leverage_pts = (
            (max(home_adv_values) - min(home_adv_values))
            + (max(away_adv_values) - min(away_adv_values))
        ) * 100

        champion_leverage_pts = (
            (max(home_champ_values) - min(home_champ_values))
            + (max(away_champ_values) - min(away_champ_values))
        ) * 100

        row_out["advance_leverage_pts"] = advance_leverage_pts
        row_out["champion_leverage_pts"] = champion_leverage_pts
        row_out["leverage_score"] = advance_leverage_pts + champion_leverage_pts * 4

        impact_rows.append(row_out)

    impacts_df = pd.DataFrame(impact_rows)
    impacts_df = impacts_df.sort_values("leverage_score", ascending=False)
    impacts_df.to_csv(MATCH_IMPACTS_OUT_PATH, index=False)

    print(f"Saved {MATCH_IMPACTS_OUT_PATH}")
    print(impacts_df.head(20).to_string(index=False))


if __name__ == "__main__":
    main()