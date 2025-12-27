#!/bin/bash

# Exit on error
set -e

echo "🔍 Checking environment..."
echo "DEBUG: ${DEBUG:-Not set}"
echo "ALLOWED_HOSTS: ${ALLOWED_HOSTS:-Not set}"
echo "DATABASE_URL: ${DATABASE_URL:+Set}"

echo "🗄️  Running database migrations..."
python manage.py migrate --noinput

echo "📦 Collecting static files..."
python manage.py collectstatic --noinput --clear || echo "⚠️  Static collection skipped"

echo "🚀 Starting Gunicorn..."
exec gunicorn football_django.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
