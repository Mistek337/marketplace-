# Наполнить БД B2B демо-каталогом (из корня neomarket\, контейнеры уже up).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
docker compose exec -T b2b python manage.py seed_demo
