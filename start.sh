#!/bin/bash
set -e # Exit on any error

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Starting Celery worker in background..."
celery -A config worker --loglevel=info &

echo "Starting Gunicorn server..."
gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}

