#!/bin/sh
set -eu

python manage.py migrate --noinput
python manage.py bootstrap
python manage.py register_telegram_webhook
python manage.py run_telegram_outbox &
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}"
