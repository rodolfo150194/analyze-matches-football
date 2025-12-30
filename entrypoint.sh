#!/bin/sh
set -e

echo "Creating static directory if not exists..."
mkdir -p /app/staticfiles

echo "🎨 Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn..."
exec gunicorn football_django.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --threads 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
