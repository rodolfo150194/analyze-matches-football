# Football Prediction System ⚽

Django-based football match prediction system using Machine Learning to analyze historical data and generate predictions for upcoming matches.

## Features

- **Comprehensive Data Import**: Import match data from SofaScore API and Football-Data.co.uk
- **Machine Learning Models**: 8 trained models predicting various match outcomes
- **Advanced Statistics**: Calculate team stats, head-to-head records, and form metrics
- **Value Bet Analysis**: Compare model predictions vs bookmaker odds using Kelly Criterion
- **Web Interface**: View and filter matches through a modern web UI
- **Player Statistics**: Track player performance metrics including xG, xA, and ratings

## Current Database Status

As of 2025-12-26:
- **254 teams** (deduplicated across competitions)
- **19,820 matches** (18,845 finished, 975 scheduled)
- **1,333 players** with detailed statistics
- **1,092 team statistics** records
- **2,222 head-to-head** matchup records

## Model Performance

Trained on 8,637 matches (2020-2024) with 33 features:

| Model | Performance | Type |
|-------|------------|------|
| **Over 10.5 Corners** | 61.6% accuracy | Best performer |
| **Over 2.5 Goals** | 55.5% accuracy | Classification |
| **BTTS** | 53.6% accuracy | Classification |
| **Over 9.5 Corners** | 50.3% accuracy | Classification |
| **Match Result** | 49.9% accuracy | Classification |
| **Total Corners** | MAE 2.64 | Regression |
| **Total Shots** | MAE 4.60 | Regression |
| **Shots on Target** | MAE 2.47 | Regression |

## Installation

### Prerequisites

- Python 3.10+
- pip
- Virtual environment (recommended)

### Setup

1. **Clone the repository**
```bash
git clone <repository_url>
cd football_django
```

2. **Create and activate virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**

Create a `.env` file in the project root:
```env
SECRET_KEY=your_django_secret_key
DEBUG=True
API_KEY_ODDS=your_odds_api_key  # Optional, for value bet analysis
```

5. **Initialize database**
```bash
python manage.py migrate
```

## Quick Start

### 1. Import Historical Data

```bash
# Import from SofaScore (recommended)
python manage.py import_sofascore_complete \
    --competitions PL,PD,BL1,SA,FL1 \
    --seasons 2020,2021,2022,2023,2024 \
    --all-data
```

### 2. Consolidate Duplicate Teams

```bash
python manage.py consolidate_teams
```

### 3. Calculate Statistics

```bash
python manage.py calculate_stats \
    --competitions PL,PD,BL1,SA,FL1 \
    --force
```

### 4. Train Models

```bash
python manage.py train_models \
    --competitions PL,PD,BL1,SA,FL1 \
    --seasons 2020,2021,2022,2023,2024
```

### 5. Generate Predictions

```bash
python manage.py predict \
    --days 7 \
    --competitions PL,PD,BL1,SA,FL1
```

### 6. View Matches (Web Interface)

```bash
python manage.py runserver
# Navigate to http://localhost:8000/matches/
```

## Usage

### Import Data from SofaScore

**Full import (teams, matches, players, stats):**
```bash
python manage.py import_sofascore_complete \
    --competitions PL,CL \
    --seasons 2024 \
    --all-data
```

**What `--all-data` imports:**
- ✅ Teams (with manager info)
- ✅ Matches (finished and scheduled)
- ✅ Match statistics (shots, corners, possession, xG, fouls, cards)
- ✅ Match lineups (starting XI and substitutes)
- ✅ Player statistics per match (goals, assists, rating, passes, tackles, duels)
- ✅ Match incidents (goals, cards, substitutions, VAR decisions)
- ✅ Advanced match data (momentum graph, shotmap, best players)
- ✅ Players with season statistics
- ✅ Team standings/classification

**Import specific modules:**
```bash
# Teams only
python manage.py import_sofascore_complete --competitions PL --seasons 2024 --teams-only

# Matches with all statistics, lineups, and incidents
python manage.py import_sofascore_complete --competitions PL --seasons 2024 --matches-only

# Players with season statistics
python manage.py import_sofascore_complete --competitions PL --seasons 2024 --players-only

# Team standings/classification
python manage.py import_sofascore_complete --competitions PL --seasons 2024 --standings-only

# Player injuries (current injury status)
python manage.py import_sofascore_complete --competitions PL --seasons 2024 --injuries-only

# Dry-run (preview without saving)
python manage.py import_sofascore_complete --competitions PL --seasons 2024 --all-data --dry-run

# Force re-import (overwrite existing data)
python manage.py import_sofascore_complete --competitions PL --seasons 2024 --all-data --force
```

**Available flags:**
- `--all-data`: Import everything (teams, matches, match stats, lineups, incidents, players, standings)
- `--teams-only`: Only import teams
- `--matches-only`: Only import matches with statistics, lineups, and incidents
- `--players-only`: Only import players with season statistics
- `--standings-only`: Only import team standings
- `--injuries-only`: Only import player injuries
- `--force`: Force re-import even if data already exists
- `--dry-run`: Preview what would be imported without saving

### Re-import Specific Matchdays or Full Seasons

If data import failed or you need to update specific matchdays:

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
- ✅ Lineups and player statistics
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

### Value Bet Analysis

Requires `API_KEY_ODDS` environment variable.

```bash
# Basic analysis
python manage.py get_odds --days 7 --competitions PL,PD

# With custom parameters
python manage.py get_odds \
    --days 7 \
    --competitions PL,PD \
    --bankroll 2000 \
    --kelly 0.33 \
    --min-edge 0.05
```

**Parameters:**
- `--bankroll`: Bankroll for stake calculations (default: 1000)
- `--kelly`: Kelly fraction for stake sizing (default: 0.25)
- `--min-edge`: Minimum edge threshold (default: 0.03 = 3%)

## Competition Codes

| Code | League |
|------|--------|
| PL | Premier League (England) |
| PD | La Liga (Spain) |
| BL1 | Bundesliga (Germany) |
| SA | Serie A (Italy) |
| FL1 | Ligue 1 (France) |
| CL | Champions League |

## Data Sources

### SofaScore API (Primary)
- Comprehensive data for all major leagues
- Teams, matches, players, statistics
- Match statistics: corners, shots, xG, possession
- May be rate-limited (403 errors)

### Football-Data.co.uk (Secondary)
- Historical CSV data (2015-2024)
- No rate limiting
- Includes betting odds from 10+ bookmakers

### The Odds API
- Live betting odds
- Used for value bet analysis
- Requires API key

## Architecture

### Django Models

- **Competition**: League/tournament information
- **Team**: Team data with global deduplication
- **Match**: Historical and scheduled matches
- **Player**: Player information and statistics
- **TeamStats**: Calculated statistics per team/season
- **HeadToHead**: Direct matchup history
- **Prediction**: ML model predictions

### Machine Learning Pipeline

1. **Data Import**: SofaScore API or Football-Data CSVs
2. **Feature Engineering**: 33 features including form, H2H, xG metrics
3. **Model Training**: Random Forest, XGBoost, LightGBM with calibration
4. **Prediction**: Ensemble method combining ML + Dixon-Coles
5. **Value Analysis**: Compare predictions vs bookmaker odds

### Key Components

- `predictions/ml/predictor.py`: ML model training and prediction
- `predictions/ml/enhanced_features.py`: Feature engineering (33 features)
- `predictions/ml/ensemble.py`: Ensemble prediction combining models
- `predictions/sofascore_api.py`: SofaScore API client
- `predictions/scrapers/`: Web scrapers for additional data

## Development

### Management Commands

Located in `predictions/management/commands/`:

**Data Import:**
- `import_sofascore_complete.py` - Unified SofaScore import (teams, matches, stats, lineups, players)
- `reimport_matchday.py` - Re-import specific matchdays (when data import failed)
- `import_leagues.py` - Import Football-Data CSVs
- `import_fixtures.py` - Import upcoming fixtures
- `import_transfermarkt.py` - Import market values
- `download_images.py` - Download team logos and player photos

**Statistics:**
- `calculate_stats.py` - Calculate all statistics
- `calculate_team_stats.py` - Team statistics by season
- `calculate_head_to_head.py` - H2H records

**Machine Learning:**
- `train_models.py` - Train prediction models
- `predict.py` - Generate predictions
- `get_odds.py` - Value bet analysis

**Utilities:**
- `consolidate_teams.py` - Merge duplicate teams (exact name matching)
- `consolidate_teams_fuzzy.py` - Merge duplicate teams (fuzzy name matching)
- `cleanup_duplicate_matches.py` - Remove duplicate matches (keeps api_id version)
- `check_db_data.py` - Database diagnostics

### Weekly Workflow

```bash
# 1. Import new matches
python manage.py import_sofascore_complete --competitions PL,PD,BL1,SA,FL1 --seasons 2025 --matches-only

# 2. Update statistics
python manage.py calculate_stats --competitions PL,PD,BL1,SA,FL1

# 3. Generate predictions
python manage.py predict --days 7 --competitions PL,PD,BL1,SA,FL1

# 4. Analyze value bets
python manage.py get_odds --days 7 --competitions PL,PD,BL1,SA,FL1 --min-edge 0.03
```

## Web Interface

Access the web interface at `http://localhost:8000/matches/`

**Features:**
- Filter by competition, season, and match status
- View match statistics (shots, corners, xG, possession)
- Responsive design for mobile and desktop

## Troubleshooting

### SofaScore 403 Errors

If you encounter rate limiting:
- Wait 10-15 minutes between imports
- Import one competition at a time
- Use `--dry-run` to test before actual import

### Duplicate Teams

If you see duplicate teams (same team across competitions):
```bash
python manage.py consolidate_teams --dry-run  # Preview
python manage.py consolidate_teams  # Execute merge
```

### Model Accuracy Issues

For better predictions:
- Ensure sufficient training data (at least 3 seasons)
- Include multiple competitions for diversity
- Retrain models quarterly with updated data
- Use ensemble predictions (combines ML + Poisson)

## Performance

- **Model training**: ~5 minutes (8,637 matches)
- **SofaScore import**: ~2-3 minutes per competition/season
- **CSV import**: ~10 minutes for 10 years of data
- **Predictions**: Seconds for 7 days of matches
- **Statistics calculation**: 5-10 minutes for all competitions

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write tests if applicable
5. Submit a pull request

## License

[Add your license here]

## Credits

- **Data Sources**: SofaScore, Football-Data.co.uk, The Odds API
- **ML Libraries**: scikit-learn, XGBoost, LightGBM
- **Web Framework**: Django 5.1+
- **Automation**: Playwright for web scraping

## Support

For issues and questions:
- Check the `CLAUDE.md` file for detailed documentation
- Review existing GitHub issues
- Create a new issue with detailed description

---

Built with Django and Machine Learning for football prediction enthusiasts.
