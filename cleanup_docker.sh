#!/bin/bash

# Script de limpieza de Docker para liberar espacio en el VPS

echo "=========================================="
echo "LIMPIEZA DE DOCKER"
echo "=========================================="

# 1. Detener todos los contenedores
echo ""
echo "[1/7] Deteniendo contenedores..."
docker-compose down

# 2. Eliminar contenedores detenidos
echo ""
echo "[2/7] Eliminando contenedores detenidos..."
docker container prune -f

# 3. Eliminar imágenes sin usar (dangling)
echo ""
echo "[3/7] Eliminando imágenes dangling..."
docker image prune -f

# 4. Eliminar todas las imágenes sin usar (CUIDADO: elimina todo lo que no esté en uso)
echo ""
echo "[4/7] Eliminando imágenes sin usar..."
docker image prune -a -f

# 5. Eliminar volúmenes sin usar
echo ""
echo "[5/7] Eliminando volúmenes sin usar..."
docker volume prune -f

# 6. Eliminar redes sin usar
echo ""
echo "[6/7] Eliminando redes sin usar..."
docker network prune -f

# 7. Limpieza completa del sistema (libera más espacio)
echo ""
echo "[7/7] Limpieza completa del sistema Docker..."
docker system prune -a -f --volumes

# Mostrar espacio liberado
echo ""
echo "=========================================="
echo "LIMPIEZA COMPLETADA"
echo "=========================================="
echo ""
echo "Uso de disco Docker:"
docker system df

echo ""
echo "Reconstruye la imagen con:"
echo "  docker-compose up -d --build"
