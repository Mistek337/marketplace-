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
