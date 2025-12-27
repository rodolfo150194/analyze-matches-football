# Feature Engineering for Football Prediction

## Feature Categories

### 1. Form Features (Recent Performance)

```python
def calculate_form_features(team_matches, n_matches=5):
    """
    Calculate rolling form indicators.
    
    Returns dict of features for the team.
    """
    recent = team_matches[-n_matches:]
    
    return {
        # Points-based form
        "points_last_5": sum(m['points'] for m in recent),
        "points_per_game": sum(m['points'] for m in recent) / n_matches,
        "win_rate_5": sum(1 for m in recent if m['points'] == 3) / n_matches,
        
        # Goals form
        "goals_scored_5": sum(m['goals_for'] for m in recent),
        "goals_conceded_5": sum(m['goals_against'] for m in recent),
        "goal_diff_5": sum(m['goals_for'] - m['goals_against'] for m in recent),
        
        # xG form (if available)
        "xg_for_5": sum(m.get('xg_for', 0) for m in recent),
        "xg_against_5": sum(m.get('xg_against', 0) for m in recent),
        "xg_diff_5": sum(m.get('xg_for', 0) - m.get('xg_against', 0) for m in recent),
        
        # Trend (comparing last 3 to previous 3)
        "form_trend": _calculate_trend(recent),
    }

def _calculate_trend(matches):
    """Positive = improving, negative = declining."""
    if len(matches) < 6:
        return 0
    recent_3 = sum(m['points'] for m in matches[-3:])
    previous_3 = sum(m['points'] for m in matches[-6:-3])
    return recent_3 - previous_3
```

### 2. Home/Away Splits

```python
def home_away_features(team_matches, venue):
    """
    Separate performance by venue. Critical for football.
    
    venue: 'home' or 'away'
    """
    venue_matches = [m for m in team_matches if m['venue'] == venue][-10:]
    
    if not venue_matches:
        return {}
    
    return {
        f"{venue}_win_rate": sum(1 for m in venue_matches if m['points'] == 3) / len(venue_matches),
        f"{venue}_goals_avg": sum(m['goals_for'] for m in venue_matches) / len(venue_matches),
        f"{venue}_conceded_avg": sum(m['goals_against'] for m in venue_matches) / len(venue_matches),
        f"{venue}_clean_sheets": sum(1 for m in venue_matches if m['goals_against'] == 0) / len(venue_matches),
    }
```

### 3. Head-to-Head Features

```python
def h2h_features(home_team, away_team, historical_matches, n_matches=10):
    """
    Historical matchups between the two teams.
    """
    h2h = [m for m in historical_matches 
           if set([m['home'], m['away']]) == set([home_team, away_team])][-n_matches:]
    
    if len(h2h) < 3:
        return {"h2h_sample_size": len(h2h)}  # Not enough data
    
    home_wins = sum(1 for m in h2h if 
                    (m['home'] == home_team and m['home_goals'] > m['away_goals']) or
                    (m['away'] == home_team and m['away_goals'] > m['home_goals']))
    
    return {
        "h2h_home_win_rate": home_wins / len(h2h),
        "h2h_avg_total_goals": sum(m['home_goals'] + m['away_goals'] for m in h2h) / len(h2h),
        "h2h_btts_rate": sum(1 for m in h2h if m['home_goals'] > 0 and m['away_goals'] > 0) / len(h2h),
        "h2h_sample_size": len(h2h),
    }
```

### 4. Strength Ratings (ELO-like)

```python
def calculate_elo(team_matches, k=20, home_advantage=100):
    """
    ELO rating system adapted for football.
    
    k: update speed (higher = more reactive)
    home_advantage: points added to home team's rating
    """
    ratings = {}
    
    for match in team_matches:
        home, away = match['home'], match['away']
        
        # Initialize if new
        ratings.setdefault(home, 1500)
        ratings.setdefault(away, 1500)
        
        # Expected scores
        home_rating = ratings[home] + home_advantage
        away_rating = ratings[away]
        
        exp_home = 1 / (1 + 10 ** ((away_rating - home_rating) / 400))
        exp_away = 1 - exp_home
        
        # Actual scores (1 = win, 0.5 = draw, 0 = loss)
        if match['home_goals'] > match['away_goals']:
            actual_home, actual_away = 1, 0
        elif match['home_goals'] < match['away_goals']:
            actual_home, actual_away = 0, 1
        else:
            actual_home, actual_away = 0.5, 0.5
        
        # Update ratings
        ratings[home] += k * (actual_home - exp_home)
        ratings[away] += k * (actual_away - exp_away)
    
    return ratings

def elo_features(home_elo, away_elo, home_advantage=100):
    """Convert ELO to match features."""
    elo_diff = (home_elo + home_advantage) - away_elo
    
    return {
        "elo_diff": elo_diff,
        "elo_home_win_prob": 1 / (1 + 10 ** (-elo_diff / 400)),
        "elo_home": home_elo,
        "elo_away": away_elo,
    }
```

### 5. Rest & Fixture Congestion

```python
from datetime import datetime, timedelta

def fatigue_features(team, match_date, schedule):
    """
    Rest days and fixture congestion.
    """
    team_schedule = [m for m in schedule if team in [m['home'], m['away']]]
    team_schedule.sort(key=lambda x: x['date'])
    
    # Days since last match
    previous = [m for m in team_schedule if m['date'] < match_date]
    days_rest = (match_date - previous[-1]['date']).days if previous else 7
    
    # Matches in last 14/30 days
    fourteen_ago = match_date - timedelta(days=14)
    thirty_ago = match_date - timedelta(days=30)
    
    matches_14d = len([m for m in previous if m['date'] >= fourteen_ago])
    matches_30d = len([m for m in previous if m['date'] >= thirty_ago])
    
    return {
        "days_rest": days_rest,
        "short_rest": 1 if days_rest <= 3 else 0,
        "matches_last_14d": matches_14d,
        "matches_last_30d": matches_30d,
        "fixture_congestion": matches_30d / 30 * 7,  # matches per week
    }
```

### 6. League Position & Points Gap

```python
def table_features(home_team, away_team, league_table):
    """
    Current league standing context.
    """
    home_pos = league_table[home_team]['position']
    away_pos = league_table[away_team]['position']
    home_pts = league_table[home_team]['points']
    away_pts = league_table[away_team]['points']
    
    return {
        "position_diff": away_pos - home_pos,  # positive = home higher
        "points_diff": home_pts - away_pts,
        "home_position": home_pos,
        "away_position": away_pos,
        "top_6_home": 1 if home_pos <= 6 else 0,
        "top_6_away": 1 if away_pos <= 6 else 0,
        "relegation_home": 1 if home_pos >= 18 else 0,
        "relegation_away": 1 if away_pos >= 18 else 0,
    }
```

### 7. Motivation & Context

```python
def motivation_features(match_context):
    """
    Situational factors affecting motivation.
    """
    return {
        "is_derby": match_context.get('is_derby', 0),
        "is_cup": match_context.get('is_cup', 0),
        "home_must_win": match_context.get('home_needs_points', 0),
        "away_must_win": match_context.get('away_needs_points', 0),
        "home_nothing_to_play": match_context.get('home_safe', 0),
        "away_nothing_to_play": match_context.get('away_safe', 0),
        "season_stage": match_context.get('matchweek', 0) / 38,  # 0-1 scale
    }
```

### 8. Squad & Injury Features

```python
def squad_features(team_injuries, team_suspensions):
    """
    Missing players impact.
    """
    # Weight by player importance (if available)
    injury_impact = sum(p.get('rating', 1) for p in team_injuries)
    suspension_impact = sum(p.get('rating', 1) for p in team_suspensions)
    
    return {
        "injuries_count": len(team_injuries),
        "suspensions_count": len(team_suspensions),
        "missing_impact": injury_impact + suspension_impact,
        "key_players_out": sum(1 for p in team_injuries + team_suspensions 
                               if p.get('is_key_player', False)),
    }
```

## Feature Selection Best Practices

1. **Correlation check**: Remove features with >0.9 correlation
2. **Importance ranking**: Use Random Forest feature importance
3. **Time validation**: Always validate on future data, never past
4. **League-specific**: Some features work better in certain leagues
5. **Sample size**: Each feature needs 100+ samples to be reliable

## Feature Engineering Pipeline

```python
def build_match_features(home_team, away_team, match_date, data):
    """
    Complete feature vector for a match.
    """
    features = {}
    
    # Form (both teams)
    features.update({f"home_{k}": v for k, v in 
                    calculate_form_features(data.get_matches(home_team)).items()})
    features.update({f"away_{k}": v for k, v in 
                    calculate_form_features(data.get_matches(away_team)).items()})
    
    # Home/Away splits
    features.update(home_away_features(data.get_matches(home_team), 'home'))
    features.update(home_away_features(data.get_matches(away_team), 'away'))
    
    # H2H
    features.update(h2h_features(home_team, away_team, data.historical))
    
    # ELO
    elos = calculate_elo(data.all_matches)
    features.update(elo_features(elos.get(home_team, 1500), 
                                  elos.get(away_team, 1500)))
    
    # Fatigue
    features.update({f"home_{k}": v for k, v in 
                    fatigue_features(home_team, match_date, data.schedule).items()})
    features.update({f"away_{k}": v for k, v in 
                    fatigue_features(away_team, match_date, data.schedule).items()})
    
    # Table
    features.update(table_features(home_team, away_team, data.league_table))
    
    return features
```

## Feature Importance (Typical Ranking)

1. ELO/Rating difference (~25% importance)
2. Recent form xG (~15%)
3. Home advantage (~12%)
4. Head-to-head (~8%)
5. Rest days difference (~7%)
6. League position (~7%)
7. Goals scored form (~6%)
8. Goals conceded form (~5%)
9. Fixture congestion (~5%)
10. Other features (~10%)

Note: Importance varies by league and model type.
