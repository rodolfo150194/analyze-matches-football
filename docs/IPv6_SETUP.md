# Configuración IPv6 para Rotación de IPs en VPS

## ¿Por qué usar IPv6?

- **Millones de IPs disponibles**: Un rango /64 te da ~18 quintillones de IPs
- **Evita rate limiting**: Rotas entre diferentes IPs para parecer usuarios diferentes
- **Gratis con VPS**: Hostinger y otros proveedores incluyen IPv6
- **Más difícil de bloquear**: Los sitios raramente bloquean rangos IPv6 completos

## Paso 1: Verificar IPv6 en tu VPS

```bash
# SSH a tu VPS Hostinger
ssh user@your-vps-ip

# Verificar IPv6
bash scripts/check_ipv6.sh
```

**Salida esperada:**
```
✓ IPv6 está habilitado
Direcciones IPv6 disponibles:
inet6 2a01:4f8:xxxx:xxxx::1/64 scope global
```

## Paso 2: Obtener tu rango IPv6 completo

### Opción A: Consultar a Hostinger

1. Abre ticket de soporte: https://hpanel.hostinger.com/
2. Pregunta: "¿Cuál es mi rango IPv6 completo asignado? (prefijo /64 o /48)"
3. Te darán algo como: `2a01:4f8:1234:5678::/64`

### Opción B: Detectar automáticamente

```bash
# Ver tu IPv6 actual
ip -6 addr show | grep inet6 | grep -v "::1" | grep -v "fe80"

# Verificar tu IPv6 pública
curl -6 ifconfig.co
```

La mayoría de VPS tienen un `/64` que te da **18,446,744,073,709,551,616 IPs únicas**.

## Paso 3: Configurar variables de entorno

Edita tu archivo `.env`:

```bash
cd /path/to/football_django
nano .env
```

Añade:
```env
# IPv6 Configuration
IPV6_SUBNET=2a01:4f8:xxxx:xxxx::/64  # Reemplaza con tu rango real
IS_VPS=true
```

## Paso 4: Configurar aliases IPv6 en el sistema

Esto asigna múltiples IPs IPv6 a tu interfaz de red:

```bash
# Ejecutar como root
sudo bash scripts/setup_ipv6_aliases.sh
```

El script:
1. Detecta tu interfaz de red automáticamente
2. Lee tu rango IPv6 de `.env`
3. Genera 20-50 IPs aleatorias del rango
4. Las configura como aliases en la interfaz

**Ejemplo de salida:**
```
Interfaz detectada: eth0
Configurando 20 aliases IPv6...
  [1/20] Configurado: 2a01:4f8:1234:5678::a1b2:c3d4:e5f6:7890
  [2/20] Configurado: 2a01:4f8:1234:5678::1234:5678:9abc:def0
  ...
✓ Configuración completada!
```

## Paso 5: Hacer la configuración permanente

Las IPs se pierden al reiniciar. Para hacerlas permanentes:

```bash
sudo nano /etc/network/interfaces
```

Añade al final (reemplaza `eth0` con tu interfaz y `2a01:4f8:1234:5678` con tu prefijo):

```
# IPv6 aliases para rotación
iface eth0 inet6 static
    up ip -6 addr add 2a01:4f8:1234:5678::a1b2:c3d4:e5f6:7890/64 dev eth0
    up ip -6 addr add 2a01:4f8:1234:5678::1234:5678:9abc:def0/64 dev eth0
    up ip -6 addr add 2a01:4f8:1234:5678::beef:cafe:dead:feed/64 dev eth0
    # ... añade más (hasta 50)
```

O usa **netplan** (Ubuntu 18.04+):

```bash
sudo nano /etc/netplan/01-netcfg.yaml
```

```yaml
network:
  version: 2
  ethernets:
    eth0:
      addresses:
        - 2a01:4f8:1234:5678::1/64
        - 2a01:4f8:1234:5678::a1b2:c3d4:e5f6:7890/64
        - 2a01:4f8:1234:5678::1234:5678:9abc:def0/64
        # ... más IPs
      gateway6: fe80::1
```

```bash
sudo netplan apply
```

## Paso 6: Verificar que funciona

```bash
# Test Python
python manage.py shell
```

```python
from predictions.ipv6_rotator import IPv6Rotator

# Inicializar
rotator = IPv6Rotator()

# Verificar
if rotator.is_available():
    print("✓ IPv6 rotation enabled!")

    # Generar 5 IPs aleatorias
    ips = rotator.get_random_ips(5)
    for ip in ips:
        print(f"  - {ip}")
else:
    print("✗ IPv6 rotation disabled")
```

**Test con curl:**

```bash
# Probar cada IP configurada
ip -6 addr show eth0 | grep "inet6" | grep -v "fe80" | while read line; do
    IP=$(echo $line | awk '{print $2}' | cut -d '/' -f1)
    echo "Testing $IP:"
    curl -6 --interface $IP https://ifconfig.co
    echo ""
done
```

Deberías ver IPs diferentes en cada request.

## Paso 7: Usar en SofaScore scraping

### Opción A: Usar versión IPv6 (recomendado)

```python
from predictions.sofascore_api_ipv6 import SofascoreAPIv6

api = SofascoreAPIv6(delay_min=5, delay_max=10)
teams = api.get_season_teams(17, 52760)  # Premier League 2024
```

### Opción B: Modificar comando de importación

El comando `import_sofascore_complete` detectará automáticamente IPv6 si:
- `IPV6_SUBNET` está configurado en `.env`
- El módulo `ipv6_rotator` está disponible

## Ventajas de este método

✓ **Gratis**: No necesitas proxies pagos
✓ **Ilimitado**: Millones de IPs únicas
✓ **Rápido**: Sin latencia de proxies externos
✓ **Confiable**: Control total sobre las IPs
✓ **Difícil de bloquear**: Los sitios raramente bloquean IPv6 completos

## Troubleshooting

### "IPv6 rotation disabled"
- Verifica que `IPV6_SUBNET` esté en `.env`
- Verifica el formato: `2a01:4f8:xxxx:xxxx::/64`

### "Connection refused" o timeout
- Verifica que las IPs estén configuradas: `ip -6 addr show`
- Prueba conectividad: `ping6 google.com`
- Algunos sitios no soportan IPv6 (prueba `curl -6 https://google.com`)

### Las IPs se pierden al reiniciar
- Configura permanentemente en `/etc/network/interfaces` o netplan

### SofaScore sigue bloqueando
- Aumenta los delays: `delay_min=15, delay_max=30`
- Combina con playwright-stealth
- Usa más IPs del pool (genera 100+ en vez de 20)

## Ejemplo completo

```bash
# 1. Configuración inicial (una vez)
sudo bash scripts/setup_ipv6_aliases.sh

# 2. Añadir a .env
echo "IPV6_SUBNET=2a01:4f8:xxxx:xxxx::/64" >> .env
echo "IS_VPS=true" >> .env

# 3. Importar datos con rotación IPv6
python manage.py import_sofascore_complete \
    --competitions PL \
    --seasons 2024 \
    --teams-only

# Cada request usará una IPv6 diferente del pool!
```

## Recursos adicionales

- [IPv6 Subnet Calculator](https://www.vultr.com/resources/subnet-calculator-ipv6/)
- [Hostinger IPv6 Docs](https://support.hostinger.com/)
- [Linux IPv6 Configuration](https://tldp.org/HOWTO/Linux+IPv6-HOWTO/)
