"""
Sofascore Web Scraper usando Playwright
Extrae datos navegando la web en lugar de usar la API directamente
"""

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
import asyncio
import json
import re
from datetime import datetime
import time
import random


class SofascoreWebScraper:
    def __init__(self, delay_min=5, delay_max=8, headless=True):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.headless = headless
        self.last_request_time = 0
        self.api_responses = {}  # Cache de respuestas interceptadas

    async def _init_browser(self):
        """Inicializar navegador con interceptación de red"""
        if self.playwright is None:
            self.playwright = await async_playwright().start()

            # Lanzar navegador
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                ]
            )

            # Crear contexto con user agent realista
            self.context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
            )

            # Crear página
            self.page = await self.context.new_page()

            # Interceptar llamadas de red
            self.page.on('response', self._handle_response)

            print("[Scraper] Navegador inicializado")

    async def _handle_response(self, response):
        """Interceptar respuestas de red para capturar llamadas a la API"""
        url = response.url

        # Solo capturar respuestas de la API de Sofascore (excluir imágenes)
        if ('api.sofascore.com' in url or 'sofascore.com/api' in url) and not '/image' in url:
            print(f"[Network] API Call: {url[:100]}... [Status: {response.status}]")

        # Solo capturar respuestas JSON (no imágenes)
        if ('api.sofascore.com' in url or 'sofascore.com/api' in url) and not '/image' in url and not '/jersey' in url and not '/flag' in url:
            try:
                # Intentar parsear como JSON
                if response.status == 200:
                    data = await response.json()

                    # Guardar en cache según el tipo de endpoint
                    if '/event/' in url and '/statistics' in url:
                        event_id = self._extract_id_from_url(url, r'/event/(\d+)')
                        self.api_responses[f'statistics_{event_id}'] = data
                        print(f"[API Intercepted] ✓ Estadísticas del evento {event_id}")

                    elif '/event/' in url and '/lineups' in url:
                        event_id = self._extract_id_from_url(url, r'/event/(\d+)')
                        self.api_responses[f'lineups_{event_id}'] = data
                        print(f"[API Intercepted] ✓ Alineaciones del evento {event_id}")

                    elif '/team/' in url and '/players' in url:
                        team_id = self._extract_id_from_url(url, r'/team/(\d+)')
                        self.api_responses[f'players_{team_id}'] = data
                        print(f"[API Intercepted] ✓ Jugadores del equipo {team_id}")

                    elif '/event/' in url and not any(x in url for x in ['statistics', 'lineups', 'incidents']):
                        event_id = self._extract_id_from_url(url, r'/event/(\d+)')
                        self.api_responses[f'event_{event_id}'] = data
                        print(f"[API Intercepted] ✓ Detalles del evento {event_id}")

                    else:
                        # Log otros endpoints que capturamos
                        print(f"[API Intercepted] Other: {url[:80]}")

            except Exception as e:
                print(f"[API Error] Failed to parse response from {url[:50]}: {e}")

    def _extract_id_from_url(self, url, pattern):
        """Extraer ID de una URL usando regex"""
        match = re.search(pattern, url)
        return match.group(1) if match else None

    async def _wait_if_needed(self):
        """Rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.delay_min:
            delay = random.uniform(self.delay_min, self.delay_max)
            await asyncio.sleep(delay)

        self.last_request_time = time.time()

    async def close(self):
        """Cerrar navegador"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("[Scraper] Navegador cerrado")

    # ============================================================================
    # MÉTODOS DE SCRAPING WEB
    # ============================================================================

    async def scrape_match_page(self, event_id):
        """
        Navegar a la página de un partido y extraer todos los datos disponibles
        """
        await self._init_browser()
        await self._wait_if_needed()

        # Limpiar cache
        self.api_responses = {}

        # Navegar directamente al tab de estadísticas para forzar carga de xG
        # Formato: https://www.sofascore.com/event/{id}#tab:statistics
        url = f"https://www.sofascore.com/event/{event_id}#tab:statistics"

        print(f"[Scraper] Navegando a: {url}")

        try:
            # Navegar a la página con tab de estadísticas
            response = await self.page.goto(url, wait_until='networkidle', timeout=30000)

            if response.status != 200:
                raise Exception(f"Error HTTP {response.status}")

            print(f"[Scraper] Página cargada")

            # Esperar a que carguen los datos iniciales
            await asyncio.sleep(5)

            # Hacer scroll para triggear lazy loading
            await self.page.evaluate('window.scrollBy(0, 300)')
            await asyncio.sleep(2)

            # Click en tab de estadísticas para triggear carga de datos
            try:
                # Intentar varios selectores
                selectors = [
                    'text=Statistics',
                    'a:has-text("Statistics")',
                    '[data-testid="wcl-statistics"]',
                    'button:has-text("Stats")'
                ]

                clicked = False
                for selector in selectors:
                    try:
                        await self.page.click(selector, timeout=3000)
                        clicked = True
                        break
                    except:
                        continue

                if clicked:
                    await asyncio.sleep(3)
                    print("[Scraper] Tab de estadísticas cargado")
                else:
                    print("[Scraper] No se encontró tab de estadísticas")

            except Exception as e:
                print(f"[Scraper] Error cargando estadísticas: {e}")

            # Click en tab de alineaciones
            try:
                selectors_lineups = [
                    'text=Line-ups',
                    'a:has-text("Line-ups")',
                    'a:has-text("Lineups")',
                    '[data-testid="wcl-lineups"]'
                ]

                clicked = False
                for selector in selectors_lineups:
                    try:
                        await self.page.click(selector, timeout=3000)
                        clicked = True
                        break
                    except:
                        continue

                if clicked:
                    await asyncio.sleep(3)
                    print("[Scraper] Tab de alineaciones cargado")
                else:
                    print("[Scraper] No se encontró tab de alineaciones")

            except Exception as e:
                print(f"[Scraper] Error cargando alineaciones: {e}")

            # Retornar datos interceptados
            return {
                'event_id': event_id,
                'url': self.page.url,  # URL final después de redirección
                'intercepted_data': self.api_responses.copy(),
                'timestamp': datetime.now().isoformat()
            }

        except PlaywrightTimeout:
            raise Exception(f"Timeout navegando a {url}")
        except Exception as e:
            raise Exception(f"Error scrapeando partido: {e}")

    async def scrape_team_players(self, team_id):
        """
        Navegar a la página de un equipo y extraer jugadores
        """
        await self._init_browser()
        await self._wait_if_needed()

        self.api_responses = {}

        url = f"https://www.sofascore.com/team/football/{team_id}#tab:statistics"

        print(f"[Scraper] Navegando a: {url}")

        try:
            await self.page.goto(url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(5)

            # Scroll para triggear lazy loading
            await self.page.evaluate('window.scrollBy(0, 500)')
            await asyncio.sleep(3)

            print("[Scraper] Tab de estadísticas del equipo cargado")

            return {
                'team_id': team_id,
                'url': self.page.url,
                'intercepted_data': self.api_responses.copy(),
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            raise Exception(f"Error scrapeando equipo: {e}")

    async def scrape_upcoming_matches(self, tournament_id, season_id):
        """
        Navegar a la página del torneo y extraer próximos partidos
        """
        await self._init_browser()
        await self._wait_if_needed()

        self.api_responses = {}

        # URL del torneo
        url = f"https://www.sofascore.com/tournament/football/{tournament_id}/season/{season_id}"

        print(f"[Scraper] Navegando a: {url}")

        try:
            await self.page.goto(url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(3)

            # Scroll para cargar más partidos
            for _ in range(3):
                await self.page.evaluate('window.scrollBy(0, 500)')
                await asyncio.sleep(1)

            return {
                'tournament_id': tournament_id,
                'season_id': season_id,
                'url': self.page.url,
                'intercepted_data': self.api_responses.copy(),
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            raise Exception(f"Error scrapeando torneo: {e}")

    async def extract_xg_from_stats(self, event_id):
        """
        Extraer xG de las estadísticas interceptadas
        """
        stats_key = f'statistics_{event_id}'

        if stats_key not in self.api_responses:
            return None

        stats = self.api_responses[stats_key]
        xg_data = {'home_xg': None, 'away_xg': None}

        try:
            # Buscar Expected Goals en las estadísticas
            if 'statistics' in stats:
                for stat_group in stats['statistics']:
                    if 'groups' in stat_group:
                        for group in stat_group['groups']:
                            if 'statisticsItems' in group:
                                for item in group['statisticsItems']:
                                    name = item.get('name', '').lower()
                                    if 'expected goals' in name or 'xg' in name:
                                        xg_data['home_xg'] = item.get('home')
                                        xg_data['away_xg'] = item.get('away')
                                        return xg_data
        except Exception as e:
            print(f"[Error] Extrayendo xG: {e}")

        return xg_data

    async def extract_lineups(self, event_id):
        """
        Extraer alineaciones de los datos interceptados
        """
        lineups_key = f'lineups_{event_id}'

        if lineups_key not in self.api_responses:
            return None

        return self.api_responses[lineups_key]

    async def extract_players(self, team_id):
        """
        Extraer jugadores de los datos interceptados
        """
        players_key = f'players_{team_id}'

        if players_key not in self.api_responses:
            return None

        return self.api_responses[players_key]


# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

async def test_scraper():
    """Función de prueba del scraper"""
    scraper = SofascoreWebScraper(headless=False)  # headless=False para ver el navegador

    try:
        # Probar con un evento (busca un partido reciente en Sofascore)
        event_id = 12345678  # Reemplazar con un ID real

        print(f"\n{'='*80}")
        print(f"PROBANDO SCRAPER CON EVENTO {event_id}")
        print(f"{'='*80}\n")

        result = await scraper.scrape_match_page(event_id)

        print(f"\n{'='*80}")
        print(f"DATOS INTERCEPTADOS:")
        print(f"{'='*80}")
        print(json.dumps(result['intercepted_data'], indent=2, default=str))

        # Extraer xG
        xg = await scraper.extract_xg_from_stats(event_id)
        print(f"\nxG extraído: {xg}")

    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(test_scraper())
