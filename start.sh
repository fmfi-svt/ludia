#!/bin/bash
set -euo pipefail

env="${1:-prod}"

python manage.py wait_for_database

python manage.py migrate

if [ "$env" = "dev" ]; then
  exec python manage.py runserver 0.0.0.0:8000
else
  exec /base/gunicorn.sh ludia.wsgi
fi
