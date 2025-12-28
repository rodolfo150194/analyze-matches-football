"""
IPv6 Rotation Helper for VPS
Genera IPs IPv6 aleatorias dentro de un rango asignado para evitar rate limiting
"""
import random
import ipaddress
import os


class IPv6Rotator:
    """Generador de IPs IPv6 aleatorias para rotación"""

    def __init__(self, subnet=None):
        """
        Args:
            subnet: Rango IPv6 en formato CIDR (ej: "2a01:4f8:1234:5678::/64")
                    Si None, lee de variable de entorno IPV6_SUBNET
        """
        if subnet is None:
            subnet = os.getenv('IPV6_SUBNET')

        if not subnet:
            self.enabled = False
            self.network = None
            print("[INFO] IPv6 rotation disabled - no IPV6_SUBNET configured")
            return

        try:
            self.network = ipaddress.IPv6Network(subnet, strict=False)
            self.enabled = True
            # Calcular cuántas IPs disponibles (limitar a 2^32 para evitar overflow)
            self.num_addresses = min(self.network.num_addresses, 2**32)
            print(f"[INFO] IPv6 rotation enabled - Subnet: {subnet}")
            print(f"[INFO] Available IPs: {self.num_addresses:,}")
        except Exception as e:
            self.enabled = False
            self.network = None
            print(f"[WARN] Invalid IPv6 subnet: {e}")

    def get_random_ip(self):
        """Genera una IP IPv6 aleatoria del rango"""
        if not self.enabled:
            return None

        # Generar offset aleatorio
        offset = random.randint(0, self.num_addresses - 1)

        # Obtener IP en esa posición
        random_ip = str(self.network.network_address + offset)

        return random_ip

    def get_random_ips(self, count=10):
        """Genera múltiples IPs IPv6 aleatorias únicas"""
        if not self.enabled:
            return []

        ips = set()
        max_attempts = count * 10  # Evitar loop infinito
        attempts = 0

        while len(ips) < count and attempts < max_attempts:
            ip = self.get_random_ip()
            if ip:
                ips.add(ip)
            attempts += 1

        return list(ips)

    def is_available(self):
        """Verifica si la rotación IPv6 está disponible"""
        return self.enabled


def test_ipv6_rotation():
    """Función de prueba"""
    print("=== Test IPv6 Rotation ===\n")

    # Test con subnet de ejemplo (usa tu subnet real)
    rotator = IPv6Rotator("2001:db8::/64")

    if rotator.is_available():
        print("Generando 5 IPs IPv6 aleatorias:")
        for i, ip in enumerate(rotator.get_random_ips(5), 1):
            print(f"  {i}. {ip}")
    else:
        print("IPv6 rotation not available")


if __name__ == "__main__":
    test_ipv6_rotation()
