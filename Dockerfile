# Dockerfile
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=2.1.4 \
    POETRY_VIRTUALENVS_CREATE=false

# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential gcc libpq-dev \
#  && rm -rf /var/lib/apt/lists/*

# Instala Poetry sem depender de curl
RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app
COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-root --no-interaction --no-ansi
RUN poetry run python manage.py migrate

COPY . .
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
