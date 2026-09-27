# Dogfood Platform

A 100% self-hosted hackathon submission and judging platform built with Django, Django REST Framework, PostgreSQL, and Docker.

---

## Architecture & Roadmap

- **Phase 1: Foundation** (Completed): Docker Compose, PostgreSQL 16, Django 5 skeleton, and app scaffolding.
- **Phase 2: Authentication & RBAC** (Completed): Custom User model with roles, signup, login/logout, role-based dashboards, reusable `@role_required` decorator, and Django Admin role management.
- **Phase 3: Events & Hackathon Lifecycles** (Current): Event, Track, and Prize models, inline formsets, draft visibility rules, core date editing protection, and deadline enforcement utilities.
- **Phase 4**: Teams & Membership (Upcoming)
- **Phase 5**: Project Submissions & Media (Upcoming)
- **Phase 6**: Public Gallery & Judging (Upcoming)

---

## Phase 3: Event Management

### Models & Schema (`apps/events/models.py`)
- **`Event`**:
  - `name`, `slug` (auto-generated unique slug), `description`
  - `start_date`, `end_date`, `registration_deadline`, `submission_deadline`
  - `status`: `draft`, `open`, `closed` (default: `draft`)
  - `gallery_enabled`: Boolean flag for public project showcase
  - `created_by`: ForeignKey to custom User model (`on_delete=PROTECT`)
- **`Track`**: Sub-theme/category under an event (`name`, `description`).
- **`Prize`**: Rank-ordered awards (`title`, `description`, `rank`).

### Access Control & Rules
1. **Creation & Editing (`/events/create/`, `/events/<slug>/edit/`)**:
   - Protected with `@role_required('organizer', 'admin')`.
   - Creation supports adding multiple tracks and prizes simultaneously via inline formsets.
   - Core dates (`start_date`, `submission_deadline`) cannot be modified after an event is set to `open` and `start_date` has arrived. Server-side validation errors are returned.
2. **Draft Visibility Rules**:
   - **Public Listing (`/events/`)**: Displays all `open` and `closed` events to all visitors. Events with status `draft` are strictly filtered in the database queryset and visible ONLY to the creator organizer or platform administrators.
   - **Event Detail (`/events/<slug>/`)**: Non-owner, non-admin visitors (including anonymous users and participants) attempting to access a draft event URL receive **HTTP 404 Not Found**.
3. **Deadline Enforcement Utility**:
   - Helper properties on `Event`:
     - `event.is_registration_open`: Returns `True` if `status == 'open'` and current time &le; `registration_deadline`.
     - `event.is_submission_open`: Returns `True` if `status == 'open'` and current time &le; `submission_deadline`.
   - Used server-side across Phase 4 (teams) and Phase 5 (submissions) to reject submissions and registrations after deadlines expire.

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
│   ├── events/            # Events, tracks, prizes, formsets, and lifecycle management
│   ├── teams/             # Teams app scaffold (Phase 4)
│   ├── submissions/       # Submissions app scaffold (Phase 5)
│   └── gallery/           # Gallery app scaffold (Phase 6)
├── templates/             # HTML templates (accounts, events, base)
├── static/                # Static asset files
└── tests/                 # Integration test suites
```

---

## Quickstart

### Running with Docker Compose
```bash
docker compose up --build
```

### Running Locally without Docker
```powershell
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py runserver 0.0.0.0:8000
```

---

## Phase 3 Verification Guide

### 1. Test Event Creation as an Organizer
1. Log in as an **Organizer** (or register one at [http://localhost:8000/signup/](http://localhost:8000/signup/)).
2. Navigate to **[http://localhost:8000/events/create/](http://localhost:8000/events/create/)** (or click **+ Create Event** in the header).
3. Fill in the event details:
   - **Name**: `Global AI Hackathon 2026`
   - **Description**: `Building next-generation autonomous software agents.`
   - **Status**: `Draft` (or `Open`)
   - **Start Date / End Date**: Set future dates.
   - **Registration / Submission Deadlines**: Set cutoff dates.
   - **Tracks (Formset)**:
     - Track 1: `Agentic Workflows`
     - Track 2: `Developer Tooling`
   - **Prizes (Formset)**:
     - Prize 1: Rank `1` | Title `1st Place` | Description `₹1,00,000`
     - Prize 2: Rank `2` | Title `2nd Place` | Description `₹50,000`
4. Click **Create Event**. You will be redirected to the event detail page displaying all tracks, prizes, and deadline statuses.

### 2. Verify Draft Visibility Rules
1. Create an event with status set to **`Draft`** while logged in as Organizer A.
2. Notice the event appears in Organizer A's listing at `/events/` with a yellow **DRAFT** badge.
3. Open an Incognito / Private browser window (or log out):
   - Navigate to `/events/`. The draft event **does NOT appear**.
   - Attempt to access the draft event detail URL directly (`/events/<slug>/`). You receive **HTTP 404 Not Found**.
4. Log in as a **Participant** in the second browser:
   - The draft event **does NOT appear** in `/events/`.
   - Accessing `/events/<slug>/` directly returns **HTTP 404 Not Found**.
5. Log in as an **Admin**:
   - The draft event **is visible** in `/events/` and the detail page returns **HTTP 200 OK**.

### 3. Verify RBAC Protection on Event Creation
1. While logged in as a **Participant**, attempt to visit `/events/create/`.
2. **Expected result**: **HTTP 403 Forbidden** (Access Denied).

### 4. Verify Core Date Editing Protection
1. Open an existing event whose status is `Open` and whose `start_date` has passed.
2. Attempt to edit the event at `/events/<slug>/edit/` and change `start_date` or `submission_deadline`.
3. **Expected result**: Validation errors are displayed:
   - `Cannot modify start date after the event has opened and started.`
   - `Cannot modify submission deadline after the event has opened and started.`

### 5. Run Automated Tests
Execute the full automated test suite (25 tests covering Phase 1, Phase 2, and Phase 3):
```powershell
.\.venv\Scripts\python manage.py test
```
**Expected Output:**
```text
Ran 25 tests in 43.153s

OK
```