# Запуск через Docker

Из корня монорепозитория (`neomarket/`):

```bash
docker compose build
docker compose up
```

- **B2C (витрина):** http://127.0.0.1:8000  
- **B2B (каталог API):** http://127.0.0.1:8001  

Один контейнер **PostgreSQL**; при первом старте создаются БД `b2b` и `neomarket` (см. `docker/postgres/init-databases.sql`).

Переменные по умолчанию заданы в `docker-compose.yml`. Для продакшена задайте свои пароли и ключи через `environment` или файл `.env` для Compose.

Остановка: `Ctrl+C` или `docker compose down`. Данные БД сохраняются в volume `pgdata`.

## Демо-данные каталога (B2B)

После первого `docker compose up` база пустая. Чтобы у ревьюеров совпадало наполнение с демо-сценарием:

```bash
docker compose exec b2b python manage.py seed_demo
```

Или из корня репозитория: `./scripts/seed-docker-databases.sh` (Unix) / `powershell -File scripts/seed-docker-databases.ps1` (Windows).

Создаются категории **Электроника → Смартфоны**, демо-продавец (**demo-seller@neomarket.local** / **demo-demo-demo**) и товар **MODERATED** с двумя SKU (один со скидкой). Повторный запуск обновляет те же записи.
