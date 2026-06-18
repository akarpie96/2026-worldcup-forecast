import json
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

FORECAST_PATH = Path("data/processed/tournament_forecast.csv")
MATCHES_PATH = Path("data/processed/matches.csv")
TEAMS_PATH = Path("data/processed/teams.csv")
BRACKET_PATH = Path("data/processed/bracket_forecast.csv")
FORECAST_HISTORY_PATH = Path("data/processed/forecast_history.csv")
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
            f"<span>{team}</span>"
            f"</div>"
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
        f"</div>"
        f'<div style="min-width:48px; text-align:right; font-weight:700;">{text}</div>'
        f"</div>"
    )


def slot_stage(slot):
    stage_order = ["Round of 32", "Round of 16", "Quarterfinal", "Semifinal", "Champion"]
    for stage in stage_order:
        if str(slot).startswith(stage):
            return stage
    return "Other"


def slot_number(slot):
    nums = re.findall(r"\d+", str(slot))
    return int(nums[-1]) if nums else 999


def friendly_slot(slot):
    if slot == "Champion":
        return "Champion"

    n = slot_number(slot)

    if str(slot).startswith("Round of 32"):
        return f"R32 Match {n}"
    if str(slot).startswith("Round of 16"):
        return f"R16 Match {n}"
    if str(slot).startswith("Quarterfinal"):
        return f"Quarterfinal {n}"
    if str(slot).startswith("Semifinal"):
        return f"Semifinal {n}"

    return str(slot)


def render_bracket_slot(slot_name, slot_df, logo_map, max_teams=3):
    top = slot_df.sort_values("probability", ascending=False).head(max_teams)
    shown_probability = top["probability"].sum()
    other_probability = max(0, 1 - shown_probability)

    html = (
        '<div class="bracket-card">'
        f'<div class="bracket-slot-title">{friendly_slot(slot_name)}</div>'
    )

    for _, row in top.iterrows():
        logo = logo_map.get(row["team"], "")
        probability = pct(row["probability"])

        html += (
            '<div class="bracket-team-row">'
            '<div class="bracket-team-left">'
            f'<img src="{logo}" width="24" height="24" style="border-radius:50%;">'
            f'<span>{row["team"]}</span>'
            "</div>"
            f'<span class="bracket-prob">{probability}</span>'
            "</div>"
        )

    if other_probability > 0.005:
        html += (
            '<div class="bracket-team-row bracket-other">'
            '<div class="bracket-team-left">'
            "<span>Others</span>"
            "</div>"
            f'<span class="bracket-prob">{pct(other_probability)}</span>'
            "</div>"
        )

    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def build_movement_story(history, metric):
    story_history = history.copy()
    story_history["timestamp"] = story_history["timestamp_utc"].apply(
        lambda x: pd.to_datetime(x, utc=True)
    )

    pivot = story_history.pivot_table(
        index="team",
        columns="timestamp",
        values=metric,
        aggfunc="last",
    )

    if pivot.shape[1] < 2:
        return None

    times = sorted(pivot.columns)
    baseline = times[0]
    latest = times[-1]

    movers = pivot[[baseline, latest]].dropna().copy()
    movers["change_pts"] = (movers[latest] - movers[baseline]) * 100
    movers = movers.reset_index()

    top_gain = movers.sort_values("change_pts", ascending=False).iloc[0]
    top_drop = movers.sort_values("change_pts", ascending=True).iloc[0]

    return {
        "top_gain_team": top_gain["team"],
        "top_gain_change": top_gain["change_pts"],
        "top_drop_team": top_drop["team"],
        "top_drop_change": top_drop["change_pts"],
    }


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
    .bracket-card {
        border: 1px solid rgba(128,128,128,0.25);
        border-radius: 14px;
        padding: 12px;
        margin-bottom: 14px;
        background: rgba(128,128,128,0.055);
        min-height: 128px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    }
    .bracket-slot-title {
        font-weight: 800;
        font-size: 13px;
        margin-bottom: 8px;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.02em;
    }
    .bracket-team-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        margin-bottom: 7px;
    }
    .bracket-team-left {
        display: flex;
        align-items: center;
        gap: 8px;
        font-weight: 650;
        min-width: 0;
    }
    .bracket-prob {
        font-weight: 850;
        white-space: nowrap;
    }
    .bracket-other {
        color: #777;
        font-style: italic;
    }
    .round-spacer-small {
        height: 70px;
    }
    .round-spacer-medium {
        height: 150px;
    }
    .round-spacer-large {
        height: 330px;
    }
    .round-spacer-xl {
        height: 700px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

forecast = pd.read_csv(FORECAST_PATH)
matches = pd.read_csv(MATCHES_PATH)
teams = pd.read_csv(TEAMS_PATH)
bracket = pd.read_csv(BRACKET_PATH)

if FORECAST_HISTORY_PATH.exists():
    history = pd.read_csv(FORECAST_HISTORY_PATH)
else:
    history = pd.DataFrame()

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

if not history.empty:
    st.markdown("### Forecast storylines")

    champion_story = build_movement_story(history, "champion_pct")
    advance_story = build_movement_story(history, "advance_pct")

    story_cols = st.columns(4)

    if champion_story:
        story_cols[0].metric(
            "📈 Champion riser",
            champion_story["top_gain_team"],
            f"{champion_story['top_gain_change']:+.2f} pts",
        )
        story_cols[1].metric(
            "📉 Champion faller",
            champion_story["top_drop_team"],
            f"{champion_story['top_drop_change']:+.2f} pts",
        )

    if advance_story:
        story_cols[2].metric(
            "🔥 Advance riser",
            advance_story["top_gain_team"],
            f"{advance_story['top_gain_change']:+.2f} pts",
        )
        story_cols[3].metric(
            "⚠️ Advance faller",
            advance_story["top_drop_team"],
            f"{advance_story['top_drop_change']:+.2f} pts",
        )

chart_top = top5.copy()
chart_top["Team"] = chart_top["team"]

st.bar_chart(
    chart_top.set_index("Team")["champion_pct"] * 100,
    height=320,
)

st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Tournament odds", "Groups", "Matches", "Live Bracket", "Movement"]
)

with tab1:
    st.subheader("Full tournament forecast")

    display = forecast.sort_values("champion_pct", ascending=False).copy()

    html_rows = []

    for _, row in display.iterrows():
        html_rows.append(
            {
                "Team": team_html(row["team"], logo_map),
                "Win Group": percent_bar(row["win_group_pct"]),
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
    group_forecast = group_forecast.sort_values(
        ["win_group_pct", "advance_pct"],
        ascending=False,
    )

    st.markdown(f"### Group {selected_group}")

    for _, row in group_forecast.iterrows():
        left, right = st.columns([2, 3])

        with left:
            st.markdown(
                team_html(row["team"], logo_map, size=34),
                unsafe_allow_html=True,
            )

        with right:
            st.markdown("**Win Group**")
            st.markdown(
                percent_bar(row["win_group_pct"], label=pct(row["win_group_pct"])),
                unsafe_allow_html=True,
            )

            st.markdown("**Advance**")
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
                "Win Group": percent_bar(row["win_group_pct"]),
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

with tab4:
    st.subheader("Live Bracket Forecast")
    st.caption(
        "Projected most likely teams for each knockout-round slot based on current simulations. "
        "Each card shows the top projected teams plus an Others bucket."
    )

    bracket["stage"] = bracket["slot"].apply(slot_stage)

    stage_columns = [
        ("Round of 32", "R32", ""),
        ("Round of 16", "R16", "round-spacer-small"),
        ("Quarterfinal", "QF", "round-spacer-medium"),
        ("Semifinal", "SF", "round-spacer-large"),
        ("Champion", "Champion", "round-spacer-xl"),
    ]

    cols = st.columns([1.35, 1.25, 1.15, 1.05, 0.95])

    for col, (stage, label, spacer_class) in zip(cols, stage_columns):
        with col:
            st.markdown(f"### {label}")

            stage_df = bracket[bracket["stage"] == stage].copy()

            if stage_df.empty:
                st.info("No projections yet.")
                continue

            slots = sorted(stage_df["slot"].unique(), key=slot_number)

            for idx, slot in enumerate(slots):
                if idx > 0 and spacer_class:
                    st.markdown(f'<div class="{spacer_class}"></div>', unsafe_allow_html=True)

                slot_df = stage_df[stage_df["slot"] == slot]
                render_bracket_slot(slot, slot_df, logo_map, max_teams=3)

with tab5:
    st.subheader("Forecast Movement")
    st.caption("Historical probability movement from saved forecast snapshots.")

    if history.empty:
        st.info("No forecast history has been recorded yet.")
    else:
        history = history.copy()
        history["timestamp"] = history["timestamp_utc"].apply(
            lambda x: pd.to_datetime(x, utc=True)
        )

        history["timestamp_local"] = history["timestamp"].dt.tz_convert(
            "America/Los_Angeles"
        )

        metric_options = {
            "Win Group": "win_group_pct",
            "Advance": "advance_pct",
            "Round of 16": "round_16_pct",
            "Quarterfinal": "quarterfinal_pct",
            "Semifinal": "semifinal_pct",
            "Final": "final_pct",
            "Champion": "champion_pct",
        }

        selected_metric_label = st.selectbox(
            "Metric",
            list(metric_options.keys()),
            index=1,
        )

        selected_metric = metric_options[selected_metric_label]

        teams_available = sorted(history["team"].dropna().unique())

        default_teams = ["Argentina", "Spain", "France"]
        selected_teams = st.multiselect(
            "Teams to compare",
            teams_available,
            default=default_teams
            if all(t in teams_available for t in default_teams)
            else teams_available[:3],
        )

        if not selected_teams:
            st.info("Select at least one team.")
        else:
            chart_history = history[history["team"].isin(selected_teams)].copy()
            chart_history = chart_history.sort_values("timestamp_local")
            chart_history["value_pct"] = chart_history[selected_metric] * 100

            latest = (
                chart_history.sort_values("timestamp_local")
                .groupby("team")
                .tail(1)
                .copy()
            )

            latest = latest.sort_values("value_pct", ascending=False)

            cols = st.columns(min(3, len(latest)))

            for col, (_, row) in zip(cols, latest.iterrows()):
                col.metric(
                    row["team"],
                    f"{row['value_pct']:.1f}%",
                )

            fig = px.line(
                chart_history,
                x="timestamp_local",
                y="value_pct",
                color="team",
                markers=True,
                labels={
                    "timestamp_local": "Time",
                    "value_pct": f"{selected_metric_label} probability (%)",
                    "team": "Team",
                },
                title=f"{selected_metric_label} probability over time",
            )

            fig.update_layout(
                hovermode="x unified",
                yaxis_ticksuffix="%",
                legend_title_text="Team",
                margin=dict(l=20, r=20, t=60, b=20),
            )

            st.plotly_chart(fig, use_container_width=True)

            st.markdown("#### Recent snapshots")

            selected_team_for_table = st.selectbox(
                "Recent snapshot table team",
                selected_teams,
            )

            table_history = chart_history[
                chart_history["team"] == selected_team_for_table
            ].copy()

            table_history["Time"] = table_history["timestamp_local"].dt.strftime(
                "%b %d %I:%M %p"
            )
            table_history["Probability"] = table_history["value_pct"].map(
                lambda x: f"{x:.1f}%"
            )

            st.dataframe(
                table_history.sort_values("timestamp_local", ascending=False)[
                    ["Time", "Probability"]
                ].head(10),
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("#### Biggest movers since pre-tournament forecast")

            pivot = history.pivot_table(
                index="team",
                columns="timestamp",
                values=selected_metric,
                aggfunc="last",
            )

            if pivot.shape[1] < 2:
                st.info("Need at least two snapshots to calculate movers.")
            else:
                sorted_times = sorted(pivot.columns)

                baseline_time = sorted_times[0]
                latest_time = sorted_times[-1]

                st.caption(
                    f"Comparing {baseline_time.strftime('%b %d %Y')} "
                    f"to the latest forecast."
                )

                movers = pivot[[baseline_time, latest_time]].dropna().copy()
                movers["change_pts"] = (
                    movers[latest_time] - movers[baseline_time]
                ) * 100

                movers = movers.reset_index()

                gainers = movers.sort_values(
                    "change_pts",
                    ascending=False,
                ).head(10)

                losers = movers.sort_values(
                    "change_pts",
                    ascending=True,
                ).head(10)

                left, right = st.columns(2)

                with left:
                    st.markdown("##### Biggest gainers")

                    gainers_display = gainers.copy()
                    gainers_display["Change"] = gainers_display[
                        "change_pts"
                    ].map(lambda x: f"{x:+.2f} pts")

                    st.dataframe(
                        gainers_display[["team", "Change"]].rename(
                            columns={"team": "Team"}
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

                with right:
                    st.markdown("##### Biggest decliners")

                    losers_display = losers.copy()
                    losers_display["Change"] = losers_display[
                        "change_pts"
                    ].map(lambda x: f"{x:+.2f} pts")

                    st.dataframe(
                        losers_display[["team", "Change"]].rename(
                            columns={"team": "Team"}
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )