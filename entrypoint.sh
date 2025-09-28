#!/usr/bin/env bash
set -e

# Espera o Postgres usando psycopg via Python 
python - <<'PY'
import os, time
import psycopg
host=os.getenv("POSTGRES_HOST","db")
port=int(os.getenv("POSTGRES_PORT","5432"))
user=os.getenv("POSTGRES_USER","postgres")
pwd=os.getenv("POSTGRES_PASSWORD","postgres")
db=os.getenv("POSTGRES_DB","postgres")
for _ in range(60):
    try:
        with psycopg.connect(host=host, port=port, user=user, password=pwd, dbname=db, connect_timeout=3) as conn:
            break
    except Exception as e:
        time.sleep(1)
else:
    raise SystemExit("Database not ready after 60s")
PY

# Migrações
poetry run python manage.py migrate --noinput

# Sobe o servidor
exec poetry run gunicorn --bind 0.0.0.0:8000 --workers 3 setup.wsgi:application --capture-output --enable-stdio-inheritance
