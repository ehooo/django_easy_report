#!/usr/bin/env bash
if ! test -f "db.sqlite3"; then
  echo "Create migrations"
  python manage.py makemigrations
  echo "Apply migrations"
  python manage.py migrate
  echo "Load basic data"
  python manage.py loaddata basic_data
  echo "Create Admin account"
  DJANGO_SUPERUSER_PASSWORD=1234 python manage.py createsuperuser --username=admin --email="admin@localhost" --skip-checks --noinput
fi
python manage.py runserver 0.0.0.0:8000
