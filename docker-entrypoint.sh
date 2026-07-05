#!/bin/sh
set -eu

python - <<'PY'
import os
import time

import psycopg2

config = {
    "dbname": os.environ.get("POSTGRES_DB", "etek_db"),
    "user": os.environ.get("POSTGRES_USER", "postgres"),
    "password": os.environ.get("POSTGRES_PASSWORD", ""),
    "host": os.environ.get("POSTGRES_HOST", "db"),
    "port": os.environ.get("POSTGRES_PORT", "5432"),
}

last_error = None
for attempt in range(1, 61):
    try:
        conn = psycopg2.connect(**config)
        conn.close()
        print("Database is ready.")
        break
    except Exception as exc:
        last_error = exc
        print(f"Waiting for database ({attempt}/60): {exc}")
        time.sleep(1)
else:
    raise SystemExit(f"Database is not ready: {last_error}")
PY

python manage.py migrate --noinput

mkdir -p /app/media
if [ -d /app/initial_media ] && [ -z "$(find /app/media -mindepth 1 -print -quit 2>/dev/null)" ]; then
    echo "Copying bundled media files..."
    cp -a /app/initial_media/. /app/media/
fi

python - <<'PY'
from pathlib import Path

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "etek_core.settings")

import django

django.setup()

from django.core.management import call_command
from store.models import Category, Product

fixture_path = Path("/app/fixtures/initial_data.json")

if fixture_path.exists():
    if Category.objects.exists() or Product.objects.exists():
        print("Demo data already exists. Skipping fixture import.")
    else:
        print(f"Loading demo data from {fixture_path}...")
        call_command("loaddata", str(fixture_path))
else:
    print("No demo fixture found. Skipping fixture import.")
PY

python manage.py seed_recommendation_metadata

python manage.py seed_default_scheduled_tasks

python - <<'PY'
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "etek_core.settings")

import django

django.setup()

from django.contrib.auth import get_user_model

username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "Admin@123456")

User = get_user_model()
user, created = User.objects.get_or_create(username=username, defaults={"email": email})
user.email = email
user.is_staff = True
user.is_superuser = True
user.set_password(password)
user.save()

if created:
    print(f"Created admin user: {username}")
else:
    print(f"Updated admin user: {username}")
PY

exec python manage.py runserver 0.0.0.0:8000