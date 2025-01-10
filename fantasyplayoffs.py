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
