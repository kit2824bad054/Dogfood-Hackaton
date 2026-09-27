#!/bin/sh
set -e

DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-dogfood_user}"
DB_NAME="${DB_NAME:-dogfood}"

echo "Waiting for PostgreSQL to be ready at ${DB_HOST}:${DB_PORT}..."

if command -v pg_isready > /dev/null 2>&1; then
    while ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; do
        echo "PostgreSQL is not ready yet - sleeping 1s"
        sleep 1
    done
else
    until nc -z -v -w30 "$DB_HOST" "$DB_PORT" > /dev/null 2>&1; do
        echo "Waiting for database connection at ${DB_HOST}:${DB_PORT}..."
        sleep 1
    done
fi

echo "PostgreSQL is ready and accepting connections!"

# Run migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

# Seed demo data automatically
echo "Seeding demo hackathons, accounts, teams, and submissions..."
python manage.py seed_demo_data

# Optionally create superuser if env vars are present
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "Creating superuser '$DJANGO_SUPERUSER_USERNAME'..."
    python manage.py createsuperuser --noinput || true
fi

# Start Django development server
echo "Starting Django development server on 0.0.0.0:8000..."
exec python manage.py runserver 0.0.0.0:8000
