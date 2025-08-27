FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.3

WORKDIR /app

# deps de sistema (opt por enquanto)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential curl libpq-dev git && rm -rf /var/lib/apt/lists/*

# poetry
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    ln -s /root/.local/bin/poetry /usr/local/bin/poetry && \
    poetry config virtualenvs.create false

# instalar deps antes de copiar o projeto (cache)
COPY pyproject.toml poetry.lock* /app/
RUN poetry install --no-interaction --no-ansi

# copiar código
COPY . /app

EXPOSE 8000

CMD ["bash", "-lc", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]
