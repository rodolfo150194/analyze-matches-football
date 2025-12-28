from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
from datetime import datetime, timedelta
import pandas as pd
import time
import random
import os

BASE_URL = "https://www.sofascore.com/api/v1"

# Lista de User-Agents para rotar (navegadores reales recientes)
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]


class SofascoreAPI:
    def __init__(self, delay_min=8, delay_max=15, is_vps=None):
        self.browser = None
        self.page = None
        self.playwright = None

        # Auto-detectar si estamos en VPS (mediante variable de entorno)
        if is_vps is None:
            is_vps = os.getenv('IS_VPS', 'false').lower() == 'true'

        # Delays más largos para VPS (anti-detección agresiva)
        if is_vps:
            self.delay_min = max(delay_min, 15)  # Mínimo 15 segundos en VPS
            self.delay_max = max(delay_max, 25)  # Máximo 25 segundos en VPS
            print(f"[INFO] Modo VPS activado - Delays: {self.delay_min}-{self.delay_max}s")
        else:
            self.delay_min = delay_min
            self.delay_max = delay_max
            print(f"[INFO] Modo Local - Delays: {self.delay_min}-{self.delay_max}s")

        self.last_request_time = 0
        self.initialized = False
        self.is_vps = is_vps

    def _init_browser(self):
        if self.playwright is None:
            self.playwright = sync_playwright().start()

            # Argumentos mejorados para anti-detección
            launch_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-software-rasterizer',
                '--disable-extensions',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-web-security',  # Útil para evitar CORS en scraping
                '--disable-features=VizDisplayCompositor',
                '--lang=en-US,en',
            ]

            self.browser = self.playwright.chromium.launch(
                headless=True,
                args=launch_args,
                slow_mo=random.randint(100, 300) if self.is_vps else 0,  # Simular humano en VPS
            )

            # Seleccionar User-Agent aleatorio
            user_agent = random.choice(USER_AGENTS)
            print(f"[INFO] User-Agent: {user_agent[:50]}...")

            # Crear contexto del navegador (mejor que new_page directamente)
            context = self.browser.new_context(
                user_agent=user_agent,
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                timezone_id='America/New_York',  # Timezone realista
                # Permisos como un usuario real
                permissions=['geolocation'],
                geolocation={'latitude': 40.7128, 'longitude': -74.0060},  # NYC
                color_scheme='light',
                device_scale_factor=1,
            )

            # Crear página desde el contexto
            self.page = context.new_page()

            # APLICAR PLAYWRIGHT-STEALTH (oculta automatización) - AHORA FUNCIONA!
            stealth_sync(self.page)
            print("[INFO] ✓ Playwright-stealth aplicado correctamente (modo SYNC)")

            # Headers adicionales más realistas
            self.page.set_extra_http_headers({
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9,es;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://www.sofascore.com/',
                'Origin': 'https://www.sofascore.com',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
                'DNT': '1',  # Do Not Track
                'Upgrade-Insecure-Requests': '1',
            })

            # Inyectar scripts para ocultar webdriver
            self.page.add_init_script("""
                // Ocultar que somos un navegador automatizado
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                // Fingir plugins de navegador real
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });

                // Fingir idiomas
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en', 'es']
                });

                // Chrome object
                window.chrome = {
                    runtime: {}
                };

                // Permisos
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)

            # Visitar la página principal para obtener cookies y sesión
            if not self.initialized:
                try:
                    print("[INFO] Inicializando sesión en SofaScore...")

                    # Ir a la página principal
                    self.page.goto('https://www.sofascore.com/', wait_until='domcontentloaded', timeout=60000)

                    # Simular comportamiento humano
                    time.sleep(random.uniform(2, 4))

                    # Scroll aleatorio (como humano)
                    self.page.evaluate(f'window.scrollBy(0, {random.randint(100, 300)})')
                    time.sleep(random.uniform(1, 2))

                    # Mover mouse aleatoriamente
                    self.page.mouse.move(random.randint(100, 500), random.randint(100, 500))
                    time.sleep(random.uniform(0.5, 1.5))

                    self.initialized = True
                    print("[INFO] Sesión inicializada correctamente")

                    # Delay extra en VPS después de inicializar
                    if self.is_vps:
                        delay = random.uniform(5, 10)
                        print(f"[INFO] Esperando {delay:.1f}s adicionales (modo VPS)...")
                        time.sleep(delay)

                except Exception as e:
                    print(f"[WARN] Error inicializando sesión: {e}")
                    # No fallar, intentar continuar

    def _wait_if_needed(self):
        """Rate limiting mejorado: espera entre peticiones con variación humana"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.delay_min:
            # Delay aleatorio con distribución más realista
            base_delay = random.uniform(self.delay_min, self.delay_max)

            # Variación adicional para parecer más humano (±10%)
            variation = random.uniform(-0.1, 0.1) * base_delay
            final_delay = max(1, base_delay + variation)  # Mínimo 1 segundo

            print(f"[RATE LIMIT] Esperando {final_delay:.1f}s antes de siguiente petición...")
            time.sleep(final_delay)
        else:
            # Aunque no necesitamos esperar, agregar micro-delay aleatorio
            micro_delay = random.uniform(0.5, 2.0)
            time.sleep(micro_delay)

        self.last_request_time = time.time()

    def _get(self, endpoint, max_retries=3):
        """GET mejorado con reintentos en caso de error 403"""
        self._init_browser()
        self._wait_if_needed()  # Rate limiting

        url = f"{BASE_URL}{endpoint}"

        for attempt in range(max_retries):
            try:
                response = self.page.goto(url, timeout=60000)

                if response.status == 200:
                    return response.json()
                elif response.status == 403:
                    print(f"[ERROR 403] Detectado en {endpoint} (intento {attempt + 1}/{max_retries})")

                    if attempt < max_retries - 1:
                        # Esperar más tiempo antes de reintentar
                        wait_time = random.uniform(30, 60) if self.is_vps else random.uniform(10, 20)
                        print(f"[RETRY] Esperando {wait_time:.1f}s antes de reintentar...")
                        time.sleep(wait_time)

                        # Cerrar y reinicializar navegador con nuevo user-agent
                        print("[RETRY] Reinicializando navegador con nuevo User-Agent...")
                        self.close()
                        self.playwright = None
                        self.initialized = False
                        self._init_browser()
                    else:
                        raise Exception(f"Error 403 persistente después de {max_retries} intentos: {endpoint}")
                else:
                    raise Exception(f"HTTP {response.status}: {endpoint}")

            except Exception as e:
                if "Timeout" in str(e) or "TimeoutError" in str(type(e).__name__):
                    print(f"[TIMEOUT] en {endpoint} (intento {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(random.uniform(5, 10))
                    else:
                        raise Exception(f"Timeout persistente: {endpoint}")
                else:
                    raise

        raise Exception(f"Failed to fetch {endpoint} after {max_retries} attempts")

    def _raw_get(self, url, max_retries=3):
        """GET mejorado para URLs completas con reintentos"""
        self._init_browser()
        self._wait_if_needed()  # Rate limiting

        for attempt in range(max_retries):
            try:
                response = self.page.goto(url, timeout=60000)

                if response.status == 200:
                    return response.json()
                elif response.status == 403:
                    print(f"[ERROR 403] Detectado en {url[:50]}... (intento {attempt + 1}/{max_retries})")

                    if attempt < max_retries - 1:
                        wait_time = random.uniform(30, 60) if self.is_vps else random.uniform(10, 20)
                        print(f"[RETRY] Esperando {wait_time:.1f}s antes de reintentar...")
                        time.sleep(wait_time)

                        # Reinicializar con nuevo user-agent
                        self.close()
                        self.playwright = None
                        self.initialized = False
                        self._init_browser()
                    else:
                        raise Exception(f"Error 403 persistente después de {max_retries} intentos")
                else:
                    raise Exception(f"HTTP {response.status}: {url}")

            except Exception as e:
                if "Timeout" in str(e) or "TimeoutError" in str(type(e).__name__):
                    print(f"[TIMEOUT] en {url[:50]}... (intento {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(random.uniform(5, 10))
                    else:
                        raise Exception(f"Timeout persistente: {url}")
                else:
                    raise

        raise Exception(f"Failed to fetch {url} after {max_retries} attempts")

    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

        # ============================================
        # MÉTODOS PARA PARTIDOS
        # ============================================

    def get_partidos_hoy(self, deporte="football"):
        """
        Obtener partidos del día actual
        Deportes disponibles: football, basketball, tennis, etc.
        """
        hoy = datetime.now().strftime("%Y-%m-%d")
        endpoint = f"/sport/{deporte}/scheduled-events/{hoy}"
        return self._get(endpoint)

    def get_partidos_fecha(self, fecha, deporte="football"):
        """
        Obtener partidos de una fecha específica
        fecha: formato "YYYY-MM-DD" o datetime object
        """
        if isinstance(fecha, datetime):
            fecha = fecha.strftime("%Y-%m-%d")
        endpoint = f"/sport/{deporte}/scheduled-events/{fecha}"
        return self._get(endpoint)

    def get_partidos_en_vivo(self, deporte="football"):
        """
        Obtener partidos en vivo
        """
        endpoint = f"/sport/{deporte}/events/live"
        return self._get(endpoint)

    def get_partido_detalles(self, event_id):
        """
        Obtener detalles de un partido específico
        """
        endpoint = f"/event/{event_id}"
        return self._get(endpoint)

    def get_partido_estadisticas(self, event_id):
        """
        Obtener estadísticas de un partido
        """
        endpoint = f"/event/{event_id}/statistics"
        return self._get(endpoint)

    def get_partido_lineups(self, event_id):
        """
        Obtener alineaciones de un partido
        """
        endpoint = f"/event/{event_id}/lineups"
        return self._get(endpoint)

    def get_partido_incidentes(self, event_id):
        """
        Obtener eventos del partido (goles, tarjetas, etc.)
        """
        endpoint = f"/event/{event_id}/incidents"
        return self._get(endpoint)

    def get_partido_xg(self, event_id):
        """
        Obtener datos de Expected Goals (xG) de un partido
        Incluido en estadísticas pero este método es más explícito
        """
        stats = self.get_partido_estadisticas(event_id)
        # xG suele estar en las estadísticas bajo 'expectedGoals'
        return stats

    def get_partido_forma_reciente(self, event_id):
        """
        Obtener forma reciente de ambos equipos antes del partido
        """
        endpoint = f"/event/{event_id}/form"
        return self._get(endpoint)

        # ============================================
        # MÉTODOS PARA EQUIPOS
        # ============================================

    def get_equipo_info(self, team_id):
        """
        Obtener información de un equipo
        """
        endpoint = f"/team/{team_id}"
        return self._get(endpoint)

    def get_equipo_proximos_partidos(self, team_id):
        """
        Obtener próximos partidos de un equipo
        """
        endpoint = f"/team/{team_id}/events/next/0"
        return self._get(endpoint)

    def get_equipo_ultimos_partidos(self, team_id):
        """
        Obtener últimos partidos de un equipo
        """
        endpoint = f"/team/{team_id}/events/last/0"
        return self._get(endpoint)

    def get_equipo_jugadores(self, team_id):
        """
        Obtener plantilla de un equipo
        """
        endpoint = f"/team/{team_id}/players"
        return self._get(endpoint)

    def get_equipo_lesiones(self, team_id):
        """
        Obtener lesiones y suspensiones de un equipo
        """
        endpoint = f"/team/{team_id}/unavailable"
        return self._get(endpoint)

    def get_jugador_info(self, player_id):
        """
        Obtener información de un jugador específico
        """
        endpoint = f"/player/{player_id}"
        return self._get(endpoint)

    def get_jugador_estadisticas(self, player_id, tournament_id, season_id):
        """
        Obtener estadísticas de un jugador en una temporada específica
        """
        endpoint = f"/player/{player_id}/unique-tournament/{tournament_id}/season/{season_id}/statistics/overall"
        return self._get(endpoint)

        # ============================================
        # MÉTODOS PARA TORNEOS/LIGAS
        # ============================================

    def get_torneo_info(self, tournament_id):
        """
        Obtener información de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/"
        # endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/info"
        return self._get(endpoint)

    def get_info_temporada_info(self, tournament_id, season_id):
        """
        Obtener información de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/info"
        return self._get(endpoint)

    def get_temporadas_ligas_info(self, tournament_id):
        """
        Obtener información de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/seasons/"
        return self._get(endpoint)

    def get_equipos_temporada_info(self, tournament_id, season_id):
        """
        Obtener información de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/teams"
        return self._get(endpoint)


    def get_torneo_tabla(self, tournament_id, season_id):
        """
        Obtener tabla de posiciones de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/standings/total"
        return self._get(endpoint)

    def get_torneo_partidos(self, tournament_id, season_id):
        """
        Obtener todos los partidos de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/events/last/0"
        return self._get(endpoint)

    def get_torneo_rounds(self, tournament_id, season_id):
        """
        Obtener las rondas de un torneo/temporada
        """
        endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/rounds"
        return self._get(endpoint)

    def get_torneo_partidos_round(self, tournament_id, season_id, round_number):
        """
        Obtener partidos de una ronda específica
        """
        endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/events/round/{round_number}"
        return self._get(endpoint)

    def get_torneo_proximos_partidos(self, tournament_id, season_id):
        """
        Obtener próximos partidos de un torneo
        """
        endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/events/next/0"
        return self._get(endpoint)

    def get_league_player_stats(self, tournament_id, season_id, accumulation='total',
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

        return self._get(endpoint)

    def get_all_league_player_stats(self, tournament_id, season_id, accumulation='total',
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
            data = self.get_league_player_stats(
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

    def get_season_teams(self, tournament_id, season_id):
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
        teams_data = self._get(teams_endpoint)

        # teams_data ya contiene la lista de equipos bajo la key 'teams'
        return teams_data

    def get_season_matches(self, tournament_id, season_id, status='all'):
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
            rounds_data = self.get_torneo_rounds(tournament_id, season_id)

            if rounds_data and 'rounds' in rounds_data:
                rounds = rounds_data['rounds']
                print(f"  [INFO] Obteniendo partidos de {len(rounds)} jornadas...")

                for round_info in rounds:
                    round_num = round_info.get('round', 0)
                    try:
                        round_matches = self.get_torneo_partidos_round(
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
                finished_data = self._get(finished_endpoint)
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
                scheduled_data = self._get(scheduled_endpoint)
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

    def get_match_complete_data(self, event_id):
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
            result['details'] = self.get_partido_detalles(event_id)
        except Exception as e:
            print(f"  [WARN] Error obteniendo detalles de {event_id}: {e}")
            result['details'] = None

        try:
            # Estadísticas del partido
            result['statistics'] = self.get_partido_estadisticas(event_id)
        except Exception as e:
            print(f"  [WARN] Error obteniendo estadísticas de {event_id}: {e}")
            result['statistics'] = None

        try:
            # Lineups
            result['lineups'] = self.get_partido_lineups(event_id)
        except Exception as e:
            print(f"  [WARN] Error obteniendo lineups de {event_id}: {e}")
            result['lineups'] = None

        return result


    # ============================================
    # FUNCIONES DE UTILIDAD
    # ============================================

    def formatear_partidos(data):
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
