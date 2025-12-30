from playwright.async_api import async_playwright
import asyncio
from datetime import datetime, timedelta
import pandas as pd
import time
import random

BASE_URL = "https://www.sofascore.com/api/v1"


class SofascoreAPI:
    def __init__(self, delay_min=2, delay_max=5):
        self.browser = None
        self.page = None
        self.playwright = None
        self.delay_min = delay_min  # Delay mínimo entre peticiones (segundos)
        self.delay_max = delay_max  # Delay máximo entre peticiones (segundos)
        self.last_request_time = 0

    async def _init_browser(self):
        if self.playwright is None:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
            self.page = await self.browser.new_page()

    async def _wait_if_needed(self):
        """Rate limiting: espera entre peticiones"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.delay_min:
            # Añadir delay aleatorio para parecer más humano
            delay = random.uniform(self.delay_min, self.delay_max)
            await asyncio.sleep(delay)

        self.last_request_time = time.time()

    async def _get(self, endpoint):
        await self._init_browser()
        await self._wait_if_needed()  # Rate limiting

        url = f"{BASE_URL}{endpoint}"
        response = await self.page.goto(url)
        if response.status == 200:
            return await response.json()
        else:
            raise Exception(f"Failed to fetch {endpoint}: {response.status}")

    async def _raw_get(self, url):
        await self._init_browser()
        await self._wait_if_needed()  # Rate limiting

        response = await self.page.goto(url)
        if response.status == 200:
            return await response.json()
        else:
            raise Exception(f"Failed to fetch {url}: {response.status}")

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        # ============================================
        # MÉTODOS PARA PARTIDOS
        # ============================================

    async def get_partidos_hoy(self, deporte="football"):
        """
        Obtener partidos del día actual
        Deportes disponibles: football, basketball, tennis, etc.
        """
        hoy = datetime.now().strftime("%Y-%m-%d")
        endpoint = f"/sport/{deporte}/scheduled-events/{hoy}"
        return await self._get(endpoint)

    async def get_partidos_fecha(self, fecha, deporte="football"):
        """
        Obtener partidos de una fecha específica
        fecha: formato "YYYY-MM-DD" o datetime object
        """
        if isinstance(fecha, datetime):
            fecha = fecha.strftime("%Y-%m-%d")
        endpoint = f"/sport/{deporte}/scheduled-events/{fecha}"
        return await self._get(endpoint)

    async def get_partidos_en_vivo(self, deporte="football"):
        """
        Obtener partidos en vivo
        """
        endpoint = f"/sport/{deporte}/events/live"
        return await self._get(endpoint)

    async def get_partido_detalles(self, event_id):
        """
        Obtener detalles de un partido específico
        """
        endpoint = f"/event/{event_id}"
        return await self._get(endpoint)

    async def get_partido_estadisticas(self, event_id):
        """
        Obtener estadísticas de un partido
        """
        endpoint = f"/event/{event_id}/statistics"
        return await self._get(endpoint)

    async def get_partido_lineups(self, event_id):
        """
        Obtener alineaciones de un partido
        """
        endpoint = f"/event/{event_id}/lineups"
        return await self._get(endpoint)

    async def get_partido_incidentes(self, event_id):
        """
        Obtener eventos del partido (goles, tarjetas, etc.)
        """
        endpoint = f"/event/{event_id}/incidents"
        return await self._get(endpoint)

    async def get_partido_xg(self, event_id):
        """
        Obtener datos de Expected Goals (xG) de un partido
        Incluido en estadísticas pero este método es más explícito
        """
        stats = await self.get_partido_estadisticas(event_id)
        # xG suele estar en las estadísticas bajo 'expectedGoals'
        return stats

    async def get_partido_forma_reciente(self, event_id):
        """
        Obtener forma reciente de ambos equipos antes del partido
        """
        endpoint = f"/event/{event_id}/form"
        return await self._get(endpoint)

        # ============================================
        # MÉTODOS PARA EQUIPOS
        # ============================================

    async def get_equipo_info(self, team_id):
        """
        Obtener información de un equipo
        """
        endpoint = f"/team/{team_id}"
        return await self._get(endpoint)

    async def get_equipo_proximos_partidos(self, team_id):
        """
        Obtener próximos partidos de un equipo
        """
        endpoint = f"/team/{team_id}/events/next/0"
        return await self._get(endpoint)

    async def get_equipo_ultimos_partidos(self, team_id):
        """
        Obtener últimos partidos de un equipo
        """
        endpoint = f"/team/{team_id}/events/last/0"
        return await self._get(endpoint)

    async def get_equipo_jugadores(self, team_id):
        """
        Obtener plantilla de un equipo
        """
        endpoint = f"/team/{team_id}/players"
        return await self._get(endpoint)

    async def get_equipo_lesiones(self, team_id):
        """
        Obtener lesiones y suspensiones de un equipo
        """
        endpoint = f"/team/{team_id}/unavailable"
        return await self._get(endpoint)

    async def get_jugador_info(self, player_id):
        """
        Obtener información de un jugador específico
        """
        endpoint = f"/player/{player_id}"
        return await self._get(endpoint)

    async def get_jugador_estadisticas(self, player_id, tournament_id, season_id):
        """
        Obtener estadísticas de un jugador en una temporada específica
        """
        endpoint = f"/player/{player_id}/unique-tournament/{tournament_id}/season/{season_id}/statistics/overall"
        return await self._get(endpoint)

        # ============================================
        # MÉTODOS PARA TORNEOS/LIGAS
        # ============================================

    async def get_torneo_info(self, tournament_id):
        """
        Obtener información de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/"
        # endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/info"
        return await self._get(endpoint)

    async def get_info_temporada_info(self, tournament_id, season_id):
        """
        Obtener información de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/info"
        return await self._get(endpoint)

    async def get_temporadas_ligas_info(self, tournament_id):
        """
        Obtener información de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/seasons/"
        return await self._get(endpoint)

    async def get_equipos_temporada_info(self, tournament_id, season_id):
        """
        Obtener información de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/teams"
        return await self._get(endpoint)


    async def get_torneo_tabla(self, tournament_id, season_id):
        """
        Obtener tabla de posiciones de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/standings/total"
        return await self._get(endpoint)

    async def get_torneo_partidos(self, tournament_id, season_id):
        """
        Obtener todos los partidos de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/events/last/0"
        return await self._get(endpoint)

    async def get_torneo_rounds(self, tournament_id, season_id):
        """
        Obtener las rondas de un torneo/temporada
        """
        endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/rounds"
        return await self._get(endpoint)

    async def get_torneo_partidos_round(self, tournament_id, season_id, round_number):
        """
        Obtener partidos de una ronda específica
        """
        endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/events/round/{round_number}"
        return await self._get(endpoint)

    async def get_torneo_proximos_partidos(self, tournament_id, season_id):
        """
        Obtener próximos partidos de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/events/next/0"
        return await self._get(endpoint)

    async def get_league_player_stats(self, tournament_id, season_id, accumulation='total',
                                      limit=100, offset=0, order='-rating'):
        """
        Obtener estadísticas de jugadores para una liga/temporada

        Args:
            tournament_id: ID del torneo en SofaScore
            season_id: ID de la temporada
            accumulation: 'total', 'per90', o 'perMatch'
            limit: Número de resultados por página (máximo 100)
            offset: Offset para paginación
            order: Ordenamiento (por defecto '-rating' = rating descendente)

        Returns:
            dict con 'results' (lista de jugadores) y 'pages' (número total de páginas)
        """
        # Campos de estadísticas a solicitar
        fields = [
            'rating', 'goals', 'assists', 'accuratePass', 'totalPass',
            'keyPass', 'accurateCross', 'totalCross', 'duelWon', 'duelLost',
            'aerialWon', 'aerialLost', 'blockedShots', 'interceptions',
            'totalTackle', 'tackles', 'wasFouled', 'fouls', 'minutesPlayed',
            'touches', 'appearances', 'expectedGoals', 'expectedAssists',
            'yellowCards', 'redCards', 'successfulDribbles', 'totalDribbles',
            'shotsOnTarget', 'shotsTotal', 'penaltyGoals', 'penaltyWon',
            'bigChanceCreated', 'bigChanceMissed'
        ]
        fields_param = '%2C'.join(fields)  # URL encode comma

        endpoint = (f"/unique-tournament/{tournament_id}/season/{season_id}/statistics"
                   f"?limit={limit}&order={order}&offset={offset}"
                   f"&accumulation={accumulation}&fields={fields_param}")

        return await self._get(endpoint)

    async def get_all_league_player_stats(self, tournament_id, season_id, accumulation='total',
                                          max_pages=None):
        """
        Obtener TODAS las estadísticas de jugadores paginadas

        Args:
            tournament_id: ID del torneo en SofaScore
            season_id: ID de la temporada
            accumulation: 'total', 'per90', o 'perMatch'
            max_pages: Límite de páginas a obtener (None = todas)

        Returns:
            list: Lista de todos los jugadores con sus estadísticas
        """
        all_players = []
        offset = 0
        page = 0

        while True:
            data = await self.get_league_player_stats(
                tournament_id, season_id, accumulation,
                limit=100, offset=offset
            )

            if not data or 'results' not in data:
                break

            all_players.extend(data['results'])
            page += 1

            # Verificar si hay más páginas
            total_pages = data.get('pages', 1)
            print(f"  Página {page}/{total_pages} - {len(data['results'])} jugadores obtenidos")

            if page >= total_pages:
                break

            if max_pages and page >= max_pages:
                break

            offset += 100

        return all_players

    # ============================================
    # MÉTODOS PARA IMPORTACIÓN UNIFICADA
    # ============================================

    async def get_season_teams(self, tournament_id, season_id):
        """
        Obtener todos los equipos de una temporada con información completa

        Args:
            tournament_id: ID del torneo
            season_id: ID de la temporada

        Returns:
            dict: Información de equipos
        """
        # Obtener lista de equipos
        teams_endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/teams"
        teams_data = await self._get(teams_endpoint)

        # teams_data ya contiene la lista de equipos bajo la key 'teams'
        return teams_data

    async def get_season_matches(self, tournament_id, season_id, status='all'):
        """
        Obtener todos los partidos de una temporada usando jornadas/rounds

        Args:
            tournament_id: ID del torneo
            season_id: ID de la temporada
            status: 'finished', 'scheduled', o 'all'

        Returns:
            list: Lista de partidos
        """
        all_matches = []
        seen_match_ids = set()

        try:
            # Primero intentar obtener todas las jornadas
            rounds_data = await self.get_torneo_rounds(tournament_id, season_id)

            if rounds_data and 'rounds' in rounds_data:
                rounds = rounds_data['rounds']
                print(f"  [INFO] Obteniendo partidos de {len(rounds)} jornadas...")

                for round_info in rounds:
                    round_num = round_info.get('round', 0)
                    try:
                        round_matches = await self.get_torneo_partidos_round(
                            tournament_id, season_id, round_num
                        )

                        if round_matches and 'events' in round_matches:
                            for match in round_matches['events']:
                                match_id = match.get('id')
                                if match_id and match_id not in seen_match_ids:
                                    match_status = match.get('status', {}).get('type', '').lower()

                                    # Filtrar por status si es necesario
                                    if status == 'finished' and match_status != 'finished':
                                        continue
                                    if status == 'scheduled' and match_status == 'finished':
                                        continue

                                    # Agregar matchday/round al partido
                                    match['_matchday'] = round_num
                                    all_matches.append(match)
                                    seen_match_ids.add(match_id)
                    except Exception as e:
                        print(f"  [WARN] Error en jornada {round_num}: {e}")
                        continue

                print(f"  [INFO] Total partidos obtenidos: {len(all_matches)}")
                return all_matches

        except Exception as e:
            print(f"  [WARN] No se pudieron obtener jornadas: {e}")

        # Fallback: método anterior (limitado)
        print(f"  [INFO] Usando método fallback (limitado)...")

        # Obtener partidos finalizados (últimos partidos)
        if status in ['finished', 'all']:
            try:
                finished_endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/events/last/0"
                finished_data = await self._get(finished_endpoint)
                if finished_data and 'events' in finished_data:
                    for match in finished_data['events']:
                        match_id = match.get('id')
                        if match_id not in seen_match_ids:
                            all_matches.append(match)
                            seen_match_ids.add(match_id)
            except Exception as e:
                print(f"  [WARN] No se pudieron obtener partidos finalizados: {e}")

        # Obtener partidos programados (próximos partidos)
        if status in ['scheduled', 'all']:
            try:
                scheduled_endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/events/next/0"
                scheduled_data = await self._get(scheduled_endpoint)
                if scheduled_data and 'events' in scheduled_data:
                    for match in scheduled_data['events']:
                        match_id = match.get('id')
                        if match_id not in seen_match_ids:
                            all_matches.append(match)
                            seen_match_ids.add(match_id)
            except Exception as e:
                # Es normal que no haya partidos programados en temporadas pasadas
                pass

        return all_matches

    async def get_match_complete_data(self, event_id):
        """
        Obtener datos completos de un partido (detalles + estadísticas + lineups)

        Args:
            event_id: ID del evento/partido

        Returns:
            dict: Diccionario con toda la información del partido
        """
        result = {}

        try:
            # Detalles básicos del partido
            result['details'] = await self.get_partido_detalles(event_id)
        except Exception as e:
            print(f"  [WARN] Error obteniendo detalles de {event_id}: {e}")
            result['details'] = None

        try:
            # Estadísticas del partido
            result['statistics'] = await self.get_partido_estadisticas(event_id)
        except Exception as e:
            print(f"  [WARN] Error obteniendo estadísticas de {event_id}: {e}")
            result['statistics'] = None

        try:
            # Lineups
            result['lineups'] = await self.get_partido_lineups(event_id)
        except Exception as e:
            print(f"  [WARN] Error obteniendo lineups de {event_id}: {e}")
            result['lineups'] = None

        return result


    # ============================================
    # FUNCIONES DE UTILIDAD
    # ============================================

    async def formatear_partidos(data):
        """
        Formatea los datos de partidos en un formato legible
        """
        partidos = []
        for evento in data.get('events', []):
            partido = {
                'id': evento.get('id'),
                'local': evento.get('homeTeam', {}).get('name'),
                'visitante': evento.get('awayTeam', {}).get('name'),
                'marcador_local': evento.get('homeScore', {}).get('current'),
                'marcador_visitante': evento.get('awayScore', {}).get('current'),
                'estado': evento.get('status', {}).get('description'),
                'torneo': evento.get('tournament', {}).get('name'),
                'fecha': datetime.fromtimestamp(evento.get('startTimestamp', 0)),
            }
            partidos.append(partido)
        return pd.DataFrame(partidos)
