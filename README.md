# Dogfood Platform

A 100% self-hosted hackathon submission and judging platform built with Django, Django REST Framework, PostgreSQL, and Docker.

---

## Architecture & Roadmap

- **Phase 1: Foundation** (Completed): Docker Compose, PostgreSQL 16, Django 5 skeleton, and app scaffolding.
- **Phase 2: Authentication & RBAC** (Completed): Custom User model with roles, signup, login/logout, role-based dashboards, reusable `@role_required` decorator, and Django Admin role management.
- **Phase 3: Events & Hackathon Lifecycles** (Completed): Event, Track, and Prize models, inline formsets, draft visibility rules, core date editing protection, and deadline enforcement utilities.
- **Phase 4: Team Formation & Membership** (Completed): Team and TeamMembership models, cryptographic URL-safe invite codes, capacity limits, member removal before submission deadline, and one-team-per-event application constraint.
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

## Phase 4: Team Formation & Membership

### Models & Schema (`apps/teams/models.py`)
- **`Team`**:
  - `event`: ForeignKey to `Event` (`related_name='teams'`)
  - `name`: CharField
  - `invite_code`: Unique random URL-safe token (generated via `secrets.token_urlsafe(9)`)
  - `max_members`: PositiveIntegerField (default: 4)
  - `created_by`: ForeignKey to custom User model (`on_delete=PROTECT`)
  - `created_at`: DateTimeField auto timestamp
  - `UniqueConstraint`: `(event, name)` — no two teams in the same event can share a name
  - Helper properties: `member_count`, `is_full`
- **`TeamMembership`**:
  - `team`: ForeignKey to `Team` (`related_name='memberships'`)
  - `user`: ForeignKey to custom User model (`on_delete=CASCADE`)
  - `joined_at`: DateTimeField auto timestamp
  - `UniqueConstraint`: `(team, user)` — participant cannot join the same team twice

### Validation & Business Logic
1. **One-Team-Per-Participant-Per-Event**:
   - Reusable validator: `validate_user_can_join_event_team(user, event)` in `apps.teams.models`.
   - Checks whether the user already has ANY membership in ANY team belonging to the same event.
   - Enforced consistently during both **team creation** and **invite code join**.
   - Raises a descriptive `ValidationError` ("You are already a member of team '{team.name}' in this event.").
2. **Registration Deadline Check**:
   - Both team creation and invite code joining check `event.is_registration_open`.
   - Rejects operations with a clear error message if the registration deadline has passed.
3. **Role-Based Protection**:
   - Only users with `role='participant'` can create or join teams (`@role_required('participant')`).
   - Organizers, judges, and admins are prevented from creating or joining participant teams.
4. **Capacity Enforcement**:
   - If `team.member_count >= team.max_members`, joins are rejected with an explicit HTTP 400 error.
5. **Team Management & Member Removal**:
   - Creators can remove members prior to the submission deadline (`event.is_submission_open`).
   - Rejects removal if `is_submission_open` is False.
   - Team creator cannot remove themselves.
   - Non-members cannot view management actions or remove members.

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
│   ├── teams/             # Teams, memberships, invite codes, and roster views (Phase 4)
│   ├── submissions/       # Submissions app scaffold (Phase 5)
│   └── gallery/           # Gallery app scaffold (Phase 6)
├── templates/             # HTML templates (accounts, events, teams, base)
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

---

## Phase 4 Verification & Testing Guide

### 1. Manual Step-by-Step Walkthrough

#### Step A: Create Two Participant Accounts
1. Log out or open two separate browser sessions (e.g. Regular Chrome and an Incognito window).
2. In Browser 1, visit [http://localhost:8000/signup/](http://localhost:8000/signup/) and sign up:
   - **Username**: `coder_alice`
   - **Email**: `alice@example.com`
   - **Role**: `Participant`
   - **Password**: `TestPass123!`
3. In Browser 2 (Incognito), visit [http://localhost:8000/signup/](http://localhost:8000/signup/) and sign up:
   - **Username**: `coder_bob`
   - **Email**: `bob@example.com`
   - **Role**: `Participant`
   - **Password**: `TestPass123!`

#### Step B: Create a Team as Participant 1 (`coder_alice`)
1. In Browser 1 as `coder_alice`, navigate to [http://localhost:8000/events/](http://localhost:8000/events/) and click on an open event (e.g. `Global AI Hackathon 2026`).
2. Click the **👥 My Team / Form Team** button (or visit `http://localhost:8000/events/<slug>/teams/create/`).
3. Fill in:
   - **Team Name**: `Quantum Hackers`
   - **Max Members**: `4`
4. Click **Create Team**.
5. You are redirected to the team detail page. Notice:
   - The prominent **Invite Code** and **Shareable Invite Link** with a 1-click **Copy Link** button.
   - `coder_alice` is automatically listed as the Team Creator and Member #1.

#### Step C: Join the Team via Invite Code as Participant 2 (`coder_bob`)
1. Copy the invite link from Browser 1 (e.g. `http://localhost:8000/teams/join/<invite_code>/`) or copy the invite code.
2. In Browser 2 (logged in as `coder_bob`), paste and visit the invite URL (or visit [http://localhost:8000/teams/join/](http://localhost:8000/teams/join/) and type the code).
3. The confirmation page will show the Team name, Event name, and current roster size.
4. Click **Confirm & Join Team**.
5. `coder_bob` is joined and redirected to the team page, now showing both `coder_alice` and `coder_bob`.

#### Step D: Verify the One-Team-Per-Event Constraint
1. In Browser 2 as `coder_bob`, try to form a separate team for the same event by visiting `http://localhost:8000/events/<slug>/teams/create/`.
2. **Expected Result**: An error alert displays:
   > *"You are already a member of team 'Quantum Hackers' in this event. Each participant can only be on one team per event."*
3. Create a third team with a different user or try to join another team with `coder_bob`.
4. **Expected Result**: Join is rejected with the same one-team constraint error.

### 2. Run Automated Tests
Execute the comprehensive test suite (34 tests covering Phase 1, Phase 2, Phase 3, and Phase 4):
```powershell
.\.venv\Scripts\python manage.py test
```
**Expected Output:**
```text
Ran 34 tests in 66.148s

OK
```