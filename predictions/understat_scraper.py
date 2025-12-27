"""
Understat.com Scraper para Expected Goals (xG)
Scraping de datos xG históricos usando BeautifulSoup y requests
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
import time
import random


class UnderstatScraper:
    def __init__(self, delay_min=2, delay_max=4):
        self.base_url = "https://understat.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.last_request_time = 0

        # Mapeo de ligas
        self.LEAGUE_MAP = {
            'PL': 'EPL',  # Premier League
            'PD': 'La_Liga',  # La Liga
            'BL1': 'Bundesliga',  # Bundesliga
            'SA': 'Serie_A',  # Serie A
            'FL1': 'Ligue_1',  # Ligue 1
            # UCL no está en Understat free
        }

    def _wait_if_needed(self):
        """Rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.delay_min:
            delay = random.uniform(self.delay_min, self.delay_max)
            time.sleep(delay)

        self.last_request_time = time.time()

    def _extract_json_from_script(self, html, variable_name):
        """
        Understat embebe los datos en variables JavaScript
        Extraerlos parseando el HTML
        """
        soup = BeautifulSoup(html, 'html.parser')
        scripts = soup.find_all('script')

        for script in scripts:
            if script.string and variable_name in script.string:
                # Buscar patrón: var variable_name = JSON.parse('...')
                pattern = rf"var {variable_name}\s*=\s*JSON\.parse\('(.+?)'\)"
                match = re.search(pattern, script.string)

                if match:
                    json_str = match.group(1)
                    # Decodificar caracteres escapados
                    json_str = json_str.encode().decode('unicode_escape')
                    return json.loads(json_str)

        return None

    # ============================================================================
    # MÉTODOS DE SCRAPING
    # ============================================================================

    def get_league_matches(self, league_code, season):
        """
        Obtener todos los partidos de una liga en una temporada

        Args:
            league_code: 'PL', 'PD', 'BL1', 'SA', 'FL1'
            season: 2024, 2023, etc.

        Returns:
            Lista de partidos con datos xG
        """
        if league_code not in self.LEAGUE_MAP:
            raise ValueError(f"Liga {league_code} no soportada en Understat")

        understat_league = self.LEAGUE_MAP[league_code]
        url = f"{self.base_url}/league/{understat_league}/{season}"

        self._wait_if_needed()

        print(f"[Understat] Scraping {understat_league} {season}: {url}")

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Extraer datos de partidos del script JavaScript
            matches_data = self._extract_json_from_script(response.text, 'datesData')

            if not matches_data:
                print(f"[Warning] No se encontraron datos de partidos")
                return []

            # Parsear partidos
            matches = []
            for date, date_matches in matches_data.items():
                for match in date_matches:
                    match_info = {
                        'match_id': match.get('id'),
                        'date': match.get('datetime'),
                        'home_team': match.get('h', {}).get('title'),
                        'away_team': match.get('a', {}).get('title'),
                        'home_goals': match.get('goals', {}).get('h'),
                        'away_goals': match.get('goals', {}).get('a'),
                        'home_xg': float(match.get('xG', {}).get('h', 0)),
                        'away_xg': float(match.get('xG', {}).get('a', 0)),
                        'forecast_home': match.get('forecast', {}).get('w'),  # Prob win home
                        'forecast_draw': match.get('forecast', {}).get('d'),  # Prob draw
                        'forecast_away': match.get('forecast', {}).get('l'),  # Prob loss (win away)
                    }
                    matches.append(match_info)

            print(f"[Understat] {len(matches)} partidos encontrados")
            return matches

        except requests.RequestException as e:
            print(f"[Error] Request failed: {e}")
            return []
        except Exception as e:
            print(f"[Error] Parsing failed: {e}")
            return []

    def get_match_details(self, match_id):
        """
        Obtener detalles de un partido específico
        Incluye xG por jugador y shots
        """
        url = f"{self.base_url}/match/{match_id}"

        self._wait_if_needed()

        print(f"[Understat] Scraping match {match_id}: {url}")

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Extraer shots data
            shots_data = self._extract_json_from_script(response.text, 'shotsData')

            # Extraer roster data (jugadores)
            roster_data = self._extract_json_from_script(response.text, 'rostersData')

            match_info = {
                'match_id': match_id,
                'url': url,
                'shots': shots_data,
                'rosters': roster_data,
                'timestamp': datetime.now().isoformat()
            }

            # Calcular xG total desde shots
            if shots_data:
                home_xg = sum(float(shot['xG']) for shot in shots_data.get('h', []))
                away_xg = sum(float(shot['xG']) for shot in shots_data.get('a', []))

                match_info['home_xg_calculated'] = round(home_xg, 2)
                match_info['away_xg_calculated'] = round(away_xg, 2)
                match_info['total_shots_home'] = len(shots_data.get('h', []))
                match_info['total_shots_away'] = len(shots_data.get('a', []))

            return match_info

        except Exception as e:
            print(f"[Error] Scraping match failed: {e}")
            return None

    def get_team_matches(self, team_name, season):
        """
        Obtener todos los partidos de un equipo en una temporada

        Args:
            team_name: 'Arsenal', 'Liverpool', etc. (nombre como aparece en Understat)
            season: 2024, 2023, etc.

        Returns:
            Lista de partidos del equipo
        """
        url = f"{self.base_url}/team/{team_name}/{season}"

        self._wait_if_needed()

        print(f"[Understat] Scraping {team_name} {season}: {url}")

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Extraer datos de partidos
            matches_data = self._extract_json_from_script(response.text, 'datesData')

            if not matches_data:
                return []

            matches = []
            for date, date_matches in matches_data.items():
                for match in date_matches:
                    match_info = {
                        'match_id': match.get('id'),
                        'date': match.get('datetime'),
                        'home_team': match.get('h', {}).get('title'),
                        'away_team': match.get('a', {}).get('title'),
                        'home_goals': match.get('goals', {}).get('h'),
                        'away_goals': match.get('goals', {}).get('a'),
                        'home_xg': float(match.get('xG', {}).get('h', 0)),
                        'away_xg': float(match.get('xG', {}).get('a', 0)),
                        'is_home': match.get('h', {}).get('title') == team_name,
                    }
                    matches.append(match_info)

            print(f"[Understat] {len(matches)} partidos encontrados para {team_name}")
            return matches

        except Exception as e:
            print(f"[Error] Scraping team failed: {e}")
            return []

    def get_player_stats(self, player_id, season):
        """
        Obtener estadísticas de un jugador
        """
        url = f"{self.base_url}/player/{player_id}"

        self._wait_if_needed()

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Extraer datos del jugador
            player_data = self._extract_json_from_script(response.text, 'statisticsData')

            return player_data

        except Exception as e:
            print(f"[Error] Scraping player failed: {e}")
            return None

    # ============================================================================
    # UTILIDADES
    # ============================================================================

    def map_team_name(self, django_team_name):
        """
        Mapear nombre de equipo de Django a nombre de Understat
        Understat usa nombres sin espacios y con guiones bajos
        """
        # Mapeo manual de equipos comunes
        TEAM_NAME_MAP = {
            'Man United': 'Manchester_United',
            'Manchester United': 'Manchester_United',
            'Man City': 'Manchester_City',
            'Manchester City': 'Manchester_City',
            'Tottenham': 'Tottenham',
            'Arsenal': 'Arsenal',
            'Liverpool': 'Liverpool',
            'Chelsea': 'Chelsea',
            'Newcastle': 'Newcastle_United',
            'Brighton': 'Brighton',
            'Aston Villa': 'Aston_Villa',
            'West Ham': 'West_Ham',
            'Wolves': 'Wolverhampton_Wanderers',
            'Everton': 'Everton',
            'Leicester': 'Leicester',
            'Crystal Palace': 'Crystal_Palace',
            'Fulham': 'Fulham',
            'Brentford': 'Brentford',
            'Nottingham Forest': 'Nottingham_Forest',
            'Bournemouth': 'Bournemouth',
            'Ipswich': 'Ipswich',
            'Southampton': 'Southampton',
            # La Liga
            'Barcelona': 'Barcelona',
            'Real Madrid': 'Real_Madrid',
            'Atletico Madrid': 'Atletico_Madrid',
            'Sevilla': 'Sevilla',
            'Valencia': 'Valencia',
            'Villarreal': 'Villarreal',
            'Real Sociedad': 'Real_Sociedad',
            'Real Betis': 'Real_Betis',
            # Bundesliga
            'Bayern Munich': 'Bayern_Munich',
            'Borussia Dortmund': 'Borussia_Dortmund',
            'RB Leipzig': 'RB_Leipzig',
            'Bayer Leverkusen': 'Bayer_Leverkusen',
            'Eintracht Frankfurt': 'Eintracht_Frankfurt',
            # Serie A
            'Juventus': 'Juventus',
            'Inter': 'Inter',
            'AC Milan': 'Milan',
            'Napoli': 'Napoli',
            'Roma': 'Roma',
            'Lazio': 'Lazio',
            'Atalanta': 'Atalanta',
        }

        return TEAM_NAME_MAP.get(django_team_name, django_team_name.replace(' ', '_'))


# ============================================================================
# FUNCIONES DE PRUEBA
# ============================================================================

if __name__ == "__main__":
    scraper = UnderstatScraper()

    # Probar scraping de Premier League 2024
    print("\n" + "="*80)
    print("PROBANDO UNDERSTAT SCRAPER - PREMIER LEAGUE 2024")
    print("="*80 + "\n")

    matches = scraper.get_league_matches('PL', 2024)

    if matches:
        print(f"\n{len(matches)} partidos encontrados")
        print("\nPrimeros 5 partidos:")
        for match in matches[:5]:
            print(f"{match['home_team']} {match['home_xg']:.2f} - {match['away_xg']:.2f} {match['away_team']}")
            print(f"  Resultado: {match['home_goals']} - {match['away_goals']}")
            print(f"  Fecha: {match['date']}")
            print()
