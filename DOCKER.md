# Запуск через Docker



- **B2C :** http://127.0.0.1:8000  
- **B2B :** http://127.0.0.1:8001  
- **Moderation :** http://127.0.0.1:8002  
вот ссылка на витрину  http://127.0.0.1:8000/catalog/

## Демо-данные каталога (B2B)



```bash
docker compose exec b2b python manage.py seed_demo
```

Или из корня репозитория: `./scripts/seed-docker-databases.sh` (Unix) / `powershell -File scripts/seed-docker-databases.ps1` (Windows).

Создаются категории **Электроника → Смартфоны**, демо-продавец (**demo-seller@neomarket.local** / **demo-demo-demo**) и товар **MODERATED** с двумя SKU (один со скидкой). Повторный запуск обновляет те же записи.

## Moderation: ошибка pip / SSL при сборке

Docker внутри контейнера часто не достучится до PyPI (`SSLEOFError`, таймаут) — это сеть/VPN/антивирус/Docker Desktop, не код проекта.

### Вариант A (проще всего): зависимости из образа b2b

Если **b2b** уже собирается, moderation можно собрать **без pip**:

```powershell
docker compose build b2b
docker build -f moderation/Dockerfile.reuse-b2b -t neomarket-moderation ./moderation
docker compose up -d moderation
```

### Вариант B: колёса на хосте

Когда pip на Windows работает:

```powershell
powershell -File moderation/scripts/download-wheels.ps1
docker compose build moderation
```

Колёса: `moderation/docker/wheels/` (в git не коммитятся).

### Вариант C: починить сеть Docker

- выключить VPN / другой DNS (в Docker Desktop: DNS `8.8.8.8`)
- отключить HTTPS-сканирование в антивирусе для Docker
- перезапустить Docker Desktop
