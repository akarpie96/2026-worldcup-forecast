from pathlib import Path

import pandas as pd
import streamlit as st

FORECAST_PATH = Path("data/processed/tournament_forecast.csv")
MATCHES_PATH = Path("data/processed/matches.csv")
TEAMS_PATH = Path("data/processed/teams.csv")

FLAG = {
    "Argentina": "🇦🇷", "Spain": "🇪🇸", "France": "🇫🇷", "England": "🏴",
    "Germany": "🇩🇪", "Brazil": "🇧🇷", "Portugal": "🇵🇹", "Netherlands": "🇳🇱",
    "Belgium": "🇧🇪", "Morocco": "🇲🇦", "Croatia": "🇭🇷", "Mexico": "🇲🇽",
    "United States": "🇺🇸", "Uruguay": "🇺🇾", "Switzerland": "🇨🇭", "Colombia": "🇨🇴",
    "Japan": "🇯🇵", "South Korea": "🇰🇷", "Scotland": "🏴", "Sweden": "🇸🇪",
    "Senegal": "🇸🇳", "Türkiye": "🇹🇷", "Australia": "🇦🇺", "Canada": "🇨🇦",
    "Ecuador": "🇪🇨", "Iran": "🇮🇷", "Austria": "🇦🇹", "Ivory Coast": "🇨🇮",
    "Norway": "🇳🇴", "Egypt": "🇪🇬", "Ghana": "🇬🇭", "Tunisia": "🇹🇳",
    "Czechia": "🇨🇿", "Algeria": "🇩🇿", "Paraguay": "🇵🇾", "Saudi Arabia": "🇸🇦",
    "South Africa": "🇿🇦", "Qatar": "🇶🇦", "Bosnia-Herzegovina": "🇧🇦",
    "New Zealand": "🇳🇿", "Congo DR": "🇨🇩", "Uzbekistan": "🇺🇿",
    "Iraq": "🇮🇶", "Jordan": "🇯🇴", "Panama": "🇵🇦", "Haiti": "🇭🇹",
    "Cape Verde": "🇨🇻", "Curaçao": "🇨🇼",
}


def pct(x):
    return f"{x * 100:.1f}%"


def team_label(team):
    return f"{FLAG.get(team, '🏳️')} {team}"


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
        margin-bottom: 28px;
    }
    .metric-card {
        padding: 18px;
        border-radius: 18px;
        border: 1px solid rgba(128,128,128,0.25);
        background: rgba(128,128,128,0.06);
        text-align: center;
    }
    .team-name {
        font-size: 22px;
        font-weight: 700;
    }
    .team-prob {
        font-size: 34px;
        font-weight: 800;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

forecast = pd.read_csv(FORECAST_PATH)
matches = pd.read_csv(MATCHES_PATH)
teams = pd.read_csv(TEAMS_PATH)

forecast["team_display"] = forecast["team"].apply(team_label)

st.markdown('<div class="big-title">🌎 2026 World Cup Forecast</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Live projections powered by ESPN match data, team ratings, and Monte Carlo simulation.</div>',
    unsafe_allow_html=True,
)

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
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="team-name">{team_label(row["team"])}</div>
                <div class="team-prob">{pct(row["champion_pct"])}</div>
                <div>Win World Cup</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.bar_chart(
    top5.set_index("team_display")["champion_pct"] * 100,
    height=320,
)

st.divider()

tab1, tab2, tab3 = st.tabs(["Tournament odds", "Groups", "Matches"])

with tab1:
    st.subheader("Full tournament forecast")

    display = forecast.copy()
    display = display.sort_values("champion_pct", ascending=False)

    for col in [
        "advance_pct",
        "round_16_pct",
        "quarterfinal_pct",
        "semifinal_pct",
        "final_pct",
        "champion_pct",
    ]:
        display[col] = display[col].apply(pct)

    display["Team"] = display["team"].apply(team_label)

    st.dataframe(
        display[
            [
                "Team",
                "advance_pct",
                "round_16_pct",
                "quarterfinal_pct",
                "semifinal_pct",
                "final_pct",
                "champion_pct",
            ]
        ].rename(
            columns={
                "advance_pct": "Advance",
                "round_16_pct": "Round of 16",
                "quarterfinal_pct": "Quarterfinal",
                "semifinal_pct": "Semifinal",
                "final_pct": "Final",
                "champion_pct": "Champion",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

with tab2:
    st.subheader("Group forecast")

    group_options = sorted(teams["group"].dropna().unique())
    selected_group = st.selectbox("Select group", group_options)

    group_teams = teams[teams["group"] == selected_group]["team"].tolist()
    group_forecast = forecast[forecast["team"].isin(group_teams)].copy()
    group_forecast = group_forecast.sort_values("advance_pct", ascending=False)
    group_forecast["Team"] = group_forecast["team"].apply(team_label)

    chart_data = group_forecast.set_index("Team")["advance_pct"] * 100
    st.bar_chart(chart_data, height=300)

    table = group_forecast.copy()
    for col in ["advance_pct", "round_16_pct", "quarterfinal_pct", "champion_pct"]:
        table[col] = table[col].apply(pct)

    st.dataframe(
        table[
            [
                "Team",
                "advance_pct",
                "round_16_pct",
                "quarterfinal_pct",
                "champion_pct",
            ]
        ].rename(
            columns={
                "advance_pct": "Advance",
                "round_16_pct": "Round of 16",
                "quarterfinal_pct": "Quarterfinal",
                "champion_pct": "Champion",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

with tab3:
    st.subheader("Match schedule and results")

    match_view = matches.copy()
    match_view["Home"] = match_view["home_team"].apply(team_label)
    match_view["Away"] = match_view["away_team"].apply(team_label)

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

    st.dataframe(
        match_view[
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
        ),
        use_container_width=True,
        hide_index=True,
    )