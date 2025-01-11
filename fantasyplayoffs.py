import streamlit as st
import pandas as pd
from sleeper_wrapper import Stats, Players

# Load team and name mapping data
file_path_teams = "Book3.csv"
file_path_name_mapping = "Book4.csv"
df_teams = pd.read_csv(file_path_teams)
df_name_mapping = pd.read_csv(file_path_name_mapping)

# Preprocess data: Map names using name mapping
name_mapping = dict(zip(df_name_mapping["Form Name"], df_name_mapping["Name"]))
df_teams = df_teams.applymap(lambda x: name_mapping.get(x, x))

# Fetch player data from Sleeper API
players_api = Players().get_all_players()
keys = [*players_api]

# Prepare player mapping and handle defenses
allnames = []
allpos = []
player_ids = []

for x in range(len(keys)):
    try:
        plrid = keys[x]
        player = players_api[plrid]['full_name']
        pos = players_api[plrid]['position']
        allnames.append(player)
        allpos.append(pos)
        player_ids.append(plrid)
    except KeyError:
        # Handle defenses
        plrid = keys[x]
        player = players_api[plrid]['team']
        pos = "DEF"
        allnames.append(player)
        allpos.append(pos)
        player_ids.append(plrid)

# Find Lamar Jackson (QB) and exclude non-QB version
lamar_index = None
for idx, (name, pos) in enumerate(zip(allnames, allpos)):
    if name == "Lamar Jackson" and pos == "QB":
        lamar_index = idx
        break

if lamar_index is not None:
    allnames.pop(lamar_index)
    keys.pop(lamar_index)
    allpos.pop(lamar_index)
    player_ids.pop(lamar_index)

# Create mappings for player positions and IDs
player_positions = {name: pos for name, pos in zip(allnames, allpos)}
player_ids_map = {name: pid for name, pid in zip(allnames, player_ids)}

# Define scoring multipliers and initialize Stats
MULTIPLIERS = {"Wildcard": 1, "Divisional": 1, "Conf_Champ": 1.5, "Super_Bowl": 2}
stats = Stats()

# Function to fetch player position
def get_player_position(player_name):
    # Handle specific case for Lamar Jackson
    if player_name == "Lamar Jackson":
        return "QB"

    # Default case: fetch position from mapping
    return player_positions.get(player_name, "Unknown")

# Function to fetch scores for a specific round
def get_scores_for_round(season_type, year, week, player_list):
    week_stats = stats.get_week_stats(season_type, year, week)
    scores = {}
    for player in player_list:
        player_id = player_ids_map.get(player, None)

        # Ensure correct Lamar Jackson (QB) is selected
        if player == "Lamar Jackson":
            for pid, details in players_api.items():
                if details.get("full_name") == "Lamar Jackson" and details.get("position") == "QB":
                    player_id = pid
                    break

        if player_id:
            player_score = stats.get_player_week_score(week_stats, player_id)
            scores[player] = player_score['pts_ppr'] if player_score and 'pts_ppr' in player_score else 0
    return scores

# Fetch scores for all rounds
rounds = ["Wildcard", "Divisional", "Conf_Champ", "Super_Bowl"]
scores_by_round = {
    round_: get_scores_for_round("regular", 2024, i + 1 + 8, df_teams.values.flatten())
    for i, round_ in enumerate(rounds)
}

# Calculate total scores for each team
team_scores = []
for col in df_teams.columns:
    team_players = df_teams[col].dropna().tolist()
    team_total = 0
    player_scores = []
    for player in team_players:
        player_round_scores = {}
        for round_ in rounds:
            # Safely handle None values
            round_score = (scores_by_round[round_].get(player, 0) or 0) * MULTIPLIERS[round_]
            player_round_scores[round_] = round_score
        player_total = sum(player_round_scores.values())
        player_scores.append({"Player": player, **player_round_scores, "Total": player_total})
        team_total += player_total
    team_scores.append({"Team": col, "Total Score": team_total, "Players": player_scores})

# Sorting order for positions
POSITION_SORT_ORDER = ["QB", "RB", "WR", "TE", "Flex", "DEF", "K"]

# Streamlit App
st.title("Fantasy Football Playoff League")

# Define the 14 NFL Playoff Teams
nfl_teams = [
    "SF", "KC", "PHI", "BUF", "CIN", "DAL", "JAX", "NYG", "LAC",
    "BAL", "MIN", "TB", "SEA", "MIA"
]

# Add a new tab for Scoring Settings
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Standings", "Player Scores", "Team Details", "Current Game", "Scoring Settings", "Player Selections"])

# Tab 1: Round Scores
with tab1:
    st.subheader("Team Round Scores")
    round_scores = []
    for team in team_scores:
        team_data = {
            "Team": team["Team"],
            **{
                round_: sum(player[round_] for player in team["Players"])
                for round_ in rounds
            },
            "Total": team["Total Score"]
        }
        round_scores.append(team_data)

    # Create and display round scores dataframe
    round_scores_df = pd.DataFrame(round_scores)
    round_scores_df = round_scores_df.set_index("Team")
    round_scores_df = round_scores_df.sort_values(by="Total", ascending=False)
    st.dataframe(round_scores_df)

# Tab 2: Player Scores
with tab2:
    st.subheader("Player Scores")

    # Get a list of all unique players across all teams
    all_players = []
    for team in team_scores:
        all_players.extend([player["Player"] for player in team["Players"]])
    unique_players = list(set(all_players))

    # Create a leaderboard with scores by round, total, and team
    player_leaderboard = []
    for player in unique_players:
        player_scores = {
            "Player": player,
            "Team": df_name_mapping[df_name_mapping["Name"] == player]["Team"].iloc[0]
            if player in df_name_mapping["Name"].values else "Unknown",
            **{
                round_: (scores_by_round[round_].get(player, 0) or 0) * MULTIPLIERS[round_]
                for round_ in rounds
            }
        }
        player_scores["Total"] = sum(player_scores[round_] for round_ in rounds)
        player_leaderboard.append(player_scores)

    # Create and display player leaderboard dataframe
    leaderboard_df = pd.DataFrame(player_leaderboard)
    leaderboard_df = leaderboard_df.sort_values(by="Total", ascending=False)
    leaderboard_df = leaderboard_df[["Player", "Team", "Wildcard", "Divisional", "Conf_Champ", "Super_Bowl", "Total"]]
    leaderboard_df = leaderboard_df.set_index("Player")  # Set Player as the index
    st.dataframe(leaderboard_df)

# Tab 3: Team Details
with tab3:
    st.subheader("Team Player Scores")

    # Sort teams by total score in descending order
    sorted_teams = sorted(team_scores, key=lambda x: x["Total Score"], reverse=True)

    # Display each team's table in its own row
    for team in sorted_teams:
        st.subheader(f"Team: {team['Team']} (Total Score: {team['Total Score']:.2f})")

        # Add position column and fetch player positions
        player_df = pd.DataFrame(team["Players"])
        player_df["Position"] = player_df["Player"].apply(get_player_position)

        # Sort by position and set index
        player_df["Position_Rank"] = player_df["Position"].apply(
            lambda x: POSITION_SORT_ORDER.index(x) if x in POSITION_SORT_ORDER else len(POSITION_SORT_ORDER)
        )
        player_df = player_df.sort_values(by=["Position_Rank", "Player"]).drop(columns=["Position_Rank"])
        player_df = player_df.set_index("Position")

        # Display the sorted dataframe
        st.dataframe(player_df)

# Tab 4: Current Game
with tab4:
    st.subheader("Current NFL Game Focus")

    # Default values for the dropdowns
    default_team1 = "Texans"  # Default first NFL team
    default_team2 = "Chargers"  # Default second NFL team
    default_round = "Wildcard"  # Default round

    # Inputs for the current game
    col1, col2 = st.columns(2)
    with col1:
        selected_team1 = st.selectbox(
            "Select the first NFL team:", nfl_teams, index=nfl_teams.index(default_team1)
        )
    with col2:
        selected_team2 = st.selectbox(
            "Select the second NFL team:", nfl_teams, index=nfl_teams.index(default_team2)
        )

    selected_round = st.selectbox(
        "Select the current round:", rounds, index=rounds.index(default_round)
    )

    # Filter data for the selected teams and round
    if selected_team1 and selected_team2:
        current_game_data = []
        for team in team_scores:
            team_name = team["Team"]
            players = team["Players"]

            # Find the player from each NFL team for the current fantasy team
            team1_player = next(
                (p for p in players if p["Player"] in player_team_map and player_team_map[p["Player"]] == selected_team1), None
            )
            team2_player = next(
                (p for p in players if p["Player"] in player_team_map and player_team_map[p["Player"]] == selected_team2), None
            )

            # Calculate current game score
            curr_game_score = 0
            if team1_player:
                curr_game_score += (scores_by_round[selected_round].get(team1_player["Player"], 0) or 0) * MULTIPLIERS[selected_round]
            if team2_player:
                curr_game_score += (scores_by_round[selected_round].get(team2_player["Player"], 0) or 0) * MULTIPLIERS[selected_round]

            # Add data to the table
            current_game_data.append({
                "Name": team_name,
                "CurrGame": curr_game_score,
                "Total": team["Total Score"],
                selected_team1: team1_player["Player"] if team1_player else "None",
                selected_team2: team2_player["Player"] if team2_player else "None",
            })

        # Create and display the dataframe
        current_game_df = pd.DataFrame(current_game_data)
        current_game_df = current_game_df.set_index("Total").sort_index(ascending=False)
        st.dataframe(current_game_df)

# Default scoring settings for Sleeper
offense_scoring = {
    "Passing Yards": "0.04 per yard (1 point per 25 yards)",
    "Passing Touchdowns": "4 points",
    "Interceptions Thrown": "-1 point",
    "Rushing Yards": "0.1 per yard (1 point per 10 yards)",
    "Rushing Touchdowns": "6 points",
    "Receiving Yards": "0.1 per yard (1 point per 10 yards)",
    "Receiving Touchdowns": "6 points",
    "Receptions (PPR)": "1 point",
    "Fumbles Lost": "-2 points",
    "2-Point Conversions": "2 points"
}

kicking_scoring = {
    "Field Goal 0-39 Yards": "3 points",
    "Field Goal 40-49 Yards": "4 points",
    "Field Goal 50+ Yards": "5 points",
    "Extra Point (PAT)": "1 point"
}

defense_scoring = {
    "Sacks": "1 point",
    "Interceptions": "2 points",
    "Fumble Recoveries": "2 points",
    "Defensive Touchdowns": "6 points",
    "Safety": "2 points",
    "Blocked Kicks": "2 points",
    "Points Allowed (0)": "10 points",
    "Points Allowed (1-6)": "7 points",
    "Points Allowed (7-13)": "4 points",
    "Points Allowed (14-20)": "1 point",
    "Points Allowed (21-27)": "0 points",
    "Points Allowed (28-34)": "-1 point",
    "Points Allowed (35+)": "-4 points"
}

# Tab 5: Scoring Settings
with tab5:
    st.subheader("Scoring Settings")

    # Offense Scoring Table
    st.markdown("### Offense Scoring")
    offense_df = pd.DataFrame(list(offense_scoring.items()), columns=["Action", "Points"]).set_index("Action")
    st.table(offense_df)

    # Kicking Scoring Table
    st.markdown("### Kicking Scoring")
    kicking_df = pd.DataFrame(list(kicking_scoring.items()), columns=["Action", "Points"]).set_index("Action")
    st.table(kicking_df)

    # Defense/Special Teams Scoring Table
    st.markdown("### Defense/Special Teams Scoring")
    defense_df = pd.DataFrame(list(defense_scoring.items()), columns=["Action", "Points"]).set_index("Action")
    st.table(defense_df)

# Tab 6: Player Selections
with tab6:
    st.subheader("Player Selections")

    # Count how many teams selected each player and track selecting team
    player_selection_counts = []
    player_selected_by = {}  # Dictionary to track which team selected the player

    for player in unique_players:
        count = 0
        selected_by = []
        for team in team_scores:
            for p in team["Players"]:
                if player == p["Player"]:
                    count += 1
                    selected_by.append(team["Team"])
        player_selection_counts.append({
            "Player": player,
            "Selections": count,
            "NFL Team": df_name_mapping[df_name_mapping["Name"] == player]["Team"].iloc[0]
            if player in df_name_mapping["Name"].values else "Unknown"
        })
        if count == 1:  # Track the team if the player is selected only once
            player_selected_by[player] = selected_by[0] if selected_by else "Unknown"

    # Create a DataFrame and sort by selections
    selections_df = pd.DataFrame(player_selection_counts)
    selections_df = selections_df.sort_values(by="Selections", ascending=False)

    # Most Selected Players (Top 10)
    st.markdown("### Most Selected Players")
    most_selected_df = selections_df.head(10)[["Player", "NFL Team", "Selections"]].set_index("Player")
    st.dataframe(most_selected_df)

    # Least Selected Players (All with 1 Selection)
    st.markdown("### Least Selected Players (Selected Once)")
    least_selected_df = selections_df[selections_df["Selections"] == 1]
    least_selected_df["Selected By"] = least_selected_df["Player"].map(player_selected_by)
    least_selected_df = least_selected_df[["Player", "NFL Team", "Selected By"]].set_index("Player")
    st.dataframe(least_selected_df)
