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
RATINGS_PATH = Path("data/processed/team_ratings.csv")
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
        f'<div style="width:130px; background:rgba(128,128,128,0.18); border-radius:999px; height:16px;">'
        f'<div style="width:{width:.1f}%; background:#2E86DE; height:16px; border-radius:999px;"></div>'
        f"</div>"
        f'<div style="min-width:48px; text-align:right; font-weight:700;">{text}</div>'
        f"</div>"
    )


def simple_prob_bar(value):
    width = max(0, min(100, value * 100))
    return (
        f'<div style="width:100%; background:rgba(128,128,128,0.16); border-radius:999px; height:10px; margin-top:8px;">'
        f'<div style="width:{width:.1f}%; background:#2E86DE; height:10px; border-radius:999px;"></div>'
        f"</div>"
    )


def win_prob(rating_a, rating_b):
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def match_outcome_probs(team_a, team_b, ratings_map):
    rating_a = ratings_map.get(team_a, 1500)
    rating_b = ratings_map.get(team_b, 1500)

    p_a_no_draw = win_prob(rating_a, rating_b)

    gap = abs(rating_a - rating_b)
    p_draw = max(0.16, 0.30 - gap / 2000)

    remaining = 1 - p_draw

    p_a_win = remaining * p_a_no_draw
    p_b_win = remaining * (1 - p_a_no_draw)

    return p_a_win, p_draw, p_b_win


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
ratings_df = pd.read_csv(RATINGS_PATH)
ratings_map = dict(zip(ratings_df["team"], ratings_df["rating"]))

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

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["Tournament odds", "Groups", "Matches", "Live Bracket", "Movement", "Match Forecasts"]
)

# NOTE:
# Tabs 1-5 stay exactly as you already have them.
# Only tab6 was changed for detailed Match Stakes.

with tab6:
    st.subheader("Upcoming Match Forecasts")
    st.caption(
        "Win/draw/loss forecasts for upcoming concrete World Cup matchups using team ratings."
    )

    upcoming = matches[matches["completed"] == False].copy()

    placeholder_pattern = "Winner|Loser|Group|Place|Semifinal|Quarterfinal|Round of 16|Round of 32"

    upcoming = upcoming[
        ~upcoming["home_team"].astype(str).str.contains(placeholder_pattern, na=False)
    ]
    upcoming = upcoming[
        ~upcoming["away_team"].astype(str).str.contains(placeholder_pattern, na=False)
    ]

    upcoming["date_parsed"] = pd.to_datetime(upcoming["date_utc"], utc=True)
    upcoming = upcoming.sort_values("date_parsed").head(12)

    if upcoming.empty:
        st.info("No upcoming concrete matchups are available yet.")
    else:
        for _, row in upcoming.iterrows():
            home = row["home_team"]
            away = row["away_team"]

            p_home, p_draw, p_away = match_outcome_probs(home, away, ratings_map)

            date_local = row["date_parsed"].tz_convert("America/Los_Angeles")
            date_label = date_local.strftime("%b %d, %I:%M %p PT")
            stage_label = str(row.get("season_slug", "")).replace("-", " ").title()

            home_logo = logo_map.get(home, "")
            away_logo = logo_map.get(away, "")

            home_rating = ratings_map.get(home, 1500)
            away_rating = ratings_map.get(away, 1500)
            rating_edge = home_rating - away_rating

            home_champ_val = forecast.loc[forecast["team"] == home, "champion_pct"]
            away_champ_val = forecast.loc[forecast["team"] == away, "champion_pct"]

            home_advance_val = forecast.loc[forecast["team"] == home, "advance_pct"]
            away_advance_val = forecast.loc[forecast["team"] == away, "advance_pct"]

            home_round16_val = forecast.loc[forecast["team"] == home, "round_16_pct"]
            away_round16_val = forecast.loc[forecast["team"] == away, "round_16_pct"]

            home_champ_val = home_champ_val.iloc[0] if not home_champ_val.empty else 0
            away_champ_val = away_champ_val.iloc[0] if not away_champ_val.empty else 0

            home_advance_val = home_advance_val.iloc[0] if not home_advance_val.empty else 0
            away_advance_val = away_advance_val.iloc[0] if not away_advance_val.empty else 0

            home_round16_val = home_round16_val.iloc[0] if not home_round16_val.empty else 0
            away_round16_val = away_round16_val.iloc[0] if not away_round16_val.empty else 0

            favorite = home if p_home > p_away else away
            favorite_prob = max(p_home, p_away)

            combined_title = home_champ_val + away_champ_val
            combined_advance = home_advance_val + away_advance_val
            combined_r16 = home_round16_val + away_round16_val
            underdog_prob = min(p_home, p_away)

            stakes_score = (
                combined_title * 1.8
                + combined_advance * 0.25
                + combined_r16 * 0.35
                + underdog_prob * 0.25
            )

            if stakes_score >= 0.65:
                stakes_label = "Very High"
            elif stakes_score >= 0.45:
                stakes_label = "High"
            elif stakes_score >= 0.25:
                stakes_label = "Medium"
            else:
                stakes_label = "Low"

            stakes_detail = (
                f"Title stakes: {pct(combined_title)} combined · "
                f"Advance stakes: {pct(combined_advance)} combined · "
                f"R16 stakes: {pct(combined_r16)} combined"
            )

            home_bar = simple_prob_bar(p_home)
            draw_bar = simple_prob_bar(p_draw)
            away_bar = simple_prob_bar(p_away)

            edge_text = (
                f"{home} +{rating_edge:,.0f}"
                if rating_edge > 0
                else f"{away} +{abs(rating_edge):,.0f}"
                if rating_edge < 0
                else "Even"
            )

            card_html = (
                '<div style="border:1px solid rgba(128,128,128,0.22); border-radius:22px; '
                'padding:22px; margin:0 0 22px 0; background:linear-gradient(180deg, '
                'rgba(128,128,128,0.07), rgba(128,128,128,0.025)); '
                'box-shadow:0 2px 8px rgba(0,0,0,0.04);">'
                '<div style="display:flex; align-items:center; justify-content:space-between; '
                'margin-bottom:16px; color:#777; font-size:14px; font-weight:600;">'
                f'<span>{date_label}</span><span>{stage_label}</span></div>'
                '<div style="display:grid; grid-template-columns:1fr auto 1fr; '
                'align-items:center; gap:22px; margin-bottom:20px;">'
                '<div style="display:flex; align-items:center; gap:14px;">'
                f'<img src="{home_logo}" width="46" height="46" style="border-radius:50%;">'
                '<div>'
                f'<div style="font-size:25px; font-weight:850;">{home}</div>'
                f'<div style="color:#777; font-size:13px;">Rating {home_rating:,.0f}</div>'
                '</div></div>'
                '<div style="font-weight:900; color:#888; border:1px solid rgba(128,128,128,0.25); '
                'border-radius:999px; padding:8px 13px; background:rgba(128,128,128,0.06);">VS</div>'
                '<div style="display:flex; align-items:center; justify-content:flex-end; gap:14px;">'
                '<div style="text-align:right;">'
                f'<div style="font-size:25px; font-weight:850;">{away}</div>'
                f'<div style="color:#777; font-size:13px;">Rating {away_rating:,.0f}</div>'
                '</div>'
                f'<img src="{away_logo}" width="46" height="46" style="border-radius:50%;">'
                '</div></div>'
                '<div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; margin-bottom:18px;">'
                '<div style="border-radius:16px; padding:14px; background:rgba(46,134,222,0.10); text-align:center;">'
                f'<div style="font-size:13px; color:#666; font-weight:700;">{home} win</div>'
                f'<div style="font-size:30px; font-weight:900;">{pct(p_home)}</div>{home_bar}'
                '</div>'
                '<div style="border-radius:16px; padding:14px; background:rgba(128,128,128,0.10); text-align:center;">'
                '<div style="font-size:13px; color:#666; font-weight:700;">Draw</div>'
                f'<div style="font-size:30px; font-weight:900;">{pct(p_draw)}</div>{draw_bar}'
                '</div>'
                '<div style="border-radius:16px; padding:14px; background:rgba(46,134,222,0.10); text-align:center;">'
                f'<div style="font-size:13px; color:#666; font-weight:700;">{away} win</div>'
                f'<div style="font-size:30px; font-weight:900;">{pct(p_away)}</div>{away_bar}'
                '</div></div>'
                '<div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; margin-bottom:14px;">'
                '<div style="border-radius:14px; padding:12px; background:rgba(128,128,128,0.07);">'
                '<div style="font-size:12px; color:#777; font-weight:800;">Favorite</div>'
                f'<div style="font-size:18px; font-weight:850;">{favorite}</div>'
                f'<div style="font-size:13px; color:#777;">{pct(favorite_prob)} win probability</div>'
                '</div>'
                '<div style="border-radius:14px; padding:12px; background:rgba(128,128,128,0.07);">'
                '<div style="font-size:12px; color:#777; font-weight:800;">Rating edge</div>'
                f'<div style="font-size:18px; font-weight:850;">{edge_text}</div>'
                '<div style="font-size:13px; color:#777;">Model strength difference</div>'
                '</div>'
                '<div style="border-radius:14px; padding:12px; background:rgba(128,128,128,0.07);">'
                '<div style="font-size:12px; color:#777; font-weight:800;">Match stakes</div>'
                f'<div style="font-size:18px; font-weight:850;">{stakes_label}</div>'
                f'<div style="font-size:13px; color:#777;">{stakes_detail}</div>'
                '</div></div>'
                '<div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; color:#555; font-size:14px;">'
                '<div style="border-top:1px solid rgba(128,128,128,0.18); padding-top:10px;">'
                f'<b>{home}</b><br>Title: {pct(home_champ_val)} · Advance: {pct(home_advance_val)} · R16: {pct(home_round16_val)}'
                '</div>'
                '<div style="border-top:1px solid rgba(128,128,128,0.18); padding-top:10px;">'
                f'<b>{away}</b><br>Title: {pct(away_champ_val)} · Advance: {pct(away_advance_val)} · R16: {pct(away_round16_val)}'
                '</div></div>'
                '</div>'
            )

            st.markdown(card_html, unsafe_allow_html=True)