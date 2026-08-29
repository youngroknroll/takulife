#!/bin/sh
set -e

if [ "${RUN_DB_MIGRATIONS:-true}" = "true" ]; then
    python manage.py migrate --noinput
else
    echo "RUN_DB_MIGRATIONS=false — skipping migrate (run it once via the PaaS release phase instead)"
fi
# collectstatic이 매니페스트에 담기 전에 셸 CSS 번들을 먼저 만들어 둔다.
python manage.py bundle_shell_css --output static/css/dist/shell.css
python manage.py collectstatic --noinput

exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-3}"
