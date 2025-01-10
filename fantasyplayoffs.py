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

# Calculate scores for each team, including player-specific round scores
team_scores = []
round_scores = []
for col in df_teams.columns:
    team_players = df_teams[col].dropna().tolist()
    team_total = 0
    player_scores = []
    round_totals = {round_: 0 for round_ in rounds}

    for player in team_players:
        player_total = 0
        player_round_scores = {}
        for round_ in rounds:
            score = (scores_by_round[round_].get(player, 0) or 0) * MULTIPLIERS[round_]
            player_round_scores[round_] = score
            player_total += score
            round_totals[round_] += score

        player_scores.append({"Player": player, **player_round_scores, "Total Score": player_total})
        team_total += player_total

    team_scores.append({"Team": col, "Total Score": round(team_total, 2), "Players": player_scores})
    round_scores.append({"Team": col, **round_totals, "Total": round(team_total, 2)})

# Sort teams by total score
team_scores = sorted(team_scores, key=lambda x: x["Total Score"], reverse=True)
round_scores = sorted(round_scores, key=lambda x: x["Total"], reverse=True)

# Streamlit App
st.title("Fantasy Football Playoff League")

# Create tabs
tab1, tab2 = st.tabs(["Team Player Scores", "Scores by Round"])

# Adjusted position sort order
POSITION_SORT_ORDER = ["QB", "RB", "WR", "TE", "FLEX", "DEF", "K"]

# Function to fetch player positions
def get_player_position(player_name):
    player_id = player_names.get(player_name)
    
    # Handle multiple "Lamar Jackson" issue
    if player_name == "Lamar Jackson":
        for pid, details in players.items():
            if details.get("full_name") == "Lamar Jackson" and details.get("position") == "QB":
                return "QB"

    # Handle general case
    if player_id and player_id in players:
        position = players[player_id].get("position", "Unknown")
        
        # Assign "DEF" for defense teams (2-3 letter names)
        if len(player_name) in [2, 3] and player_name.isupper():
            return "DEF"
        return position
    
    return "Unknown"

# Tab 1: Team Player Scores
with tab1:
    st.subheader("Team Player Scores")
    for team in team_scores:
        st.subheader(f"Team: {team['Team']} (Total Score: {team['Total Score']:.2f})")

        # Add position column and fetch player positions
        player_df = pd.DataFrame(team["Players"])
        player_df["Position"] = player_df["Player"].apply(get_player_position)

        # Sort by position using the predefined sort order
        player_df["Position_Rank"] = player_df["Position"].apply(
            lambda x: POSITION_SORT_ORDER.index(x) if x in POSITION_SORT_ORDER else len(POSITION_SORT_ORDER)
        )
        player_df = player_df.sort_values(by="Position_Rank").drop(columns=["Position_Rank"])

        # Set the index to "Position"
        player_df = player_df.set_index("Position")

        # Display the sorted dataframe
        st.dataframe(player_df)

# Tab 2: Scores by Round
with tab2:
    st.subheader("Scores by Round")
    round_scores_df = pd.DataFrame(round_scores).set_index("Team")
    st.dataframe(round_scores_df)
