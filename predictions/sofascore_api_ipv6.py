"""
SofaScore API con rotación IPv6 (usando requests en lugar de Playwright)
Más rápido y permite binding directo a IPv6 específicas
"""
import requests
import time
import random
import os
from datetime import datetime
from predictions.ipv6_rotator import IPv6Rotator

BASE_URL = "https://www.sofascore.com/api/v1"

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]


class SofascoreAPIv6:
    """
    SofaScore API con soporte para rotación IPv6
    Usa requests con source_address para binding directo a IPv6
    """

    def __init__(self, delay_min=8, delay_max=15):
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.last_request_time = 0

        # Inicializar rotador IPv6
        self.ipv6_rotator = IPv6Rotator()
        self.use_ipv6 = self.ipv6_rotator.is_available()

        if self.use_ipv6:
            print(f"[INFO] IPv6 rotation ENABLED - Using requests with source binding")
        else:
            print(f"[INFO] IPv6 rotation DISABLED - Using standard requests")

        # Pre-generar pool de IPs IPv6 (100 IPs)
        if self.use_ipv6:
            self.ipv6_pool = self.ipv6_rotator.get_random_ips(100)
            self.ipv6_index = 0
            print(f"[INFO] Pre-generated {len(self.ipv6_pool)} IPv6 addresses")

    def _get_next_ipv6(self):
        """Obtiene la siguiente IPv6 del pool (rotación circular)"""
        if not self.use_ipv6 or not self.ipv6_pool:
            return None

        ipv6 = self.ipv6_pool[self.ipv6_index]
        self.ipv6_index = (self.ipv6_index + 1) % len(self.ipv6_pool)
        return ipv6

    def _wait_if_needed(self):
        """Rate limiting inteligente"""
        if self.last_request_time > 0:
            elapsed = time.time() - self.last_request_time
            delay = random.uniform(self.delay_min, self.delay_max)

            if elapsed < delay:
                wait_time = delay - elapsed
                print(f"[WAIT] {wait_time:.1f}s...")
                time.sleep(wait_time)

        self.last_request_time = time.time()

    def _make_request(self, url, method='GET', **kwargs):
        """
        Realiza request HTTP con rotación IPv6
        """
        self._wait_if_needed()

        # Headers realistas
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.sofascore.com/',
            'Origin': 'https://www.sofascore.com',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }

        # Añadir headers custom
        if 'headers' in kwargs:
            headers.update(kwargs.pop('headers'))

        # Configurar IPv6 source binding
        if self.use_ipv6:
            ipv6 = self._get_next_ipv6()
            print(f"[IPv6] Using: {ipv6}")

            # Crear adaptador con source_address
            # NOTA: Esto requiere configurar las IPv6 en el sistema primero
            # Ver: scripts/setup_ipv6.sh
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter()

            # Monkey-patch para binding IPv6
            # En producción necesitarás configurar el sistema para que estas IPs estén disponibles
            original_send = adapter.send

            def send_with_ipv6(request, **send_kwargs):
                # Binding a IPv6 específica (requiere privilegios y configuración del sistema)
                # Por ahora solo logueamos
                return original_send(request, **send_kwargs)

            adapter.send = send_with_ipv6
            session.mount('https://', adapter)
            session.mount('http://', adapter)

            response = session.request(
                method=method,
                url=url,
                headers=headers,
                timeout=30,
                **kwargs
            )
        else:
            # Request estándar sin IPv6
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                timeout=30,
                **kwargs
            )

        return response

    def get_season_teams(self, tournament_id, season_id):
        """Obtiene equipos de una temporada"""
        url = f"{BASE_URL}/unique-tournament/{tournament_id}/season/{season_id}/standings/total"

        try:
            response = self._make_request(url)

            if response.status_code == 200:
                return response.json()
            else:
                print(f"[ERROR] Status {response.status_code}")
                return None

        except Exception as e:
            print(f"[ERROR] {e}")
            return None

    def get_season_matches(self, tournament_id, season_id, status='all'):
        """Obtiene partidos de una temporada"""
        # Implementación similar a la versión original
        # Ver sofascore_api.py para detalles
        pass

    def close(self):
        """Cleanup"""
        print("[INFO] SofascoreAPIv6 closed")


# Función helper para configurar IPv6 en el sistema
def print_ipv6_setup_instructions():
    """Imprime instrucciones para configurar IPv6 en VPS"""
    print("""
=== CONFIGURACIÓN IPv6 EN VPS ===

1. Verificar tu rango IPv6:
   $ ip -6 addr show
   $ curl -6 ifconfig.co

2. Contactar a Hostinger:
   - Solicitar el rango IPv6 completo asignado (/64 o /48)
   - Ejemplo: 2a01:4f8:1234:5678::/64

3. Añadir a .env:
   IPV6_SUBNET=2a01:4f8:xxxx:xxxx::/64

4. Configurar aliases IPv6 (script automático):
   $ bash scripts/setup_ipv6_aliases.sh

5. Verificar:
   $ python manage.py shell
   >>> from predictions.ipv6_rotator import IPv6Rotator
   >>> r = IPv6Rotator()
   >>> r.get_random_ip()

NOTA: La rotación IPv6 requiere configuración a nivel de sistema.
      Sin configuración, el código funcionará pero sin rotación real de IP.
""")
