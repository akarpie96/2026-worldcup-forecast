from pathlib import Path

import pandas as pd
import streamlit as st

FORECAST_PATH = Path("data/processed/tournament_forecast.csv")

st.set_page_config(
    page_title="2026 World Cup Forecast",
    page_icon="🌎",
    layout="wide",
)

st.title("🌎 2026 World Cup Forecast")
st.caption("Live-ish projections powered by ESPN match data and Monte Carlo simulation.")

forecast = pd.read_csv(FORECAST_PATH)

pct_cols = [
    "advance_pct",
    "round_16_pct",
    "quarterfinal_pct",
    "semifinal_pct",
    "final_pct",
    "champion_pct",
]

display = forecast.copy()

for col in pct_cols:
    display[col] = (display[col] * 100).round(1)

st.subheader("🏆 Championship odds")

top = display.sort_values("champion_pct", ascending=False).head(15)

st.dataframe(
    top[
        [
            "team",
            "advance_pct",
            "round_16_pct",
            "quarterfinal_pct",
            "semifinal_pct",
            "final_pct",
            "champion_pct",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

st.bar_chart(
    top.set_index("team")["champion_pct"]
)

st.subheader("📈 Full forecast table")

st.dataframe(
    display.sort_values("champion_pct", ascending=False),
    use_container_width=True,
    hide_index=True,
)