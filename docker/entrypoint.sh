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

# 「지금 수집」·러너 후보 제출이 요청 안에서 동기 네트워크를 돌아 기본 30초를 넘길 수 있다.
# 0은 타임아웃 해제라 금지.
# 접근 로그는 표준출력으로 보낸다. 포맷은 쿼리 문자열을 남기지 않는다
# (%(U)s는 경로만, 전체 요청 라인 %(r)s나 쿼리 문자열 %(q)s는 쓰지 않음).
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    --access-logfile - \
    --access-logformat '%(h)s %(t)s "%(m)s %(U)s" %(s)s %(b)s "%(a)s"'
