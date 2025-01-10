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
    round_: get_scores_for_round("post", 2023, i + 1, df_teams.values.flatten())
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

# Tab Layout
tab1, tab2, tab3, tab4 = st.tabs(["Round Scores", "Player Leaderboard", "Team Details", "Current Game"])

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

# Tab 2: Player Leaderboard
with tab2:
    st.subheader("Player Leaderboard")

    # Get a list of all unique players across all teams
    all_players = []
    for team in team_scores:
        all_players.extend([player["Player"] for player in team["Players"]])
    unique_players = list(set(all_players))

    # Create a leaderboard with scores by round and total
    player_leaderboard = []
    for player in unique_players:
        player_scores = {
            "Player": player,
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
    leaderboard_df = leaderboard_df.set_index("Player")
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

# Tab 4: Current NFL Game
with tab4:
    st.subheader("Current NFL Game Focus")

    # Dropdown inputs for NFL teams and round
    col1, col2 = st.columns(2)
    with col1:
        selected_team1 = st.selectbox("Select the first NFL team:", sorted(df_name_mapping["Team"].unique()))
    with col2:
        selected_team2 = st.selectbox("Select the second NFL team:", sorted(df_name_mapping["Team"].unique()))

    selected_round = st.selectbox("Select the current round:", rounds, index=0)

    # Filter data for the selected teams and round
    if selected_team1 and selected_team2:
        current_game_data = []
        for team in team_scores:
            team_name = team["Team"]
            players = team["Players"]

            # Find the player from each NFL team for the current fantasy team
            team1_player = next(
                (p for p in players if p["Player"] in df_name_mapping[df_name_mapping["Team"] == selected_team1]["Name"].values),
                None
            )
            team2_player = next(
                (p for p in players if p["Player"] in df_name_mapping[df_name_mapping["Team"] == selected_team2]["Name"].values),
                None
            )

            # Calculate current game score
            curr_game_score = 0
            if team1_player:
                curr_game_score += (scores_by_round[selected_round].get(team1_player["Player"], 0) or 0) * MULTIPLIERS[selected_round]
            if team2_player:
                curr_game_score += (scores_by_round[selected_round].get(team2_player["Player"], 0) or 0) * MULTIPLIERS[selected_round]

            # Add data to the table
            current_game_data.append({
                "Total": team["Total Score"],
                "Name": team_name,
                "CurrGame": curr_game_score,
                selected_team1: team1_player["Player"] if team1_player else "None",
                selected_team2: team2_player["Player"] if team2_player else "None",
            })

        # Create and display the dataframe
        current_game_df = pd.DataFrame(current_game_data)
        # Sort by Total in descending order
        current_game_df = current_game_df.sort_values(by="Total", ascending=False)
        # Set Total as the index
        current_game_df = current_game_df.set_index("Total")
        st.dataframe(current_game_df)
