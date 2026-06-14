import json
from pathlib import Path

import pandas as pd
import streamlit as st

FORECAST_PATH = Path("data/processed/tournament_forecast.csv")
MATCHES_PATH = Path("data/processed/matches.csv")
TEAMS_PATH = Path("data/processed/teams.csv")
METADATA_PATH = Path("data/processed/metadata.json")


def pct(x):
    return f"{x * 100:.1f}%"


def get_last_updated():
    try:
        with open(METADATA_PATH, "r") as f:
            metadata = json.load(f)
        return metadata.get("last_updated_utc", "Unknown")
    except FileNotFoundError:
        return "Unknown"


def team_logo(team, logo_map):
    return logo_map.get(team, "")


def team_html(team, logo_map, size=26):
    logo = team_logo(team, logo_map)

    if logo:
        return (
            f'<div style="display:flex; align-items:center; gap:8px;">'
            f'<img src="{logo}" width="{size}" height="{size}" style="border-radius:50%;">'
            f'<span>{team}</span>'
            f'</div>'
        )

    return str(team)


def percent_bar(value, label=None):
    width = max(0, min(100, value * 100))
    text = label if label is not None else pct(value)

    return (
        f'<div style="display:flex; align-items:center; gap:10px; min-width:190px;">'
        f'<div style="width:130px; background:rgba(128,128,128,0.18); '
        f'border-radius:999px; height:16px;">'
        f'<div style="width:{width:.1f}%; background:#2E86DE; '
        f'height:16px; border-radius:999px;"></div>'
        f'</div>'
        f'<div style="min-width:48px; text-align:right; font-weight:700;">{text}</div>'
        f'</div>'
    )


st.set_page_config(
    page_title="2026 World Cup Forecast",
    page_icon="🌎",
    layout="wide",
)

st.markdown(
    """
    <style>
    .big-title {
        font-size: 46px;
        font-weight: 800;
        margin-bottom: 0px;
    }
    .subtitle {
        color: #666;
        font-size: 18px;
        margin-bottom: 6px;
    }
    .metric-card {
        padding: 18px;
        border-radius: 18px;
        border: 1px solid rgba(128,128,128,0.25);
        background: rgba(128,128,128,0.06);
        text-align: center;
        min-height: 160px;
    }
    .team-name {
        font-size: 18px;
        font-weight: 700;
        margin-top: 8px;
    }
    .team-prob {
        font-size: 34px;
        font-weight: 800;
        margin-top: 6px;
    }
    .small-muted {
        color: #777;
        font-size: 13px;
    }
    table {
        width: 100%;
        border-collapse: collapse;
    }
    th, td {
        padding: 12px 14px;
        border-bottom: 1px solid rgba(128,128,128,0.25);
        vertical-align: middle;
    }
    th {
        font-weight: 800;
        background: rgba(128,128,128,0.05);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

forecast = pd.read_csv(FORECAST_PATH)
matches = pd.read_csv(MATCHES_PATH)
teams = pd.read_csv(TEAMS_PATH)
last_updated = get_last_updated()

logo_map = dict(zip(teams["team"], teams["logo"]))

forecast = forecast.merge(
    teams[["team", "group", "logo", "abbrev"]],
    on="team",
    how="left",
)

st.markdown('<div class="big-title">🌎 2026 World Cup Forecast</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Live projections powered by ESPN match data, team ratings, and Monte Carlo simulation.</div>',
    unsafe_allow_html=True,
)
st.caption(f"Last updated: {last_updated}")

total_sims = int(forecast["sims"].max())
completed_matches = int(matches["completed"].sum())
total_matches = len(matches)

c1, c2, c3 = st.columns(3)
c1.metric("Simulations", f"{total_sims:,}")
c2.metric("Completed matches", f"{completed_matches}/{total_matches}")
c3.metric("Teams", f"{forecast['team'].nunique()}")

st.divider()

st.subheader("🏆 Championship odds")

top5 = forecast.sort_values("champion_pct", ascending=False).head(5)
cols = st.columns(5)

for col, (_, row) in zip(cols, top5.iterrows()):
    with col:
        logo = row.get("logo", "")

        st.markdown(
            f"""
            <div class="metric-card">
                <img src="{logo}" width="56" height="56" style="border-radius:50%;">
                <div class="team-name">{row["team"]}</div>
                <div class="team-prob">{pct(row["champion_pct"])}</div>
                <div class="small-muted">Win World Cup</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

chart_top = top5.copy()
chart_top["Team"] = chart_top["team"]

st.bar_chart(
    chart_top.set_index("Team")["champion_pct"] * 100,
    height=320,
)

st.divider()

tab1, tab2, tab3 = st.tabs(["Tournament odds", "Groups", "Matches"])

with tab1:
    st.subheader("Full tournament forecast")

    display = forecast.sort_values("champion_pct", ascending=False).copy()

    html_rows = []

    for _, row in display.iterrows():
        html_rows.append(
            {
                "Team": team_html(row["team"], logo_map),
                "Advance": percent_bar(row["advance_pct"]),
                "Round of 16": pct(row["round_16_pct"]),
                "Quarterfinal": pct(row["quarterfinal_pct"]),
                "Semifinal": pct(row["semifinal_pct"]),
                "Final": pct(row["final_pct"]),
                "Champion": pct(row["champion_pct"]),
            }
        )

    html_df = pd.DataFrame(html_rows)

    st.markdown(
        html_df.to_html(escape=False, index=False),
        unsafe_allow_html=True,
    )

with tab2:
    st.subheader("Group forecast")

    group_options = sorted(teams["group"].dropna().unique())
    selected_group = st.selectbox("Select group", group_options)

    group_teams = teams[teams["group"] == selected_group]["team"].tolist()
    group_forecast = forecast[forecast["team"].isin(group_teams)].copy()
    group_forecast = group_forecast.sort_values("advance_pct", ascending=False)

    st.markdown(f"### Group {selected_group}")

    for _, row in group_forecast.iterrows():
        left, right = st.columns([2, 3])

        with left:
            st.markdown(
                team_html(row["team"], logo_map, size=34),
                unsafe_allow_html=True,
            )

        with right:
            st.markdown(
                percent_bar(row["advance_pct"], label=pct(row["advance_pct"])),
                unsafe_allow_html=True,
            )

    st.markdown("#### Group table")

    group_rows = []

    for _, row in group_forecast.iterrows():
        group_rows.append(
            {
                "Team": team_html(row["team"], logo_map),
                "Advance": percent_bar(row["advance_pct"]),
                "Round of 16": pct(row["round_16_pct"]),
                "Quarterfinal": pct(row["quarterfinal_pct"]),
                "Champion": pct(row["champion_pct"]),
            }
        )

    group_df = pd.DataFrame(group_rows)

    st.markdown(
        group_df.to_html(escape=False, index=False),
        unsafe_allow_html=True,
    )

with tab3:
    st.subheader("Match schedule and results")

    match_view = matches.copy()

    match_view["Home"] = match_view["home_team"].apply(lambda t: team_html(t, logo_map))
    match_view["Away"] = match_view["away_team"].apply(lambda t: team_html(t, logo_map))

    match_view["Score"] = (
        match_view["home_score"].astype(str)
        + " - "
        + match_view["away_score"].astype(str)
    )

    stage = st.selectbox(
        "Stage",
        ["All"] + sorted(match_view["season_slug"].dropna().unique()),
    )

    if stage != "All":
        match_view = match_view[match_view["season_slug"] == stage]

    match_table = match_view[
        [
            "date_utc",
            "season_slug",
            "Home",
            "Score",
            "Away",
            "status_desc",
        ]
    ].rename(
        columns={
            "date_utc": "Date UTC",
            "season_slug": "Stage",
            "status_desc": "Status",
        }
    )

    st.markdown(
        match_table.to_html(escape=False, index=False),
        unsafe_allow_html=True,
    )