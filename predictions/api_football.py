"""
API-Football.com Wrapper
Documentación: https://www.api-football.com/documentation-v3

Endpoints principales:
- /fixtures - Información de partidos
- /fixtures/statistics - Estadísticas del partido (incluye xG)
- /fixtures/lineups - Alineaciones
- /injuries - Lesiones y suspensiones
- /standings - Clasificación
"""

import requests
import time
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class APIFootball:
    def __init__(self, api_key=None, rate_limit=10):
        """
        Args:
            api_key: API key de API-Football (si None, se obtiene de .env)
            rate_limit: Requests por minuto (10 para tier free, 300 para paid)
        """
        self.api_key = api_key or os.getenv('API_KEY_FOOTBALL')
        if not self.api_key:
            raise ValueError("API_KEY_FOOTBALL no encontrada en .env")

        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': 'v3.football.api-sports.io'
        }

        self.rate_limit = rate_limit  # Requests por minuto
        self.last_request_time = 0
        self.requests_made_today = 0
        self.requests_remaining = None

        # Mapeo de competiciones
        self.LEAGUE_MAP = {
            'PL': 39,      # Premier League
            'PD': 140,     # La Liga
            'BL1': 78,     # Bundesliga
            'SA': 135,     # Serie A
            'FL1': 61,     # Ligue 1
            'CL': 2,       # Champions League
        }

    def _wait_if_needed(self):
        """Rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        # Esperar al menos 60/rate_limit segundos entre requests
        min_interval = 60.0 / self.rate_limit

        if time_since_last < min_interval:
            wait_time = min_interval - time_since_last
            time.sleep(wait_time)

        self.last_request_time = time.time()

    def _make_request(self, endpoint, params=None):
        """Hacer request a la API con rate limiting"""
        self._wait_if_needed()

        url = f"{self.base_url}/{endpoint}"

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)

            # Actualizar información de rate limiting
            self.requests_remaining = response.headers.get('x-ratelimit-requests-remaining')

            if response.status_code == 200:
                data = response.json()
                return data

            elif response.status_code == 429:
                raise Exception("Rate limit exceeded. Espera antes de hacer más requests.")

            else:
                raise Exception(f"Error {response.status_code}: {response.text}")

        except requests.exceptions.RequestException as e:
            raise Exception(f"Request failed: {e}")

    # ============================================================================
    # FIXTURES - Partidos
    # ============================================================================

    def get_fixture(self, fixture_id):
        """
        Obtener información de un partido específico

        Args:
            fixture_id: ID del partido en API-Football

        Returns:
            dict con información del partido
        """
        params = {'id': fixture_id}
        response = self._make_request('fixtures', params)

        if response.get('results', 0) > 0:
            return response['response'][0]
        return None

    def get_fixtures_by_league_season(self, league_code, season):
        """
        Obtener todos los partidos de una liga en una temporada

        Args:
            league_code: 'PL', 'PD', 'BL1', 'SA', 'FL1', 'CL'
            season: Año (2024, 2023, etc.)

        Returns:
            Lista de partidos
        """
        if league_code not in self.LEAGUE_MAP:
            raise ValueError(f"Liga {league_code} no soportada")

        league_id = self.LEAGUE_MAP[league_code]
        params = {
            'league': league_id,
            'season': season
        }

        response = self._make_request('fixtures', params)

        if response.get('results', 0) > 0:
            return response['response']
        return []

    def get_fixtures_by_date(self, date, league_code=None):
        """
        Obtener partidos de una fecha específica

        Args:
            date: Fecha en formato 'YYYY-MM-DD' o datetime
            league_code: Opcional, filtrar por liga

        Returns:
            Lista de partidos
        """
        if isinstance(date, datetime):
            date = date.strftime('%Y-%m-%d')

        params = {'date': date}

        if league_code:
            if league_code not in self.LEAGUE_MAP:
                raise ValueError(f"Liga {league_code} no soportada")
            params['league'] = self.LEAGUE_MAP[league_code]

        response = self._make_request('fixtures', params)

        if response.get('results', 0) > 0:
            return response['response']
        return []

    # ============================================================================
    # STATISTICS - Estadísticas (incluye xG)
    # ============================================================================

    def get_fixture_statistics(self, fixture_id):
        """
        Obtener estadísticas de un partido (incluye xG)

        Args:
            fixture_id: ID del partido

        Returns:
            dict con estadísticas de ambos equipos
        """
        params = {'fixture': fixture_id}
        response = self._make_request('fixtures/statistics', params)

        if response.get('results', 0) > 0:
            return response['response']
        return None

    def extract_xg_from_statistics(self, statistics):
        """
        Extraer datos xG de las estadísticas

        Args:
            statistics: Respuesta de get_fixture_statistics()

        Returns:
            dict: {'home_xg': float, 'away_xg': float}
        """
        xg_data = {'home_xg': None, 'away_xg': None}

        if not statistics or len(statistics) < 2:
            return xg_data

        # statistics es una lista con 2 elementos: [home_team_stats, away_team_stats]
        for team_stats in statistics:
            stats_list = team_stats.get('statistics', [])
            team_name = team_stats.get('team', {}).get('name')

            # Buscar "expected_goals" en las estadísticas
            for stat in stats_list:
                if stat.get('type') == 'expected_goals':
                    xg_value = stat.get('value')

                    # Convertir a float (puede venir como string "2.3")
                    if xg_value is not None:
                        try:
                            xg_value = float(xg_value)
                        except (ValueError, TypeError):
                            xg_value = None

                    # Determinar si es home o away
                    # El primer elemento es home, el segundo es away
                    if statistics.index(team_stats) == 0:
                        xg_data['home_xg'] = xg_value
                    else:
                        xg_data['away_xg'] = xg_value

        return xg_data

    # ============================================================================
    # LINEUPS - Alineaciones
    # ============================================================================

    def get_fixture_lineups(self, fixture_id):
        """
        Obtener alineaciones de un partido

        Args:
            fixture_id: ID del partido

        Returns:
            dict con alineaciones de ambos equipos
        """
        params = {'fixture': fixture_id}
        response = self._make_request('fixtures/lineups', params)

        if response.get('results', 0) > 0:
            return response['response']
        return None

    # ============================================================================
    # INJURIES - Lesiones
    # ============================================================================

    def get_injuries(self, league_code, season):
        """
        Obtener lesiones de una liga

        Args:
            league_code: 'PL', 'PD', etc.
            season: Año

        Returns:
            Lista de lesiones
        """
        if league_code not in self.LEAGUE_MAP:
            raise ValueError(f"Liga {league_code} no soportada")

        league_id = self.LEAGUE_MAP[league_code]
        params = {
            'league': league_id,
            'season': season
        }

        response = self._make_request('injuries', params)

        if response.get('results', 0) > 0:
            return response['response']
        return []

    def get_team_injuries(self, team_id):
        """
        Obtener lesiones de un equipo específico

        Args:
            team_id: ID del equipo en API-Football

        Returns:
            Lista de lesiones del equipo
        """
        params = {'team': team_id}
        response = self._make_request('injuries', params)

        if response.get('results', 0) > 0:
            return response['response']
        return []

    # ============================================================================
    # STANDINGS - Clasificación
    # ============================================================================

    def get_standings(self, league_code, season):
        """
        Obtener clasificación de una liga

        Args:
            league_code: 'PL', 'PD', etc.
            season: Año

        Returns:
            Clasificación
        """
        if league_code not in self.LEAGUE_MAP:
            raise ValueError(f"Liga {league_code} no soportada")

        league_id = self.LEAGUE_MAP[league_code]
        params = {
            'league': league_id,
            'season': season
        }

        response = self._make_request('standings', params)

        if response.get('results', 0) > 0:
            return response['response']
        return []

    # ============================================================================
    # UTILITIES
    # ============================================================================

    def get_remaining_requests(self):
        """Obtener número de requests restantes"""
        return self.requests_remaining

    def map_team_name(self, api_football_name):
        """
        Mapear nombre de equipo de API-Football a nuestro sistema

        Args:
            api_football_name: Nombre del equipo en API-Football

        Returns:
            Nombre normalizado
        """
        # Mapeo manual de nombres comunes
        NAME_MAP = {
            'Manchester United': 'Man United',
            'Manchester City': 'Man City',
            'Tottenham': 'Tottenham',
            'West Ham United': 'West Ham',
            'Wolverhampton Wanderers': 'Wolves',
            'Brighton & Hove Albion': 'Brighton',
            'Newcastle United': 'Newcastle',
            'Nottingham Forest': 'Nottingham Forest',
        }

        return NAME_MAP.get(api_football_name, api_football_name)


# ============================================================================
# FUNCIONES DE PRUEBA
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("TEST DE API-FOOTBALL - OBTENCIÓN DE xG")
    print("=" * 80)

    api = APIFootball()

    # Probar obtener partidos recientes de Premier League
    print("\n[1] Obteniendo partidos recientes de Premier League 2024...")

    try:
        fixtures = api.get_fixtures_by_league_season('PL', 2024)
        print(f"Total partidos encontrados: {len(fixtures)}")

        if fixtures:
            # Tomar un partido finalizado
            finished_fixture = None
            for fixture in fixtures:
                if fixture['fixture']['status']['short'] == 'FT':
                    finished_fixture = fixture
                    break

            if finished_fixture:
                fixture_id = finished_fixture['fixture']['id']
                home = finished_fixture['teams']['home']['name']
                away = finished_fixture['teams']['away']['name']
                score_home = finished_fixture['goals']['home']
                score_away = finished_fixture['goals']['away']

                print(f"\nPartido seleccionado (ID: {fixture_id}):")
                print(f"  {home} {score_home} - {score_away} {away}")

                # Obtener estadísticas con xG
                print(f"\n[2] Obteniendo estadísticas y xG del partido...")
                stats = api.get_fixture_statistics(fixture_id)

                if stats:
                    xg = api.extract_xg_from_statistics(stats)
                    print(f"\n  xG Home: {xg['home_xg']}")
                    print(f"  xG Away: {xg['away_xg']}")

                    if xg['home_xg'] is not None:
                        print(f"\n  ✓ xG OBTENIDO EXITOSAMENTE!")
                    else:
                        print(f"\n  ⚠ xG no disponible para este partido")
                else:
                    print("  No se pudieron obtener estadísticas")

        print(f"\n[3] Requests restantes: {api.get_remaining_requests()}")

    except Exception as e:
        print(f"\nError: {e}")

    print("\n" + "=" * 80)
