import streamlit as st
import pandas as pd
from sleeper_wrapper import Stats, Players
import time
import plotly.express as px

# Auto-refresh settings
enable_auto_refresh = False
refresh_interval_seconds = 30

if enable_auto_refresh:
    st.experimental_set_query_params(refresh=str(time.time()))
    time.sleep(refresh_interval_seconds)
    st.experimental_rerun()

# Load data
file_path_teams = "Book3.csv"
file_path_name_mapping = "Book4.csv"

df_teams = pd.read_csv(file_path_teams)
df_name_mapping = pd.read_csv(file_path_name_mapping)

# Name mapping
name_mapping = dict(zip(df_name_mapping["Form Name"], df_name_mapping["Name"]))
df_teams.loc[:, :] = df_teams.applymap(lambda x: name_mapping.get(x, x))

# ── Sleeper players ──────────────────────────────────────────────────────────
players_api = Players().get_all_players()
keys = [*players_api]

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
        # Defenses
        plrid = keys[x]
        player = players_api[plrid]['team']
        pos = "DEF"
        allnames.append(player)
        allpos.append(pos)
        player_ids.append(plrid)

# Remove duplicate Lamar Jackson (keep only QB)
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

player_positions = {name: pos for name, pos in zip(allnames, allpos)}
player_ids_map = {name: pid for name, pid in zip(allnames, player_ids)}

# Scoring setup
MULTIPLIERS = {"Wildcard": 1, "Divisional": 1, "Conf_Champ": 1.5, "Super_Bowl": 2}
stats = Stats()
rounds = ["Wildcard", "Divisional", "Conf_Champ", "Super_Bowl"]

def get_player_position(player_name):
    if player_name == "Lamar Jackson":
        return "QB"
    return player_positions.get(player_name, "Unknown")

def get_scores_for_round(season_type, year, week, player_list):
    week_stats = stats.get_week_stats(season_type, year, week)
    scores = {}
    for player in player_list:
        player_id = player_ids_map.get(player, None)
        if player == "Lamar Jackson":
            for pid, details in players_api.items():
                if details.get("full_name") == "Lamar Jackson" and details.get("position") == "QB":
                    player_id = pid
                    break
        if player_id:
            player_score = stats.get_player_week_score(week_stats, player_id)
            scores[player] = player_score['pts_ppr'] if player_score and 'pts_ppr' in player_score else 0
    return scores

# Get all scores
scores_by_round = {
    round_: get_scores_for_round("post", 2025, i + 1, df_teams.values.flatten())
    for i, round_ in enumerate(rounds)
}

# Calculate team scores
team_scores = []
for col in df_teams.columns:
    team_players = df_teams[col].dropna().tolist()
    team_total = 0
    player_scores = []
    for player in team_players:
        player_round_scores = {}
        for round_ in rounds:
            round_score = (scores_by_round[round_].get(player, 0) or 0) * MULTIPLIERS[round_]
            player_round_scores[round_] = round_score
        player_total = sum(player_round_scores.values())
        player_scores.append({"Player": player, **player_round_scores, "Total": player_total})
        team_total += player_total
    team_scores.append({"Team": col, "Total Score": team_total, "Players": player_scores})

# Position sort order
POSITION_SORT_ORDER = ["QB", "RB", "WR", "TE", "Flex", "DEF", "K"]

# ── App ──────────────────────────────────────────────────────────────────────
st.title("2026 Fantasy Playoff Challenge")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Standings", "Player Scores", "Team Details",
    "Current Game", "Scoring Settings", "Player Selections"
])

def get_rank_suffix(rank):
    if 10 <= rank % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(rank % 10, "th")

# ── Tab 1: Standings ─────────────────────────────────────────────────────────
with tab1:
    st.subheader("Standings")
    
    round_scores = []
    for team in team_scores:
        team_data = {
            "Team": team["Team"],
            **{round_: sum(player[round_] for player in team["Players"])
               for round_ in rounds},
            "Total": team["Total Score"]
        }
        round_scores.append(team_data)

    round_scores_df = pd.DataFrame(round_scores)
    round_scores_df = round_scores_df.sort_values(by="Total", ascending=False).reset_index(drop=True)

    # ── CORRECTED RANKING: Competition style (1224) ──────────────────────────
    ranks = []
    current_rank = 1
    previous_total = None

    for idx, total in enumerate(round_scores_df["Total"]):
        if idx == 0 or total < previous_total:  # New lower score → advance rank
            current_rank = idx + 1  # Rank = position (1-based) at start of group
        ranks.append(f"{current_rank}{get_rank_suffix(current_rank)}")
        previous_total = total

    round_scores_df.insert(0, "Place", ranks)

    # Points behind leader
    first_place_total = round_scores_df["Total"].iloc[0]
    round_scores_df["Points Behind"] = first_place_total - round_scores_df["Total"]

    # Final display
    round_scores_df = round_scores_df.set_index("Place")
    st.dataframe(round_scores_df.style.format({col: "{:.1f}" for col in rounds + ["Total", "Points Behind"]}))

# ── Tab 2: Player Scores ─────────────────────────────────────────────────────
with tab2:
    st.subheader("Player Scores")
    all_players = [p["Player"] for t in team_scores for p in t["Players"]]
    unique_players = list(set(all_players))

    leaderboard = []
    for p in unique_players:
        score_dict = {
            "Player": p,
            "Team": df_name_mapping[df_name_mapping["Name"] == p]["Team"].iloc[0]
            if p in df_name_mapping["Name"].values else "Unknown",
            **{r: (scores_by_round[r].get(p, 0) or 0) * MULTIPLIERS[r] for r in rounds}
        }
        score_dict["Total"] = sum(score_dict[r] for r in rounds)
        leaderboard.append(score_dict)

    df_leader = pd.DataFrame(leaderboard)
    df_leader = df_leader.sort_values("Total", ascending=False)
    df_leader = df_leader[["Player", "Team", "Wildcard", "Divisional", "Conf_Champ", "Super_Bowl", "Total"]]
    st.dataframe(df_leader.set_index("Player"))

# ── Tab 3: Team Details ──────────────────────────────────────────────────────
with tab3:
    st.subheader("Team Player Scores")
    for team in sorted(team_scores, key=lambda x: x["Total Score"], reverse=True):
        st.subheader(f"{team['Team']}  (Total: {team['Total Score']:.2f})")
        pdf = pd.DataFrame(team["Players"])
        pdf["Position"] = pdf["Player"].apply(get_player_position)
        pdf["PosRank"] = pdf["Position"].apply(
            lambda x: POSITION_SORT_ORDER.index(x) if x in POSITION_SORT_ORDER else 999)
        pdf = pdf.sort_values(["PosRank", "Player"]).drop(columns="PosRank")
        pdf = pdf.set_index("Position")
        st.dataframe(pdf)

# Tab 4: Current NFL Game
with tab4:
    st.subheader("Current NFL Game")
    
    # Default values for dropdowns
    default_team1 = "Bills"      # Default first NFL team
    default_team2 = "Broncos"  # Default second NFL team
    default_round = "Divisional"  # Default round
    
    # Dropdown inputs for NFL teams and round
    col1, col2 = st.columns(2)
    with col1:
        selected_team1 = st.selectbox(
            "Select the first NFL team:",
            sorted(df_name_mapping["Team"].unique()),
            index=sorted(df_name_mapping["Team"].unique()).index(default_team1)
        )
    with col2:
        selected_team2 = st.selectbox(
            "Select the second NFL team:",
            sorted(df_name_mapping["Team"].unique()),
            index=sorted(df_name_mapping["Team"].unique()).index(default_team2)
        )
    
    selected_round = st.selectbox(
        "Select the current round:",
        rounds,
        index=rounds.index(default_round)
    )
    
    # Filter data for the selected teams and round
    if selected_team1 and selected_team2:
        current_game_data = []
        player_counts = {}  # Track counts and individual scores
        
        # Fetch fresh scores for all rounds (you might want to cache this in future)
        scores_by_round = {
            round_: get_scores_for_round("post", 2025, i + 1, df_teams.values.flatten())
            for i, round_ in enumerate(rounds)
        }
       
        for team in team_scores:
            team_name = team["Team"]
            players = team["Players"]
            
            # Find the player from each selected NFL team in this fantasy team
            team1_player = next(
                (p for p in players if p["Player"] in df_name_mapping[df_name_mapping["Team"] == selected_team1]["Name"].values),
                None
            )
            team2_player = next(
                (p for p in players if p["Player"] in df_name_mapping[df_name_mapping["Team"] == selected_team2]["Name"].values),
                None
            )
            
            # Update player counts for summary table
            for player in [team1_player, team2_player]:
                if player and "Player" in player:
                    player_name = player["Player"]
                    player_team = selected_team1 if player == team1_player else selected_team2
                    player_score = (scores_by_round[selected_round].get(player_name, 0) or 0) * MULTIPLIERS[selected_round]
                    
                    if player_name not in player_counts:
                        player_counts[player_name] = {
                            "Team": player_team,
                            "Count": 1,
                            "Current Game Score": player_score,
                        }
                    else:
                        player_counts[player_name]["Count"] += 1
            
            # Calculate this fantasy team's score from the selected matchup
            curr_game_score = 0
            if team1_player:
                curr_game_score += (scores_by_round[selected_round].get(team1_player["Player"], 0) or 0) * MULTIPLIERS[selected_round]
            if team2_player:
                curr_game_score += (scores_by_round[selected_round].get(team2_player["Player"], 0) or 0) * MULTIPLIERS[selected_round]
            
            # Add row to main table
            current_game_data.append({
                "Total": team["Total Score"],
                "Name": team_name,
                "CurrGame": curr_game_score,
                selected_team1: team1_player["Player"] if team1_player else "None",
                selected_team2: team2_player["Player"] if team2_player else "None",
            })
        
        # Create and sort the main dataframe
        current_game_df = pd.DataFrame(current_game_data)
        current_game_df = current_game_df.sort_values(by="Total", ascending=False).reset_index(drop=True)
        
        # ── FIXED RANKING: Competition style (1224) ──────────────────────────
        ranks = []
        current_rank = 1
        previous_total = None

        for idx, total in enumerate(current_game_df["Total"]):
            if idx == 0 or total < previous_total:  # New lower score group → start new rank
                current_rank = idx + 1
            ranks.append(f"{current_rank}{get_rank_suffix(current_rank)}")
            previous_total = total
        
        current_game_df.insert(0, "Place", ranks)
        current_game_df = current_game_df.set_index("Place")
        
        # Display main table
        st.dataframe(current_game_df)
        
        # Player counts summary
        st.markdown("### Player Counts")
        player_counts_df = pd.DataFrame.from_dict(player_counts, orient="index")
        player_counts_df.index.name = "Player"
        player_counts_df = player_counts_df[["Team", "Count", "Current Game Score"]]
        player_counts_df = player_counts_df.sort_values(by="Current Game Score", ascending=False)
        st.dataframe(player_counts_df)

# ── Tab 5: Scoring Settings ──────────────────────────────────────────────────
with tab5:
    st.subheader("Scoring Settings")
    
    # Offense Scoring
    st.markdown("### Offense Scoring")
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
    offense_df = pd.DataFrame(list(offense_scoring.items()), columns=["Action", "Points"])
    offense_df.set_index("Action", inplace=True)
    st.table(offense_df)
    
    # Kicking Scoring
    st.markdown("### Kicking Scoring")
    kicking_scoring = {
        "Field Goal 0-39 Yards": "3 points",
        "Field Goal 40-49 Yards": "4 points",
        "Field Goal 50+ Yards": "5 points",
        "Extra Point (PAT)": "1 point"
    }
    kicking_df = pd.DataFrame(list(kicking_scoring.items()), columns=["Action", "Points"])
    kicking_df.set_index("Action", inplace=True)
    st.table(kicking_df)
    
    # Defense/Special Teams Scoring
    st.markdown("### Defense/Special Teams Scoring")
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
    defense_df = pd.DataFrame(list(defense_scoring.items()), columns=["Action", "Points"])
    defense_df.set_index("Action", inplace=True)
    st.table(defense_df)

# ── Tab 6: Player Selections (FIXED) ─────────────────────────────────────────
with tab6:
    st.subheader("Player Selections")

    # Prepare selection data
    player_selection_counts = []
    for player in unique_players:
        selecting_teams = [team["Team"] for team in team_scores
                          for p in team["Players"] if p["Player"] == player]

        if selecting_teams:
            nfl_team = (df_name_mapping[df_name_mapping["Name"] == player]["Team"].iloc[0]
                        if player in df_name_mapping["Name"].values else "Unknown")

            player_selection_counts.append({
                "Player": player,
                "Selections": len(selecting_teams),
                "NFL Team": nfl_team,
                "Selected_By_List": selecting_teams
            })

    df_selections = pd.DataFrame(player_selection_counts)
    df_selections = df_selections.sort_values("Selections", ascending=False).reset_index(drop=True)

    # Dropdowns
    col1, col2 = st.columns(2)
    with col1:
        all_nfl = ["All"] + sorted(df_selections["NFL Team"].unique())
        selected_nfl = st.selectbox("Highlight players from NFL team", all_nfl, index=0)

    with col2:
        all_managers = ["All"] + sorted(df_teams.columns.tolist())
        selected_manager = st.selectbox("Highlight players owned by manager", all_managers, index=0)

    # Highlight logic
    highlight_mask = pd.Series(True, index=df_selections.index)

    if selected_nfl != "All":
        highlight_mask &= (df_selections["NFL Team"] == selected_nfl)

    if selected_manager != "All":
        highlight_mask &= df_selections["Selected_By_List"].apply(
            lambda teams: selected_manager in teams
        )

    colors = ['#e15759' if h else '#d3d3d3' for h in highlight_mask]

    # Bar chart
    fig = px.bar(
        df_selections,
        x="Player",
        y="Selections",
        title="Player Selection Frequency",
        text="Selections",
        color=colors,
        color_discrete_sequence=colors
    )

    fig.update_layout(
        xaxis_title="Player",
        yaxis_title="Number of teams that selected this player",
        xaxis={'categoryorder':'total descending'},
        showlegend=False,
        height=550,
        margin=dict(l=20, r=20, t=60, b=180),
        xaxis_tickangle=-45
    )
    fig.update_traces(textposition='auto', textfont_size=11, marker_line_width=0)

    st.plotly_chart(fig, use_container_width=True)

    # Tables
    st.markdown("### Most Selected Players")
    st.dataframe(df_selections.head(12)[["Player", "NFL Team", "Selections"]].set_index("Player"))

    st.markdown("### Least Selected Players (Selected Once)")
    once = df_selections[df_selections["Selections"] == 1].copy()

    # Create nice display column only for the table
    once["Selected By"] = once["Selected_By_List"].apply(lambda x: ", ".join(sorted(x)))

    st.dataframe(once[["Player", "NFL Team", "Selected By"]].set_index("Player"))
