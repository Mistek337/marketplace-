# Запуск через Docker



- **B2C :** http://127.0.0.1:8000  
- **B2B :** http://127.0.0.1:8001  


## Демо-данные каталога (B2B)



```bash
docker compose exec b2b python manage.py seed_demo
```

Или из корня репозитория: `./scripts/seed-docker-databases.sh` (Unix) / `powershell -File scripts/seed-docker-databases.ps1` (Windows).

Создаются категории **Электроника → Смартфоны**, демо-продавец (**demo-seller@neomarket.local** / **demo-demo-demo**) и товар **MODERATED** с двумя SKU (один со скидкой). Повторный запуск обновляет те же записи.
