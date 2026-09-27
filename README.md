# Dogfood Platform - Phase 1: Foundation

A 100% self-hosted hackathon submission and judging platform built with Django, Django REST Framework, PostgreSQL, and Docker.

---

## Architecture Overview (Phase 1)

This repository contains the Phase 1 foundation scaffold:
- **Django 5.x** core project configuration in `config/`
- **Django REST Framework** integration
- **Domain App Scaffolds** in `apps/`:
  - `accounts`: User roles and profiles (Participant, Judge, Organizer, Admin)
  - `events`: Hackathons, timelines, rules, tracks
  - `teams`: Team formation, membership, and invitations
  - `submissions`: Project submissions, links, media, and metadata
  - `gallery`: Public showcase and discovery
- **PostgreSQL 16** containerized database with named volume persistence
- **Docker Compose** orchestration with database health checks and automatic migrations

---

## Project Structure

```text
.
├── docker-compose.yml     # Compose config for web and db services
├── Dockerfile             # Python 3.12-slim container definition
├── entrypoint.sh          # Database wait loop, migration, and server boot script
├── .env.example           # Template for environment variables
├── requirements.txt       # Core dependencies (Django, DRF, psycopg2, django-environ)
├── manage.py              # Django management utility
├── config/                # Django project settings and root routing
├── apps/                  # Modular application domain packages
│   ├── accounts/
│   ├── events/
│   ├── teams/
│   ├── submissions/
│   └── gallery/
├── templates/             # Project-level HTML templates
├── static/                # Static asset files (CSS, JS, images)
└── tests/                 # Foundation smoke and integration tests
```

---

## Getting Started

### Prerequisites
- [Docker Engine & Docker Compose](https://docs.docker.com/get-docker/)

### 1. Clone the repository
```bash
git clone https://github.com/kit2824bad054/Dogfood-Hackaton.git
cd Dogfood-Hackaton
```

### 2. Configure Environment (Optional for local dev)
Defaults are pre-configured in `docker-compose.yml` and `config/settings.py` for instant local development. To customize settings:
```bash
cp .env.example .env
```

### 3. Start the Platform
Run:
```bash
docker compose up --build
```

Compose will:
1. Build the Python 3.12 `web` container.
2. Launch PostgreSQL 16 `db` service and verify health via `pg_isready`.
3. Wait for PostgreSQL to be healthy before starting `web`.
4. Run Django's database migrations (`python manage.py migrate`).
5. Launch the Django server at [http://localhost:8000](http://localhost:8000).

---

## Verification

1. **Verify Web Service**: Open [http://localhost:8000](http://localhost:8000) in your browser. You will see Django's default welcome page ("The install worked successfully!").
2. **Verify Database Health**:
   ```bash
   docker compose ps
   ```
   Both `web` and `db` will show `Up` (with `db` showing `healthy`).
3. **Run Smoke Tests**:
   ```bash
   docker compose exec web python manage.py test
   ```
   All tests will pass without errors.