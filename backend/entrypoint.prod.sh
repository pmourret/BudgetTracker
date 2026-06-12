#!/bin/sh
set -e

echo "→ Migrations"
python manage.py migrate --noinput

echo "→ Collectstatic"
python manage.py collectstatic --noinput

echo "→ Référentiels structurels (idempotent)"
python manage.py seed_referentiels

echo "→ Gunicorn"
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 60
