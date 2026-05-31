FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc gunicorn \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY docker/wheels/ /wheels/
RUN if ls /wheels/*.whl >/dev/null 2>&1 || ls /wheels/*.tar.gz >/dev/null 2>&1; then \
        echo "Installing Python deps from local wheels (offline)..."; \
        pip install --no-index --find-links=/wheels --no-cache-dir -r requirements.txt; \
    else \
        echo "No wheels in moderation/docker/wheels — installing from PyPI..."; \
        pip install --no-cache-dir --default-timeout=300 --retries=20 -r requirements.txt; \
    fi

COPY . .

EXPOSE 8002

CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn moderation.wsgi:application --bind 0.0.0.0:8002 --workers 2"]
