from basketball_reference_web_scraper import client
import numpy as np
import time
from requests.exceptions import HTTPError
from requests import Session

# Create a session for requests to use a specific user agent
session = Session()
session.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
)


def calculate_z_scores(team_array, key):
    # Extract box_plus_minus values from the team array
    bpm_values = [player[key] for player in team_array]
    # Calculate mean and standard deviation
    mean_bpm = sum(bpm_values) / len(bpm_values)
    std_dev_bpm = (
        sum([(bpm - mean_bpm) ** 2 for bpm in bpm_values]) / len(bpm_values)
    ) ** 0.5

    z_scores_array = []

    for player in team_array:
        z_score = (player[key] - mean_bpm) / std_dev_bpm
        z_scores_array.append(
            {
                "name": player["name"],
                "z_score": z_score,
                "minutes_played": player["minutes_played"],
            }
        )

    return z_scores_array


def group_by_team_and_calculate_z_scores(season_end_year):
    players_data = client.players_advanced_season_totals(
        season_end_year=season_end_year
    )
    team_grouped = {}

    # Group players by their team
    for player in players_data:
        team = player["team"]
        if team not in team_grouped:
            team_grouped[team] = []

        # Append the relevant data for the player
        team_grouped[team].append(
            {
                "name": player["name"],
                "team": team,
                "box_plus_minus": player["box_plus_minus"],
                "minutes_played": player["minutes_played"],
            }
        )

    # Convert teams to z_scores arrays
    all_teams_z_scores = [
        calculate_z_scores(team_grouped[team], "box_plus_minus")
        for team in team_grouped
    ]

    # Flattening the list of lists to a single list for cumulative z_scores
    all_players_z_scores = [player for team in all_teams_z_scores for player in team]

    # Calculating cumulative z_scores
    all_teams_cumulative_z_scores = calculate_z_scores(all_players_z_scores, "z_score")

    # Filter players with below average minutes played
    percentile_70_minutes = np.percentile(
        [player["minutes_played"] for player in all_players_z_scores], 70
    )

    # Filter players with minutes_played above 70th percentile
    filtered_results = [
        player
        for player in all_teams_cumulative_z_scores
        if player["minutes_played"] >= percentile_70_minutes
    ]

    return filtered_results


def get_cumulative_z_scores(start_year, end_year):
    cumulative_z_scores = {}
    seasons_count = {}
    RETRY_TIMES = 3  # Number of times to retry fetching data

    for year in range(start_year, end_year + 1):
        print(f"Processing year {year}...")
        attempts = 0

        while attempts < RETRY_TIMES:
            try:
                yearly_results = group_by_team_and_calculate_z_scores(year)
                # ... [rest of your logic]
                break  # Break out of the retry loop if successful
            except HTTPError as e:
                if e.response.status_code == 429:  # Too Many Requests
                    attempts += 1
                    print(f"Hit rate limit. Retrying in {2 ** attempts} seconds...")
                    time.sleep(2**attempts)  # Exponential backoff
                else:
                    raise e  # If it's not a rate limit error, raise it

        print(f"Processing year {year}...")
        yearly_results = group_by_team_and_calculate_z_scores(year)

        # Calculate average and 70th percentile of minutes played
        average_z_score = np.mean([player["z_score"] for player in yearly_results])
        percentile_70_minutes = np.percentile(
            [player["minutes_played"] for player in yearly_results], 70
        )

        # Filter out players based on above-average Z-score and 70th percentile minutes
        filtered_players = [
            player
            for player in yearly_results
            if player["minutes_played"] >= percentile_70_minutes
        ]

        # Accumulate Z-scores and seasons count for each player
        for player in filtered_players:
            if player["name"] not in cumulative_z_scores:
                cumulative_z_scores[player["name"]] = []
                seasons_count[player["name"]] = 0
            cumulative_z_scores[player["name"]].append(player["z_score"])
            seasons_count[player["name"]] += 1

    # For each player, only sum Z-scores that are above their own average
    for player, scores in cumulative_z_scores.items():
        avg_score = sum(scores) / seasons_count[player]
        cumulative_z_scores[player] = sum(
            score for score in scores if score > avg_score
        )

    return cumulative_z_scores


# Calculate cumulative Z-scores from 1983 to 2021
cumulative_scores = get_cumulative_z_scores(1980, 2021)

# Sort and print top five
sorted_players = sorted(cumulative_scores.items(), key=lambda x: x[1], reverse=True)
top_five_players = sorted_players[:5]

for player, score in top_five_players:
    print(f"Name: {player}, Cumulative Z-score: {score:.2f}")
