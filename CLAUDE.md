# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Django-based football match prediction system using Machine Learning. The system imports historical match data from multiple sources (Football-Data.co.uk CSVs and SofaScore API), trains 8 ML models to predict various match outcomes, and generates predictions for upcoming matches.

**Current Database Status (as of 2025-12-26):**
- 254 teams (deduplicated) - down from 286 after fuzzy consolidation
- 20,874 matches (all cleaned, no duplicates)
- 1,333 players with statistics
- 1,092 TeamStats records
- 2,222 HeadToHead records
- Match statistics: corners, shots, xG, possession, cards, fouls

## Development Commands

### Database Setup
```bash
python manage.py makemigrations
python manage.py migrate
```

### Data Import

**RECOMMENDED: Unified SofaScore Import (ALL data)**
```bash
# Import everything for one competition/season
python manage.py import_sofascore_complete --competitions PL --seasons 2024 --all-data

# Import multiple competitions
python manage.py import_sofascore_complete --competitions PL,PD,BL1,SA,FL1 --seasons 2024,2023 --all-data

# Import specific modules only
python manage.py import_sofascore_complete --competitions CL --seasons 2024 --teams-only
python manage.py import_sofascore_complete --competitions PL --seasons 2024 --matches-only --players-only

# Available flags:
# --all-data: Import teams, matches, match stats, players, player stats, standings, injuries
# --teams-only: Import only teams
# --matches-only: Import only matches with statistics
# --players-only: Import only players with statistics
# --standings-only: Import only team standings
# --injuries-only: Import only player injuries (current injury status per team)
# --dry-run: Preview what would be imported without saving
# --force: Reimport existing data
```

**Alternative: Legacy imports**
```bash
# Import domestic leagues from Football-Data.co.uk CSVs (no rate limit)
python manage.py import_leagues --years 2015-2024 --competitions PL,PD,BL1,SA,FL1

# Import upcoming fixtures from Football-Data.org API (10 requests/minute limit)
python manage.py import_fixtures --competitions PL,PD,BL1,SA,FL1 --season 2025
```

### Consolidate Duplicate Teams
```bash
# Method 1: Exact name matching (original command)
python manage.py consolidate_teams
python manage.py consolidate_teams --dry-run  # Preview only

# Method 2: FUZZY name matching (RECOMMENDED for variants like "Leicester" vs "Leicester City")
python manage.py consolidate_teams_fuzzy --competition PL --threshold 95 --dry-run  # Preview
python manage.py consolidate_teams_fuzzy --competition PL --threshold 95  # Execute

# Consolidate all competitions
python manage.py consolidate_teams_fuzzy --threshold 95

# Lower threshold for more matches (be careful of false positives)
python manage.py consolidate_teams_fuzzy --threshold 85 --dry-run
```

### Clean Duplicate Matches
```bash
# IMPORTANT: If you imported from both CSV and SofaScore, you may have duplicates
# This happens because CSV imports don't have api_id, so the unique constraint doesn't work

# Check and remove duplicate matches (keeps the one with api_id/more data)
python manage.py cleanup_duplicate_matches --dry-run  # Preview only
python manage.py cleanup_duplicate_matches  # Actually remove duplicates
```

### Download Team Logos and Player Photos
```bash
# Download images from SofaScore API and store locally in media/ folder
# Images saved as: media/teams/{team_id}.png and media/players/{player_id}.png
# Updates Team.crest_url and Player.photo fields with relative paths

# Download everything (teams + players)
python manage.py download_images --teams --players

# Download only team logos
python manage.py download_images --teams-only

# Download only player photos
python manage.py download_images --players-only

# Preview without downloading
python manage.py download_images --dry-run --limit 10

# Re-download existing images
python manage.py download_images --teams --players --force

# Download with limit (for testing)
python manage.py download_images --teams-only --limit 20
```

### Re-import Specific Matchdays or Full Seasons
```bash
# Re-import Premier League matchday 20 from 2024/25 season
python manage.py reimport_matchday --competition PL --seasons 2024 --matchday 20

# Re-import multiple matchdays from one season
python manage.py reimport_matchday --competition PL --seasons 2024 --matchday 18,19,20

# Re-import ALL matchdays from 2024/25 season
python manage.py reimport_matchday --competition PL --seasons 2024

# Re-import ALL matchdays from multiple seasons
python manage.py reimport_matchday --competition PL --seasons 2023,2024

# Re-import specific matchday from multiple seasons
python manage.py reimport_matchday --competition PL --seasons 2023,2024 --matchday 20

# Preview without actually importing
python manage.py reimport_matchday --competition PL --seasons 2024 --matchday 20 --dry-run

# Force re-import even if data already exists
python manage.py reimport_matchday --competition PL --seasons 2024 --force
```

**What `reimport_matchday` imports:**
- ✅ Match statistics (shots, corners, possession, xG, etc.)
- ✅ Lineups and player statistics per match
- ✅ Match incidents (goals, cards, substitutions, VAR)
- ✅ Advanced match data (momentum graph, shotmap, best players)

**Key features:**
- `--seasons`: Required. One or multiple seasons (comma-separated)
- `--matchday`: Optional. If omitted, imports ALL matchdays from specified season(s)
- `--force`: Re-import even if data already exists
- `--dry-run`: Preview what would be imported

**Difference between commands:**
- `import_sofascore_complete --all-data`: Imports **everything** (teams, matches, players, stats, standings)
- `reimport_matchday`: Re-imports **only match-level data** (stats, lineups, incidents) for existing matches

### Calculate Statistics
```bash
# Calculate ALL statistics (TeamStats + HeadToHead) - RECOMMENDED
python manage.py calculate_stats --competitions PL,PD,BL1,SA,FL1,CL --force

# Calculate with specific seasons
python manage.py calculate_stats --seasons 2023,2024 --competitions PL,PD

# Calculate only team statistics by season
python manage.py calculate_team_stats --seasons 2023,2024 --competitions PL,PD

# Calculate only head-to-head records
python manage.py calculate_head_to_head --competitions PL,PD --recent 10
```

### Model Training
```bash
# Train all 8 models with specified competitions and seasons
python manage.py train_models --competitions PL,PD,BL1,SA,FL1 --seasons 2020,2021,2022,2023,2024
```

**Training Results (8,637 matches, 33 features):**
- **over_105_corners**: 61.6% accuracy (BEST)
- **over_25**: 55.5% accuracy
- **btts**: 53.6% accuracy
- **over_95_corners**: 50.3% accuracy
- **result**: 49.9% accuracy
- **total_corners**: MAE 2.64
- **total_shots**: MAE 4.60
- **total_shots_on_target**: MAE 2.47

### Generate Predictions
```bash
# Generate predictions for next N days
python manage.py predict --days 7 --competitions PL,PD,BL1,SA,FL1
```

### Get Betting Odds & Value Bet Analysis
```bash
# Requires API_KEY_ODDS environment variable
export API_KEY_ODDS="your_api_key"

# Basic usage - analyzes odds vs model predictions
python manage.py get_odds --days 7 --competitions PL,PD

# With custom bankroll and Kelly fraction
python manage.py get_odds --days 7 --competitions PL,PD --bankroll 2000 --kelly 0.33

# Adjust minimum edge threshold for value bets
python manage.py get_odds --days 7 --competitions PL,PD --min-edge 0.05  # 5% minimum edge

# Available parameters:
# --bankroll: Bankroll for stake calculations (default: 1000)
# --kelly: Kelly fraction for stake sizing (default: 0.25 = quarter Kelly)
# --min-edge: Minimum edge threshold for value bets (default: 0.03 = 3%)
```

**Output includes:**
- Visual table with all markets (h2h, totals, spreads)
- Model probabilities vs bookmaker implied odds
- Edge calculation (Model % - Implied %)
- Bet grade (A+ to F based on edge size)
- Kelly criterion stake recommendations
- Expected Value (EV) and ROI for each bet
- Value bets highlighted in green

### Django Admin & Web Interface
```bash
python manage.py runserver
# Access matches list at http://localhost:8000/matches/
# Access admin at http://localhost:8000/admin/
```

## Architecture

### Core App Structure
- **predictions/** - Main Django app containing all football prediction logic
  - **models.py** - 7 core models: Competition, Team, Match, TeamStats, HeadToHead, Prediction, Player
  - **ml/** - Machine Learning modules using Django ORM
    - **predictor.py** - EnhancedPredictor class with 8 trained models
    - **enhanced_features.py** - EnhancedFeatureEngineer with 33 features
    - **features.py** - Base FeatureEngineer class
    - **ensemble.py** - Ensemble predictor combining ML + Dixon-Coles
  - **scrapers/** - Web scrapers for data collection
    - **transfermarkt_scraper.py** - Market values scraper
    - **utils.py** - Fuzzy matching utilities
  - **management/commands/** - Custom Django management commands
    - **import_sofascore_complete.py** - Unified SofaScore import (teams, matches, players, stats)
    - **reimport_matchday.py** - Re-import specific matchdays or full seasons (stats, lineups, incidents)
    - **import_leagues.py** - Import from Football-Data.co.uk CSVs
    - **import_fixtures.py** - Import upcoming fixtures
    - **import_transfermarkt.py** - Import market values
    - **consolidate_teams.py** - Merge duplicate teams (exact name matching)
    - **consolidate_teams_fuzzy.py** - Merge duplicate teams (fuzzy name matching)
    - **cleanup_duplicate_matches.py** - Remove duplicate matches (keeps api_id version)
    - **download_images.py** - Download team logos and player photos from SofaScore
    - **calculate_stats.py** - Calculate ALL statistics (wrapper for team_stats + h2h)
    - **calculate_team_stats.py** - Calculate TeamStats per team/season
    - **calculate_head_to_head.py** - Calculate HeadToHead records between teams
    - **train_models.py** - Train ML models
    - **predict.py** - Generate predictions
    - **get_odds.py** - Fetch odds from The Odds API & analyze value bets
  - **views.py** - Web views for match listings
  - **urls.py** - URL routing
  - **templates/** - HTML templates for web interface

### Data Model Relationships

**Competition** (PL, PD, BL1, SA, FL1, CL, etc.)
- → Teams (one-to-many)
- → Matches (one-to-many)

**Team**
- → home_matches (as home_team)
- → away_matches (as away_team)
- → stats (TeamStats per season)
- → h2h_as_team1, h2h_as_team2 (HeadToHead records)
- → players (Player)
- **Global unique constraint**: api_id (not per competition)
- **crest_url**: Path to team logo (e.g., 'teams/2523.png')

**Match** (historical and future)
- References: competition, home_team, away_team
- Basic stats: scores (FT/HT), shots, corners, cards, fouls, offsides, possession
- Advanced stats: xG, xA, attendance, referee, hit woodwork, free kicks, booking points
- Betting odds (74 fields from Football-Data CSVs):
  - Match result (1X2): Bet365, Pinnacle, William Hill, Betfair, Betbrain aggregates, Market max/avg
  - Over/Under 2.5: Bet365, Pinnacle, Betbrain aggregates, Market max/avg
  - Asian Handicap: Bet365, Pinnacle, Betbrain aggregates, Market max/avg with handicap sizes
- Computed properties: result (H/D/A), half_time_result, total_goals, both_teams_scored

**Player** (NEW)
- References: team
- Basic info: name, position, nationality, date_of_birth, height, market_value
- Statistics: goals, assists, appearances, minutes_played, yellow_cards, red_cards
- Advanced: xG, xA, rating, shots, shots_on_target, pass_accuracy
- **photo**: Path to player photo (e.g., 'players/12345.png')

**TeamStats** (calculated per team/season/competition)
- General: matches_played, wins, draws, losses, goals_for/against, points, goal_difference
- Home stats: home_matches, home_wins/draws/losses, home_goals_for/against
- Away stats: away_matches, away_wins/draws/losses, away_goals_for/against
- Advanced: avg_goals_for/against, clean_sheets, failed_to_score, btts_count, over_25_count
- xG metrics: avg_xg_for, avg_xg_against, xg_overperformance, total_xg_for/against
- Recent form (last 5): form_points, form_goals_for/against

**HeadToHead** (calculated per pair of teams)
- Total matches, team1_wins, team2_wins, draws
- Total goals: team1_goals, team2_goals
- Recent matches (JSON): last 10 encounters with dates, scores, venues, results

**Prediction**
- Links to Match
- Contains probabilities: prob_home, prob_draw, prob_away
- Additional markets: over_25, btts, corners (9.5/10.5), shots

### Machine Learning Pipeline

**8 Models Trained:**
1. **result** - Match outcome (Home/Draw/Away) - Accuracy 49.9%
2. **over_25** - Over 2.5 goals - Accuracy 55.5%
3. **btts** - Both teams to score - Accuracy 53.6%
4. **over_95_corners** - Over 9.5 corners - Accuracy 50.3%
5. **over_105_corners** - Over 10.5 corners - Accuracy 61.6% ⭐ BEST
6. **total_corners** - Total corners regression - MAE 2.64
7. **total_shots** - Total shots regression - MAE 4.60
8. **total_shots_on_target** - Shots on target regression - MAE 2.47

**33 Features Used:**
- Form metrics (general, last 5, last 3, momentum)
- Home/away specific performance (recent and season-long)
- Head-to-head history (wins, draws, BTTS%, Over 2.5%)
- Season statistics (PPG, goals, clean sheets, BTTS%, Over 2.5%)
- Season stats split by venue (home team playing at home, away team playing away)
- H2H advanced metrics (BTTS rate, Over 2.5 rate, high-scoring rate)
- Advanced stats (corners, shots, conversion rate, accuracy)
- Derived features (differentials, strength indices, venue advantages)
- Combined indicators (both teams high BTTS/Over2.5 tendency)

**Algorithms:**
- RandomForest (baseline)
- XGBoost (if installed)
- LightGBM (if installed) - Primary choice
- CalibratedClassifierCV for probability calibration

**Model Storage:**
- Trained models saved to: `predictions/ml/enhanced_models.pkl`

### Feature Engineering Flow

When predicting a match:
1. **EnhancedFeatureEngineer** extracts features for both teams
2. Features calculated from historical matches before the target match date
3. Features include:
   - Recent form (last 5 and last 3 matches)
   - Home/away specific stats
   - Season-long statistics
   - Head-to-head history
   - Momentum indicators (improving vs declining)
   - Advanced stats (corners, shots, xG, accuracy rates)
4. Features normalized using StandardScaler
5. Predictions generated using calibrated models

## Data Sources

### SofaScore API (PRIMARY - Comprehensive)
- **Unified import**: import_sofascore_complete.py
- **Coverage**: All major leagues + Champions League
- **Data included**:
  - Teams (with global api_id to prevent duplicates)
  - Matches (finished and scheduled)
  - Match statistics (corners, shots, xG, possession, cards, fouls)
  - Players with detailed stats
  - Team standings/classification
- **Rate limiting**: May return 403 if overused
- **Tournament IDs**:
  - PL (Premier League): 17
  - PD (La Liga): 8
  - BL1 (Bundesliga): 35
  - SA (Serie A): 23
  - FL1 (Ligue 1): 34
  - CL (Champions League): 7

### Football-Data.co.uk (Secondary - Historical CSVs)
- Free CSV downloads, no API key needed
- Covers: Premier League (PL), La Liga (PD), Bundesliga (BL1), Serie A (SA), Ligue 1 (FL1)
- Years: 2015-2024 available
- Data includes: results, shots, corners, cards, betting odds (74 fields)
- No rate limiting concerns
- **Use case**: Historical data, betting odds

### The Odds API
- Requires API key (set via API_KEY_ODDS environment variable)
- Used by get_odds command
- Fetches current betting odds from bookmakers
- **Use case**: Live odds for value bet analysis

## Important Implementation Notes

### Team Deduplication
- **Global api_id lookup**: Teams stored globally, not per competition
- **SofaScore issue**: Same team has different api_ids in different competitions
  - Example: Barcelona = api_id 81 (La Liga), 2817 (Champions League)
- **Solution**: Use `consolidate_teams` command to merge duplicates by exact name match
- **Result**: 254 unique teams (deduplicated from 263)

### Match Deduplication
- **Issue**: Importing from both CSV and SofaScore creates duplicates
  - CSV imports have `api_id = NULL`
  - SofaScore imports have valid `api_id`
  - SQL's `UNIQUE` constraint doesn't prevent NULL duplicates (NULL != NULL)
- **Detection**: Same (competition, home_team, away_team, utc_date) but different IDs
- **Solution**: Use `cleanup_duplicate_matches` command
  - Keeps matches with `api_id` (SofaScore data is more complete)
  - Deletes matches without `api_id` (CSV data has fewer statistics)
- **Prevention**:
  - `import_leagues.py` now checks for existing matches before creating
  - `import_sofascore_complete.py` uses `api_id` unique constraint

### Django ORM Patterns Used
- All ML feature engineering uses Django ORM queries (no raw SQL)
- Queries optimized with `select_related()` and `prefetch_related()`
- Uses Q objects for complex filtering
- Date filtering: `utc_date__lt=before_date` to avoid data leakage
- Async support: `sync_to_async` for database operations in async contexts

### Match Status Values
- `FINISHED` - Completed matches (used for training)
- `SCHEDULED` - Future matches (used for predictions)
- `TIMED` - Future matches with confirmed time
- `POSTPONED`, `CANCELLED`, `IN_PLAY` - Other states

### Competition Codes
- **PL** - Premier League (England)
- **PD** - La Liga (Spain)
- **BL1** - Bundesliga (Germany)
- **SA** - Serie A (Italy)
- **FL1** - Ligue 1 (France)
- **CL** - Champions League

### Environment Variables
Create `.env` file in project root:
```env
API_KEY_ODDS=your_api_key_here
SECRET_KEY=your_django_secret_key
DEBUG=True
```

## Database Schema

- **SQLite** used by default (`db.sqlite3`)
- All models use explicit `db_table` names for consistency
- Key indexes on: competition/season, team relationships, dates, status
- Unique constraints: Competition.api_id, Team.api_id, Match.api_id
- Composite unique: TeamStats (team, competition, season), HeadToHead (team1, team2)

## Testing Approach

Currently no automated tests. When implementing tests:
- Test ML predictor with known match data
- Test feature engineering calculations
- Test data import commands with sample data
- Mock external API calls (SofaScore, The Odds API)

## Performance Considerations

- Model training takes ~5 minutes with 8,637 matches (2020-2024)
- SofaScore import: ~2-3 minutes per competition/season
- Import of 10 years domestic leagues from CSVs: ~10 minutes
- Prediction generation: seconds for 7 days of matches
- Feature calculation: 5-10 minutes for all competitions (cached in TeamStats)

## Custom Skills

### betting-analyst
Location: `.claude/skills/betting-analyst/`

Professional sports betting analysis skill for identifying value bets using statistical models. This skill provides:

**Core Capabilities:**
- Value bet detection (comparing model probabilities vs bookmaker odds)
- Expected Value (EV) calculation
- Kelly Criterion for optimal bankroll management
- Closing Line Value (CLV) analysis
- Bet grading system (A+ to D based on edge)
- Model calibration using Brier score

**Usage:**
Ask Claude to analyze betting opportunities, calculate value bets, or determine optimal stake sizes. The skill triggers on queries about:
- Odds analysis
- Value betting opportunities
- Betting edge calculation
- Bankroll management
- Sports prediction model evaluation

**Key Formulas:**
- Value Bet = Model Probability > Implied Probability from Odds
- Kelly Stake = (Edge × Probability) / (Odds - 1) × Bankroll × Fraction
- Expected Value = (Probability × Win) - ((1 - Probability) × Loss)

**Reference Materials:**
- `references/poisson-models.md` - Poisson distribution for goal modeling
- `references/features.md` - Feature engineering for betting models
- `references/line-movement.md` - Analyzing odds movement
- `scripts/value_analyzer.py` - Python implementation of value analysis

## Workflow Recommendations

### Initial Setup
1. Migrate database: `python manage.py migrate`
2. Import historical data: `python manage.py import_sofascore_complete --competitions PL,PD,BL1,SA,FL1 --seasons 2020,2021,2022,2023,2024 --all-data`
3. Consolidate duplicate teams:
   - `python manage.py consolidate_teams`
   - `python manage.py consolidate_teams_fuzzy --threshold 95`  # For name variants
4. Clean duplicate matches: `python manage.py cleanup_duplicate_matches`
5. Calculate statistics: `python manage.py calculate_stats --competitions PL,PD,BL1,SA,FL1 --force`
6. Train models: `python manage.py train_models --competitions PL,PD,BL1,SA,FL1 --seasons 2020,2021,2022,2023,2024`

### Weekly Updates
1. Import new matches: `python manage.py import_sofascore_complete --competitions PL,PD,BL1,SA,FL1 --seasons 2025 --matches-only`
2. Update statistics: `python manage.py calculate_stats --competitions PL,PD,BL1,SA,FL1`
3. Generate predictions: `python manage.py predict --days 7 --competitions PL,PD,BL1,SA,FL1`
4. Analyze value bets: `python manage.py get_odds --days 7 --competitions PL,PD,BL1,SA,FL1 --min-edge 0.03`

### Seasonal Maintenance
- Retrain models quarterly with new data
- Check for duplicate teams after major competitions
- Backup database regularly
