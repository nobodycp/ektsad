#!/bin/sh
set -eu

python manage.py migrate --noinput
python manage.py bootstrap
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}"
