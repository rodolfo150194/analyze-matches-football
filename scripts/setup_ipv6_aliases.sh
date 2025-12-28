#!/bin/bash
# Script para configurar aliases IPv6 en VPS (Ubuntu/Debian)
# Esto permite usar múltiples IPs IPv6 del rango asignado

set -e

echo "=== Configuración de aliases IPv6 ==="
echo ""

# Verificar si se ejecuta como root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Este script debe ejecutarse como root"
    echo "Usa: sudo bash $0"
    exit 1
fi

# Leer subnet de .env o solicitar al usuario
if [ -f "../.env" ]; then
    SUBNET=$(grep IPV6_SUBNET ../.env | cut -d '=' -f2)
fi

if [ -z "$SUBNET" ]; then
    echo "Introduce tu rango IPv6 (ejemplo: 2a01:4f8:1234:5678::/64):"
    read SUBNET
fi

echo "Rango IPv6: $SUBNET"
echo ""

# Detectar interfaz de red principal
INTERFACE=$(ip -6 route | grep default | awk '{print $5}' | head -1)

if [ -z "$INTERFACE" ]; then
    echo "ERROR: No se pudo detectar la interfaz de red"
    echo "Interfaces disponibles:"
    ip link show
    exit 1
fi

echo "Interfaz detectada: $INTERFACE"
echo ""

# Preguntar cuántas IPs configurar
echo "¿Cuántas IPs IPv6 quieres configurar? (recomendado: 10-50)"
read NUM_IPS

if [ -z "$NUM_IPS" ]; then
    NUM_IPS=20
fi

echo "Configurando $NUM_IPS aliases IPv6..."
echo ""

# Extraer prefijo (primeros 64 bits)
PREFIX=$(echo $SUBNET | cut -d '/' -f1 | cut -d ':' -f1-4)

# Generar y configurar IPs aleatorias
echo "Generando IPs aleatorias..."

for i in $(seq 1 $NUM_IPS); do
    # Generar sufijo aleatorio (últimos 64 bits)
    SUFFIX=$(printf "%04x:%04x:%04x:%04x" $RANDOM $RANDOM $RANDOM $RANDOM)

    IPV6="${PREFIX}:${SUFFIX}"

    # Añadir IP a la interfaz
    ip -6 addr add ${IPV6}/64 dev $INTERFACE

    echo "  [$i/$NUM_IPS] Configurado: $IPV6"
done

echo ""
echo "✓ Configuración completada!"
echo ""

# Verificar
echo "IPs IPv6 configuradas en $INTERFACE:"
ip -6 addr show $INTERFACE | grep "inet6" | grep -v "fe80" | head -5
echo "... (total: $NUM_IPS)"

echo ""
echo "IMPORTANTE: Esta configuración se perderá al reiniciar."
echo "Para hacerla permanente, añade a /etc/network/interfaces:"
echo ""
echo "iface $INTERFACE inet6 static"
for i in $(seq 1 5); do
    SUFFIX=$(printf "%04x:%04x:%04x:%04x" $RANDOM $RANDOM $RANDOM $RANDOM)
    echo "  up ip -6 addr add ${PREFIX}:${SUFFIX}/64 dev $INTERFACE"
done
echo "  ..."

echo ""
echo "=== Testing ==="
echo "Probando conectividad con diferentes IPs:"

# Probar 3 IPs aleatorias
ip -6 addr show $INTERFACE | grep "inet6" | grep -v "fe80" | head -3 | while read line; do
    TEST_IP=$(echo $line | awk '{print $2}' | cut -d '/' -f1)
    echo -n "Testing $TEST_IP ... "
    if curl -6 --interface $TEST_IP --max-time 5 -s https://ifconfig.co >/dev/null 2>&1; then
        echo "✓ OK"
    else
        echo "✗ FAILED"
    fi
done
