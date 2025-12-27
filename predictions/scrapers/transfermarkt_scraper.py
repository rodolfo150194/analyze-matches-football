"""
Transfermarkt Scraper - Scrapes squad valuations and transfer data

Transfermarkt provides:
- Team market values (total squad value, average player value)
- Individual player valuations
- Transfer activity (income, expenditure, net spend)
- Squad composition (size, average age, foreigners)

Note: Transfermarkt has stricter rate limiting than other sites.
Use conservative delays (4-7 seconds).

Usage:
    from predictions.scrapers.transfermarkt_scraper import TransfermarktScraper

    scraper = TransfermarktScraper()

    # Get league market values
    teams = scraper.get_league_market_values('PL', 2024)

    # Get individual player values
    players = scraper.get_team_squad_values(team_id)
"""

import requests
import re
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from .utils import (
    RateLimiter, get_browser_headers,
    parse_transfermarkt_value, safe_int, safe_float
)


# Transfermarkt league code mapping
TRANSFERMARKT_LEAGUE_CODES = {
    'PL': 'GB1',     # Premier League
    'PD': 'ES1',     # La Liga
    'BL1': 'L1',     # Bundesliga
    'SA': 'IT1',     # Serie A
    'FL1': 'FR1',    # Ligue 1
    'CL': 'CL',      # Champions League
}

# Transfermarkt league names (for URL construction)
TRANSFERMARKT_LEAGUE_NAMES = {
    'PL': 'premier-league',
    'PD': 'laliga',
    'BL1': 'bundesliga',
    'SA': 'serie-a',
    'FL1': 'ligue-1',
    'CL': 'champions-league',
}


class TransfermarktScraper:
    """
    Scraper for Transfermarkt.com market values and transfer data

    Rate limiting: 4-7 seconds between requests (stricter than FBRef)
    """

    BASE_URL = "https://www.transfermarkt.com"
    BASE_URL_US = "https://www.transfermarkt.us"  # Fallback

    def __init__(self, delay_min=4, delay_max=7, use_us_domain=False):
        """
        Initialize Transfermarkt scraper

        Args:
            delay_min: Minimum delay between requests (seconds)
            delay_max: Maximum delay between requests (seconds)
            use_us_domain: Use .us domain instead of .com
        """
        self.rate_limiter = RateLimiter(delay_min, delay_max)
        self.headers = get_browser_headers()
        self.headers['Referer'] = 'https://www.transfermarkt.com/'

        # Use US domain if specified (sometimes less strict)
        if use_us_domain:
            self.base_url = self.BASE_URL_US
        else:
            self.base_url = self.BASE_URL

    def _make_request(self, url: str, max_retries: int = 3) -> Optional[BeautifulSoup]:
        """
        Make HTTP request with rate limiting and retry logic

        Args:
            url: URL to fetch
            max_retries: Maximum number of retries

        Returns:
            BeautifulSoup object or None on failure
        """
        for attempt in range(max_retries):
            try:
                self.rate_limiter.wait()

                response = requests.get(url, headers=self.headers, timeout=30)

                if response.status_code == 429:
                    print("[WARNING] Rate limited by Transfermarkt")
                    if self.rate_limiter.wait_on_429(max_retries):
                        continue
                    else:
                        print("Max retries exceeded")
                        return None

                # Transfermarkt sometimes returns 403 for bots
                if response.status_code == 403:
                    print("[WARNING] Blocked by Transfermarkt (403)")
                    return None

                response.raise_for_status()
                self.rate_limiter.reset_retry_count()

                return BeautifulSoup(response.content, 'html.parser')

            except requests.exceptions.RequestException as e:
                print(f"Request error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)
                else:
                    return None

        return None

    def get_league_market_values(self, league_code: str, season: int) -> List[Dict]:
        """
        Scrape market values for all teams in a league

        URL format: https://www.transfermarkt.com/premier-league/startseite/wettbewerb/GB1/plus/?saison_id=2024

        Args:
            league_code: League code (PL, PD, BL1, SA, FL1)
            season: Season year (2024 for 2024-2025)

        Returns:
            List of dicts with team market values
        """
        tm_code = TRANSFERMARKT_LEAGUE_CODES.get(league_code)
        league_name = TRANSFERMARKT_LEAGUE_NAMES.get(league_code)

        if not tm_code or not league_name:
            print(f"Unknown league code: {league_code}")
            return []

        url = f"{self.base_url}/{league_name}/startseite/wettbewerb/{tm_code}/plus/?saison_id={season}"

        print(f"Fetching market values from: {url}")
        soup = self._make_request(url)

        if not soup:
            return []

        return self._parse_league_table(soup)

    def _parse_league_table(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Parse Transfermarkt league table with market values

        Args:
            soup: BeautifulSoup object

        Returns:
            List of team dicts with market values
        """
        teams_data = []

        # Find the main table (responsive-table class)
        table = soup.find('table', {'class': 'items'})

        if not table:
            print("Market value table not found")
            return []

        tbody = table.find('tbody')
        if not tbody:
            return []

        for row in tbody.find_all('tr'):
            # Skip header rows
            if row.find('th'):
                continue

            cells = row.find_all('td')

            if len(cells) < 5:
                continue

            team_dict = {}

            # Team name is in cell with class 'hauptlink' (usually cell 1)
            team_cell = None
            for cell in cells:
                if 'hauptlink' in cell.get('class', []):
                    team_cell = cell
                    break

            if not team_cell:
                continue

            team_link = team_cell.find('a')
            if team_link:
                team_dict['team_name'] = team_link.text.strip()
                team_dict['team_url'] = team_link.get('href', '')
                team_dict['team_id'] = self._extract_team_id_from_url(team_dict['team_url'])

            # Based on actual structure:
            # Cell 0: Logo, Cell 1: Team name, Cell 2: Squad size, Cell 3: Avg age
            # Cell 4: Foreigners, Cell 5: Avg player value, Cell 6: Total value

            # Squad size (cell 2)
            if len(cells) > 2:
                team_dict['squad_size'] = safe_int(cells[2].text.strip())

            # Average age (cell 3)
            if len(cells) > 3:
                team_dict['avg_age'] = safe_float(cells[3].text.strip())

            # Foreigners (cell 4)
            if len(cells) > 4:
                team_dict['foreigners_count'] = safe_int(cells[4].text.strip())

            # Total market value (cell 6, last cell)
            if len(cells) > 6:
                value_text = cells[6].text.strip()
                team_dict['total_market_value_eur'] = parse_transfermarkt_value(value_text)

            # Calculate average player value
            if team_dict.get('total_market_value_eur') and team_dict.get('squad_size'):
                team_dict['avg_player_value_eur'] = int(
                    team_dict['total_market_value_eur'] / team_dict['squad_size']
                )

            if team_dict:
                teams_data.append(team_dict)

        return teams_data

    def get_team_squad_values(self, team_id: str, season: Optional[int] = None) -> List[Dict]:
        """
        Scrape individual player market values for a team

        URL format: https://www.transfermarkt.com/arsenal/kader/verein/11/saison_id/2024

        Args:
            team_id: Transfermarkt team ID (e.g., "11" for Arsenal)
            season: Optional season year

        Returns:
            List of dicts with player valuations
        """
        url = f"{self.base_url}/x/kader/verein/{team_id}"

        if season:
            url += f"/saison_id/{season}"

        print(f"Fetching squad values from: {url}")
        soup = self._make_request(url)

        if not soup:
            return []

        return self._parse_squad_table(soup)

    def _parse_squad_table(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Parse Transfermarkt squad table with player values

        Args:
            soup: BeautifulSoup object

        Returns:
            List of player dicts
        """
        players_data = []

        # Find squad table
        table = soup.find('table', {'class': 'items'})

        if not table:
            print("Squad table not found")
            return []

        tbody = table.find('tbody')
        if not tbody:
            return []

        for row in tbody.find_all('tr', {'class': ['odd', 'even']}):
            cells = row.find_all('td')

            if len(cells) < 7:
                continue

            player_dict = {}

            # Player number
            number_cell = cells[0]
            player_dict['shirt_number'] = safe_int(number_cell.text.strip())

            # Player name (with link)
            name_cell = cells[1]
            player_link = name_cell.find('a', {'class': 'spielprofil_tooltip'})
            if player_link:
                player_dict['player_name'] = player_link.text.strip()
                player_dict['player_url'] = player_link.get('href', '')
                player_dict['player_id'] = self._extract_player_id_from_url(player_dict['player_url'])

            # Position
            position_cell = cells[2]
            player_dict['position'] = position_cell.text.strip()

            # Date of birth / Age
            age_cell = cells[3]
            age_text = age_cell.text.strip()
            # Format: "Jan 1, 2000 (24)"
            if '(' in age_text:
                try:
                    age = int(age_text.split('(')[1].split(')')[0])
                    player_dict['age'] = age
                except:
                    pass

            # Nationality
            nationality_cell = cells[4]
            img = nationality_cell.find('img')
            if img:
                player_dict['nationality'] = img.get('alt', '').strip()

            # Market value (last cell or second-to-last)
            value_cell = cells[-1]
            value_text = value_cell.text.strip()
            player_dict['market_value_eur'] = parse_transfermarkt_value(value_text)

            if player_dict:
                players_data.append(player_dict)

        return players_data

    def get_team_transfers(self, team_id: str, season: int) -> Dict:
        """
        Scrape transfer activity for a team (income, expenditure)

        URL format: https://www.transfermarkt.com/arsenal/transfers/verein/11/saison_id/2024

        Args:
            team_id: Transfermarkt team ID
            season: Season year

        Returns:
            Dict with transfer_income_eur, transfer_expenditure_eur, net_transfer_eur
        """
        url = f"{self.base_url}/x/transfers/verein/{team_id}/saison_id/{season}"

        print(f"Fetching transfers from: {url}")
        soup = self._make_request(url)

        if not soup:
            return {}

        return self._parse_transfers_page(soup)

    def _parse_transfers_page(self, soup: BeautifulSoup) -> Dict:
        """
        Parse Transfermarkt transfers page to extract income/expenditure

        Args:
            soup: BeautifulSoup object

        Returns:
            Dict with transfer financial data
        """
        transfer_data = {
            'transfer_income_eur': 0,
            'transfer_expenditure_eur': 0,
            'net_transfer_eur': 0,
        }

        # Look for transfer summary box
        summary_box = soup.find('div', {'class': 'large-8'})

        if not summary_box:
            return transfer_data

        # Find income and expenditure values
        # Transfermarkt shows these in a specific format
        summary_text = summary_box.get_text()

        # Try to extract income (Einnahmen / Income)
        income_match = re.search(r'Income[:\s]+([€\d,\.]+\s*(?:m|Mio\.|k|Th\.))', summary_text, re.IGNORECASE)
        if income_match:
            transfer_data['transfer_income_eur'] = parse_transfermarkt_value(income_match.group(1))

        # Try to extract expenditure (Ausgaben / Expenditure)
        expenditure_match = re.search(r'Expenditure[:\s]+([€\d,\.]+\s*(?:m|Mio\.|k|Th\.))', summary_text, re.IGNORECASE)
        if expenditure_match:
            transfer_data['transfer_expenditure_eur'] = parse_transfermarkt_value(expenditure_match.group(1))

        # Calculate net transfer
        transfer_data['net_transfer_eur'] = (
            transfer_data['transfer_expenditure_eur'] - transfer_data['transfer_income_eur']
        )

        return transfer_data

    def _extract_team_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract Transfermarkt team ID from URL

        Args:
            url: URL like "/arsenal/startseite/verein/11"

        Returns:
            Team ID (e.g., "11") or None
        """
        if not url:
            return None

        match = re.search(r'/verein/(\d+)', url)
        if match:
            return match.group(1)

        return None

    def _extract_player_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract Transfermarkt player ID from URL

        Args:
            url: URL like "/bukayo-saka/profil/spieler/433177"

        Returns:
            Player ID (e.g., "433177") or None
        """
        if not url:
            return None

        match = re.search(r'/spieler/(\d+)', url)
        if match:
            return match.group(1)

        return None


# Convenience function for testing
if __name__ == '__main__':
    scraper = TransfermarktScraper()

    # Test: Get Premier League market values for 2024-2025
    print("\n" + "="*70)
    print("Testing TransfermarktScraper - Premier League Market Values 2024")
    print("="*70 + "\n")

    teams = scraper.get_league_market_values('PL', 2024)

    if teams:
        print(f"Found {len(teams)} teams")
        print("\nFirst 3 teams:")
        for team in teams[:3]:
            value_m = team.get('total_market_value_eur', 0) / 1_000_000
            print(f"  {team.get('team_name')}: €{value_m:.1f}M")
    else:
        print("No data retrieved")
