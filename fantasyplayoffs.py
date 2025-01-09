import streamlit as st
import pandas as pd
from sleeper_wrapper import Stats, Players

# Load data from uploaded files
df_teams = pd.read_csv("Book3.csv")
df_name_mapping = pd.read_csv("Book4.csv")

# Preprocess data
players = Players().get_all_players()
player_keys = [*players]
player_names = {player['full_name']: player['player_id'] for player in players.values() if 'full_name' in player}

# Define scoring multipliers
MULTIPLIERS = {"Wildcard": 1, "Divisional": 1, "Conf_Champ": 1.5, "Super_Bowl": 2}

# Initialize stats fetcher
stats = Stats()

# Function to fetch scores for a specific round
def get_scores_for_round(season_type, year, week, player_list):
    week_stats = stats.get_week_stats(season_type, year, week)
    scores = {}
    for player in player_list:
        player_id = player_names.get(player, None)
        if player_id:
            player_score = stats.get_player_week_score(week_stats, player_id)
            scores[player] = player_score['pts_ppr'] if player_score and 'pts_ppr' in player_score else 0
    return scores

# Fetch scores for all rounds
rounds = ["Wildcard", "Divisional", "Conf_Champ", "Super_Bowl"]
scores_by_round = {round_: get_scores_for_round("post", 2023, i + 1, df_teams.values.flatten()) for i, round_ in enumerate(rounds)}

# Calculate total scores for each team and scores per round
team_scores = []
round_scores = []
for col in df_teams.columns:
    team_players = df_teams[col].dropna().tolist()
    team_total = 0
    player_scores = []
    round_totals = {round_: 0 for round_ in rounds}

    for player in team_players:
        player_total = sum((scores_by_round[round_].get(player, 0) or 0) * MULTIPLIERS[round_] for round_ in rounds)
        player_scores.append({"Player": player, "Score": player_total})
        team_total += player_total

        # Calculate round-specific scores
        for round_ in rounds:
            round_totals[round_] += (scores_by_round[round_].get(player, 0) or 0) * MULTIPLIERS[round_]

    team_scores.append({"Team": col, "Total Score": team_total, "Players": player_scores})
    round_scores.append({"Team": col, **round_totals, "Total": team_total})

# Streamlit App
st.title("Fantasy Football Playoff League")

# Create tabs
tab1, tab2 = st.tabs(["Team Rosters & Scores", "Scores by Round"])

# Tab 1: Team Rosters & Scores
with tab1:
    for team in team_scores:
        st.subheader(f"Team: {team['Team']} (Total Score: {team['Total Score']})")
        player_df = pd.DataFrame(team["Players"])
        st.dataframe(player_df.sort_values(by="Score", ascending=False))

# Tab 2: Scores by Round
with tab2:
    st.subheader("Scores by Round")
    round_scores_df = pd.DataFrame(round_scores)
    st.dataframe(round_scores_df)
