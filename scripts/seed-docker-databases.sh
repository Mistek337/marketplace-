#!/usr/bin/env sh
# Наполнить БД B2B демо-каталогом (из корня neomarket/, контейнеры уже up).
set -e
cd "$(dirname "$0")/.."
docker compose exec -T b2b python manage.py seed_demo
