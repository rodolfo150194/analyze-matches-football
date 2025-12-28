#!/bin/bash
# Script para verificar IPv6 en VPS y generar configuración

echo "=== Verificación de IPv6 en VPS ==="
echo ""

# 1. Verificar si IPv6 está habilitado
echo "[1] Verificando si IPv6 está habilitado..."
if ip -6 addr show | grep -q "inet6"; then
    echo "✓ IPv6 está habilitado"
else
    echo "✗ IPv6 NO está habilitado"
    exit 1
fi

echo ""

# 2. Mostrar direcciones IPv6 asignadas
echo "[2] Direcciones IPv6 disponibles:"
ip -6 addr show | grep "inet6" | grep -v "::1" | grep -v "fe80"

echo ""

# 3. Mostrar el rango IPv6 principal
echo "[3] Rango IPv6 principal:"
ip -6 addr show | grep "inet6" | grep -v "::1" | grep -v "fe80" | head -1

echo ""

# 4. Probar conectividad IPv6
echo "[4] Probando conectividad IPv6..."
if ping6 -c 1 google.com >/dev/null 2>&1; then
    echo "✓ Conectividad IPv6 funcionando"
else
    echo "✗ Sin conectividad IPv6"
fi

echo ""

# 5. Verificar rango asignado por el proveedor
echo "[5] Para usar rotación IPv6, necesitas:"
echo "   - Consultar con Hostinger el rango IPv6 completo asignado (/64 o /48)"
echo "   - Ejemplo: 2a01:4f8:1234:5678::/64 te da ~18 quintillones de IPs"

echo ""
echo "=== Instrucciones ==="
echo "1. Contacta a Hostinger para obtener tu rango IPv6 completo"
echo "2. Añade el rango a .env como: IPV6_SUBNET=2a01:4f8:xxxx:xxxx::/64"
echo "3. El script rotará automáticamente entre IPs de ese rango"
