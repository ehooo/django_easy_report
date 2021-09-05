#!/usr/bin/env sh
if ! test -f "db.sqlite3"; then
  python manage.py makemigrations
  python manage.py migrate
  python manage.py loaddata initial_data
  DJANGO_SUPERUSER_PASSWORD=1234 python manage.py createsuperuser --username=admin --email="admin@localhost" --skip-checks --noinput
fi
python manage.py runserver 0.0.0.0:8000
