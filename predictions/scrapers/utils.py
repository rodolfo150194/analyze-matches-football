"""
Utilidades para web scraping y fuzzy matching
Usado por todos los scrapers e import commands
"""

import time
import random
from thefuzz import process, fuzz
from predictions.models import Team, Player


# ============================================================================
# TEAM NAME OVERRIDES - Manual mapping para casos problemáticos
# ============================================================================

TEAM_NAME_OVERRIDES = {
    # Premier League - Football-Data.co.uk uses abbreviated names
    # Transfermarkt -> Database mapping
    'Manchester City': 'Man City',
    'Manchester United': 'Man United',
    'Tottenham Hotspur': 'Tottenham',
    'Wolverhampton Wanderers': 'Wolves',
    'Newcastle United': 'Newcastle',
    'Brighton & Hove Albion': 'Brighton',
    'West Ham United': 'West Ham',
    'Nottingham Forest': "Nott'm Forest",
    'AFC Bournemouth': 'Bournemouth',
    'Ipswich Town': 'Ipswich',

    # Reverse mappings (in case scrapers use abbreviated names)
    'Man United': 'Man United',
    'Man City': 'Man City',
    'Spurs': 'Tottenham',
    'Wolves': 'Wolves',
    'Newcastle': 'Newcastle',
    'Brighton': 'Brighton',
    'West Ham': 'West Ham',
    'Nott\'m Forest': "Nott'm Forest",

    # La Liga
    'Atlético Madrid': 'Atletico Madrid',
    'Atlético de Madrid': 'Atletico Madrid',
    'Athletic Club': 'Athletic Bilbao',
    'Athletic Bilbao': 'Athletic Bilbao',
    'Betis': 'Real Betis',
    'Sociedad': 'Real Sociedad',

    # Bundesliga
    'Bayern München': 'Bayern Munich',
    'Bayern Munich': 'Bayern Munich',
    'Bor. Mönchengladbach': 'Borussia Monchengladbach',
    'Gladbach': 'Borussia Monchengladbach',
    'Dortmund': 'Borussia Dortmund',
    'Leverkusen': 'Bayer Leverkusen',

    # Serie A
    'Milan': 'AC Milan',
    'Inter': 'Inter Milan',
    'Roma': 'AS Roma',
    'Atalanta': 'Atalanta BC',
    'Napoli': 'SSC Napoli',

    # Ligue 1
    'PSG': 'Paris Saint-Germain',
    'Paris SG': 'Paris Saint-Germain',
    'Saint-Étienne': 'Saint-Etienne',
}


# ============================================================================
# PLAYER NAME OVERRIDES - Manual mapping para jugadores
# ============================================================================

PLAYER_NAME_OVERRIDES = {
    'Bruno Fernandes': 'Bruno Miguel Borges Fernandes',
    'Diogo Jota': 'José Diogo Dalot Teixeira',
    'Ederson': 'Ederson Santana de Moraes',
    'Gabriel Jesus': 'Gabriel Fernando de Jesus',
    'Alex Iwobi': 'Alexander Chuka Iwobi',
    'Pep Guardiola': 'Josep Guardiola Sala',
}


# ============================================================================
# FUZZY MATCHING FUNCTIONS
# ============================================================================

def fuzzy_match_team(scraped_name: str, existing_teams, threshold: int = 80):
    """
    Match scraped team name to existing Team record using fuzzy matching

    Args:
        scraped_name: Team name from scraper
        existing_teams: QuerySet or list of Team objects
        threshold: Minimum similarity score (0-100)

    Returns:
        tuple: (Team object, score) or (None, 0) if no match

    Example:
        >>> teams = Team.objects.filter(competition__code='PL')
        >>> team, score = fuzzy_match_team('Man United', teams)
        >>> print(f"{team.name} ({score}%)")
        Manchester United (95%)
    """
    # Check override first
    if scraped_name in TEAM_NAME_OVERRIDES:
        override_name = TEAM_NAME_OVERRIDES[scraped_name]
        # Try exact match with override
        for team in existing_teams:
            if team.name == override_name:
                return team, 100

    # Build mapping of team names to IDs
    team_names = {team.id: team.name for team in existing_teams}

    if not team_names:
        return None, 0

    # Fuzzy match
    result = process.extractOne(
        scraped_name,
        team_names.values(),
        scorer=fuzz.token_sort_ratio,
        score_cutoff=threshold
    )

    if result:
        matched_name, score = result[0], result[1]
        # Find team ID for matched name
        team_id = [k for k, v in team_names.items() if v == matched_name][0]

        # Get Team object
        for team in existing_teams:
            if team.id == team_id:
                return team, score

    return None, 0


def fuzzy_match_player(scraped_name: str, existing_players, threshold: int = 85):
    """
    Match scraped player name to existing Player record using fuzzy matching

    Args:
        scraped_name: Player name from scraper
        existing_players: QuerySet or list of Player objects
        threshold: Minimum similarity score (0-100, higher for players)

    Returns:
        tuple: (Player object, score) or (None, 0) if no match

    Example:
        >>> players = Player.objects.filter(team__name='Arsenal')
        >>> player, score = fuzzy_match_player('Bruno Fernandes', players)
    """
    # Check override first
    if scraped_name in PLAYER_NAME_OVERRIDES:
        override_name = PLAYER_NAME_OVERRIDES[scraped_name]
        # Try exact match with override
        for player in existing_players:
            if player.name == override_name:
                return player, 100

    # Build mapping
    player_names = {player.id: player.name for player in existing_players}

    if not player_names:
        return None, 0

    # Try exact match on short_name too
    for player in existing_players:
        if player.short_name and player.short_name.lower() == scraped_name.lower():
            return player, 100

    # Fuzzy match
    result = process.extractOne(
        scraped_name,
        player_names.values(),
        scorer=fuzz.token_sort_ratio,
        score_cutoff=threshold
    )

    if result:
        matched_name, score = result[0], result[1]
        player_id = [k for k, v in player_names.items() if v == matched_name][0]

        for player in existing_players:
            if player.id == player_id:
                return player, score

    return None, 0


def normalize_team_name(name: str) -> str:
    """
    Normalize team name for better matching

    Args:
        name: Raw team name

    Returns:
        Normalized team name

    Example:
        >>> normalize_team_name("  Man. United  ")
        'Manchester United'
    """
    # Strip whitespace
    name = name.strip()

    # Apply override if exists
    if name in TEAM_NAME_OVERRIDES:
        return TEAM_NAME_OVERRIDES[name]

    # Remove common suffixes
    suffixes = [' FC', ' CF', ' SC', ' AFC', ' United FC']
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]

    return name.strip()


def normalize_player_name(name: str) -> str:
    """
    Normalize player name for better matching

    Args:
        name: Raw player name

    Returns:
        Normalized player name
    """
    # Strip whitespace
    name = name.strip()

    # Apply override if exists
    if name in PLAYER_NAME_OVERRIDES:
        return PLAYER_NAME_OVERRIDES[name]

    # Remove accents and special characters (optional)
    # For now, keep as-is to preserve player names authenticity

    return name


# ============================================================================
# RATE LIMITING DECORATORS AND UTILITIES
# ============================================================================

class RateLimiter:
    """
    Rate limiter for web scraping with exponential backoff

    Usage:
        limiter = RateLimiter(delay_min=3, delay_max=6)
        limiter.wait()
    """

    def __init__(self, delay_min=3, delay_max=6):
        """
        Args:
            delay_min: Minimum delay in seconds
            delay_max: Maximum delay in seconds
        """
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.last_request_time = 0
        self.retry_count = 0

    def wait(self):
        """Wait if needed based on last request time"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time

        if elapsed < self.delay_min:
            delay = random.uniform(self.delay_min, self.delay_max)
            time.sleep(delay)

        self.last_request_time = time.time()

    def wait_on_429(self, max_retries=3):
        """
        Exponential backoff on 429 (rate limit) errors

        Args:
            max_retries: Maximum number of retries

        Returns:
            bool: True if should retry, False if max retries exceeded
        """
        if self.retry_count >= max_retries:
            self.retry_count = 0
            return False

        # Exponential backoff: 2^retry * delay_min
        wait_time = (2 ** self.retry_count) * self.delay_min
        wait_time = min(wait_time, 60)  # Max 60 seconds

        print(f"Rate limited. Waiting {wait_time}s before retry ({self.retry_count + 1}/{max_retries})...")
        time.sleep(wait_time)

        self.retry_count += 1
        return True

    def reset_retry_count(self):
        """Reset retry counter after successful request"""
        self.retry_count = 0


def get_browser_headers():
    """
    Get realistic browser headers to avoid blocking

    Returns:
        dict: Headers for requests
    """
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
    }


# ============================================================================
# DATA PARSING UTILITIES
# ============================================================================

def parse_transfermarkt_value(value_str: str) -> int:
    """
    Parse Transfermarkt market value string to integer EUR

    Args:
        value_str: Value string like "€45.5m" or "45,5 Mio. €"

    Returns:
        int: Value in EUR

    Examples:
        >>> parse_transfermarkt_value("€45.5m")
        45500000
        >>> parse_transfermarkt_value("1,2 Mio. €")
        1200000
        >>> parse_transfermarkt_value("500Th. €")
        500000
    """
    if not value_str or value_str == '-':
        return 0

    # Remove € symbol and whitespace
    value_str = value_str.replace('€', '').replace(' ', '').strip()

    # Handle different formats
    multiplier = 1

    # German format: "45,5 Mio."
    if 'Mrd.' in value_str:  # German billions
        multiplier = 1_000_000_000
        value_str = value_str.replace('Mrd.', '')
    elif 'Mio.' in value_str or 'Mio' in value_str:
        multiplier = 1_000_000
        value_str = value_str.replace('Mio.', '').replace('Mio', '')
    elif 'Th.' in value_str or 'Th' in value_str:
        multiplier = 1_000
        value_str = value_str.replace('Th.', '').replace('Th', '')
    # English format: "45.5m" or "1.36bn"
    elif value_str.endswith('bn') or value_str.endswith('BN'):
        multiplier = 1_000_000_000
        value_str = value_str[:-2]
    elif value_str.endswith('m') or value_str.endswith('M'):
        multiplier = 1_000_000
        value_str = value_str[:-1]
    elif value_str.endswith('k') or value_str.endswith('K'):
        multiplier = 1_000
        value_str = value_str[:-1]

    # Replace German decimal comma with dot
    value_str = value_str.replace(',', '.')

    try:
        value = float(value_str) * multiplier
        return int(value)
    except ValueError:
        return 0


def safe_float(value, default=0.0):
    """Safely convert value to float, return default on error"""
    try:
        if value is None or value == '' or value == '-':
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default=0):
    """Safely convert value to int, return default on error"""
    try:
        if value is None or value == '' or value == '-':
            return default
        return int(float(value))  # Handle "1.0" -> 1
    except (ValueError, TypeError):
        return default


# ============================================================================
# VALIDATION UTILITIES
# ============================================================================

def validate_xg(xg_value):
    """
    Validate xG value is within reasonable range

    Args:
        xg_value: xG value to validate

    Returns:
        float: Validated xG or None if invalid
    """
    try:
        xg = float(xg_value)
        # xG should be between 0 and 1 for a single shot
        # Team xG can be higher
        if 0 <= xg <= 10:  # Reasonable upper limit for team xG
            return xg
        return None
    except (ValueError, TypeError):
        return None


def validate_percentage(pct_value):
    """
    Validate percentage value is within 0-100 range

    Args:
        pct_value: Percentage value to validate

    Returns:
        float: Validated percentage or None if invalid
    """
    try:
        pct = float(pct_value)
        if 0 <= pct <= 100:
            return pct
        return None
    except (ValueError, TypeError):
        return None
