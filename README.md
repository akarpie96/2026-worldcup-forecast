# 2026 World Cup Forecast

A live forecasting and simulation platform for the 2026 FIFA World Cup built with Python, Monte Carlo simulation, ESPN match data, FIFA ratings, GitHub Actions, and Streamlit.

## Live App

https://2026-worldcup-forecast-easdzxu4cskft8ckvdty9x.streamlit.app/
## Features

* Live World Cup forecasts
* Group advancement probabilities
* Group winner probabilities
* Round of 32, Quarterfinal, Semifinal, Final, and Champion odds
* Knockout bracket projections
* Historical forecast tracking
* Forecast movement charts
* Biggest risers and fallers since the pre-tournament forecast
* Automated data updates via GitHub Actions

## How It Works

### Match Data

The project pulls World Cup match and standings data from ESPN and processes:

* Match schedule
* Completed results
* Group stage standings
* Knockout bracket structure

### Team Strength Ratings

Each team is assigned a strength rating using FIFA ratings.

These ratings drive the simulation engine and determine expected match outcomes.

### Monte Carlo Simulation

The forecasting model runs thousands of tournament simulations.

For each simulation:

1. Remaining matches are simulated.
2. Group standings are calculated.
3. Knockout brackets are generated.
4. The tournament is played through to a champion.

The results are aggregated into probabilities such as:

* Advance from group
* Win group
* Reach Round of 16
* Reach Quarterfinal
* Reach Semifinal
* Reach Final
* Win World Cup

### Historical Tracking

Every forecast snapshot is stored over time.

This allows users to:

* Track probability changes
* Compare teams
* View forecast movement
* Identify the biggest risers and fallers

## Tech Stack

* Python
* Pandas
* Streamlit
* Plotly
* GitHub Actions
* FIFA Ratings
* ESPN Data

## Local Development

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the full pipeline:

```bash
python run_pipeline.py
```

Launch the dashboard:

```bash
streamlit run app.py
```

## Future Roadmap

* Live in-match probability updates
* Team comparison pages
* Enhanced bracket visualization
* Match prediction pages
* Forecast explanations and model transparency
* Historical forecast archive

## Disclaimer

This project is an independent forecasting model and is not affiliated with FIFA, ESPN, or any national federation.
