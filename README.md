# Dogfood Platform

A 100% self-hosted hackathon submission and judging platform built with Django, Django REST Framework, PostgreSQL, and Docker.

---

## Architecture & Roadmap

- **Phase 1: Foundation** (Completed): Docker Compose, PostgreSQL 16, Django 5 skeleton, and app scaffolding.
- **Phase 2: Authentication & RBAC** (Current): Custom User model with roles, signup, login/logout, role-based dashboards, reusable `@role_required` decorator, and Django Admin role management.
- **Phase 3**: Events & Hackathon Lifecycles (Upcoming)
- **Phase 4**: Teams & Membership (Upcoming)
- **Phase 5**: Project Submissions & Media (Upcoming)
- **Phase 6**: Public Gallery & Judging (Upcoming)

---

## Phase 2: Auth & Role-Based Access Control

### Platform Roles
- **Participant** (`participant`): Standard user submitting projects and joining teams (Default at signup).
- **Judge** (`judge`): Evaluator scoring submissions.
- **Organizer** (`organizer`): Manages hackathons, timelines, and tracks.
- **Admin** (`admin`): Full platform administrator (promoted exclusively via Django Admin or superuser).

### Access Control Utility
Views and APIs are protected via reusable access control utilities in `apps/accounts/`:
- **Django Views Decorator**: `@role_required('organizer', 'admin')`
  - Unauthenticated users are redirected to login.
  - Authenticated users with invalid roles receive **HTTP 403 Forbidden**.
- **DRF Permission Class**: `HasRole` with `allowed_roles = [...]`.

---

## Project Structure

```text
.
├── docker-compose.yml     # Compose config for web and db services
├── Dockerfile             # Python 3.12-slim container definition
├── entrypoint.sh          # Database wait loop, migration, superuser, and server boot script
├── .env.example           # Template for environment variables
├── requirements.txt       # Core dependencies (Django, DRF, psycopg2, django-environ)
├── manage.py              # Django management utility
├── config/                # Django project settings and root routing
├── apps/                  # Modular application domain packages
│   ├── accounts/          # Custom User model, auth views, RBAC decorators & admin
│   ├── events/            # Events app scaffold
│   ├── teams/             # Teams app scaffold
│   ├── submissions/       # Submissions app scaffold
│   └── gallery/           # Gallery app scaffold
├── templates/             # HTML templates (base, signup, login, dashboard)
├── static/                # Static asset files
└── tests/                 # Integration test suites
```

---

## Quickstart with Docker Compose

### 1. Start the Platform
```bash
docker compose up --build
```

Compose automatically:
1. Builds the `web` container.
2. Boots PostgreSQL 16 and waits for health check (`pg_isready`).
3. Runs database migrations (`python manage.py migrate`).
4. Serves the web application at [http://localhost:8000](http://localhost:8000).

---

## Manual Verification Guide (Phase 2)

### Step 1: Create a Superuser
Run the standard Django createsuperuser command:
```bash
docker compose exec web python manage.py createsuperuser
```
Follow prompts to enter username (e.g. `admin`), email, and password. Superusers automatically receive the `admin` role.

### Step 2: Test User Signup & Role Dashboards
1. Open [http://localhost:8000/signup/](http://localhost:8000/signup/).
2. Register a new user choosing role **Participant** (e.g. `alice`).
   - You are logged in automatically and redirected to `/dashboard/participant/`.
3. Log out via [http://localhost:8000/logout/](http://localhost:8000/logout/).
4. Register another user choosing role **Organizer** (e.g. `bob`).
   - You are redirected to `/dashboard/organizer/`.
5. Register a third user choosing role **Judge** (e.g. `carol`).
   - You are redirected to `/dashboard/judge/`.

### Step 3: Verify 403 Forbidden Access Control
1. Log in as the participant (`alice`).
2. Attempt to navigate directly to the Organizer dashboard:
   ```
   http://localhost:8000/dashboard/organizer/
   ```
3. **Expected result**: HTTP 403 Forbidden (Access Denied).
4. Attempt to navigate directly to the Judge dashboard:
   ```
   http://localhost:8000/dashboard/judge/
   ```
5. **Expected result**: HTTP 403 Forbidden (Access Denied).

### Step 4: Verify Django Admin Role Management
1. Log in as the superuser at [http://localhost:8000/admin/](http://localhost:8000/admin/).
2. Under **Accounts > Users**, view all registered users. Notice the **Role** column in the user table.
3. Click on user `alice`. In the **Platform Role Management** section, change her role from `Participant` to `Organizer` and click **Save**.
4. Log out of admin, log back in as `alice`, and navigate to [http://localhost:8000/dashboard/organizer/](http://localhost:8000/dashboard/organizer/).
5. **Expected result**: HTTP 200 OK — `alice` now has access to the organizer dashboard.

### Step 5: Run Automated Tests
Execute the full test suite:
```bash
docker compose exec web python manage.py test
```
All unit and RBAC tests will pass.