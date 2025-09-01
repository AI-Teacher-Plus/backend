# Dockerfile
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=2.1.4 \
    POETRY_VIRTUALENVS_CREATE=false

# deps de sistema (psycopg2, build, etc.): não obrigatório por enquanto
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential libpq-dev && \
#     rm -rf /var/lib/apt/lists/*

# instala Poetry (version pin)
RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

# 1) cache de deps
COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-root --no-interaction --no-ansi

# 2) agora o código (manage.py incluso)
COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]
