import pandas as pd
from itertools import chain, cycle
from sleeper_wrapper import Stats
import streamlit as st

# Load data from the CSV files
file_path_teams = "Book3.csv"  # Replace with the path to Book3.csv
file_path_mapping = "Book4.csv"  # Replace with the path to Book4.csv

# Read data from CSV files
df_teams = pd.read_csv(file_path_teams)
df_teams_players = pd.read_csv(file_path_mapping)

# Drop empty columns if any
df_teams = df_teams.dropna(axis=1)

# Process the data
members = list(df_teams.columns)
members.sort()

dflist = []
totalslistWC = []
totalslistDV = []
totalslistCC = []
totalslistSB = []
totalslistTot = []

allpickedplayers = []

stats = Stats()
week_statsWC = stats.get_week_stats("post", 2023, 1)
week_statsDV = stats.get_week_stats("post", 2023, 2)
week_statsCC = stats.get_week_stats("post", 2023, 3)
week_statsSB = stats.get_week_stats("post", 2023, 4)

for name in members:
    mem1 = df_teams[name].tolist()
    allpickedplayers.extend(mem1)

    allscoresWC = []
    allscoresDV = []
    allscoresCC = []
    allscoresSB = []
    positions = []

    for player in mem1:
        # Mocked logic for getting player stats - replace with your implementation
        scoreWC = 10  # Example score for Wildcard round
        scoreDV = 15  # Example score for Divisional round
        scoreCC = 20  # Example score for Conf Championship round
        scoreSB = 25  # Example score for Super Bowl round

        allscoresWC.append(scoreWC)
        allscoresDV.append(scoreDV)
        allscoresCC.append(scoreCC)
        allscoresSB.append(scoreSB)

    df_final_table = pd.DataFrame(
        {
            "Player": mem1,
            "Wildcard": allscoresWC,
            "Divisional": allscoresDV,
            "Conf_Champ": allscoresCC,
            "Super_Bowl": allscoresSB,
        }
    )

    df_final_table["Conf_Champ"] = df_final_table["Conf_Champ"].multiply(1.5)
    df_final_table["Super_Bowl"] = df_final_table["Super_Bowl"].multiply(2)

    dflist.append(df_final_table)

    totalWC = df_final_table.Wildcard.sum()
    totalDV = df_final_table.Divisional.sum()
    totalCC = df_final_table.Conf_Champ.sum()
    totalSB = df_final_table.Super_Bowl.sum()
    totalTot = totalWC + totalDV + totalCC + totalSB

    totalslistWC.append(totalWC)
    totalslistDV.append(totalDV)
    totalslistCC.append(totalCC)
    totalslistSB.append(totalSB)
    totalslistTot.append(totalTot)

# Create the summary table
df_summary = pd.DataFrame(
    {
        "Name": members,
        "Wildcard": totalslistWC,
        "Divisional": totalslistDV,
        "Conf_Champ": totalslistCC,
        "Super_Bowl": totalslistSB,
        "Total": totalslistTot,
    }
)

df_summary = df_summary.sort_values("Total", ascending=False)
df_summary = df_summary.set_index("Name")

# Streamlit table display
st.title("Fantasy Football Playoff Standings")
st.table(df_summary)
