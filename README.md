# Dogfood Platform

A 100% self-hosted hackathon submission and judging platform built with Django, Django REST Framework, PostgreSQL, and Docker.

---

## Architecture & Roadmap

- **Phase 1: Foundation** (Completed): Docker Compose, PostgreSQL 16, Django 5 skeleton, and app scaffolding.
- **Phase 2: Authentication & RBAC** (Completed): Custom User model with roles, signup, login/logout, role-based dashboards, reusable `@role_required` decorator, and Django Admin role management.
- **Phase 3: Events & Hackathon Lifecycles** (Completed): Event, Track, and Prize models, inline formsets, draft visibility rules, core date editing protection, and deadline enforcement utilities.
- **Phase 4: Team Formation & Membership** (Completed): Team and TeamMembership models, cryptographic URL-safe invite codes, capacity limits, member removal before submission deadline, and one-team-per-event application constraint.
- **Phase 5: Project Submissions** (Completed): Submission model (OneToOne with Team), collaborative team draft editing, server-side deadline enforcement, submit/un-submit lifecycle, and organizer dashboard.
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

## Phase 5: Project Submissions

### Models & Schema (`apps/submissions/models.py`)
- **`Submission`**:
  - `team`: `OneToOneField` to `Team` (`related_name='submission'`) — ensures strictly one submission per team.
  - `event`: `ForeignKey` to `Event` (`related_name='submissions'`) — denormalized from `team.event` on save, never user-editable.
  - `track`: `ForeignKey` to `Track` (`null=True, blank=True, on_delete=SET_NULL`) — optional track selection scoped to event.
  - `title`: `CharField(max_length=200, blank=True)`
  - `description`: `TextField(blank=True)`
  - `repo_url`: `URLField(max_length=500, blank=True)`
  - `demo_url`: `URLField(max_length=500, blank=True)`
  - `status`: `choices=['draft', 'submitted']` (default: `'draft'`)
  - `submitted_at`: DateTimeField (set only when status transitions to `'submitted'`)
  - `created_at`, `updated_at`: auto timestamps

### Access Control & Collaborative Draft Editing
1. **Team-Scoped Permissions**:
   - Only registered members of the team can create, edit, or submit project drafts (checked via `team.has_member(user)`). Non-members receive **HTTP 403 Forbidden**.
   - Any member of the team can edit the shared draft collaboratively.
2. **Server-Side Deadline Enforcement (Critical)**:
   - Evaluates `event.is_submission_open` on **EVERY write path** (draft creation, editing, and final submit).
   - Once the submission deadline has passed:
     - Direct POST attempts to save or submit are rejected with **HTTP 400 Bad Request** (`Deadline Passed`).
     - Visiting the edit endpoint renders a **read-only display view** (no `<form>` or input fields).
3. **Submit & Un-Submit Lifecycle**:
   - **Submit Action**: Changes status to `'submitted'` and timestamps `submitted_at`. Requires `title`, `description`, and `repo_url` to be non-empty (incomplete drafts rejected with HTTP 400).
   - **Un-Submit Action**: Before the submission deadline, teams can un-submit back to `'draft'` to make further revisions. Once deadline passes, un-submitting is locked.
4. **Organizer & Admin Views**:
   - Organizers can view a read-only list of all submissions for their own events at `/events/<slug>/submissions/`.
   - Organizers attempting to view submissions for events they do not own receive **HTTP 403 Forbidden**.
   - Platform Administrators can view submissions across all events.

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
│   ├── submissions/       # Submissions, drafts, deadline enforcement & organizer console (Phase 5)
│   └── gallery/           # Gallery app scaffold (Phase 6)
├── templates/             # HTML templates (accounts, events, teams, submissions, base)
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
Execute the comprehensive test suite (43 tests covering Phases 1, 2, 3, 4, and 5):
```powershell
.\.venv\Scripts\python manage.py test
```
**Expected Output:**
```text
Ran 43 tests in 193.820s

OK
```

---

## Phase 5 Verification & Testing Guide: Project Submissions

### 1. Automated Endpoint Rejection Verification
Run the built-in Phase 5 verification command:
```powershell
.\.venv\Scripts\python manage.py verify_phase5
```

**Verification Steps Executed by the Command:**
1. Authenticates as a team participant and POSTs to `/teams/<team_id>/submission/edit/` to create an initial project draft.
2. Manually sets the hackathon's `submission_deadline` to a past date (`timezone.now() - timedelta(hours=2)`).
3. Directly POSTs an edit revision to `/teams/<team_id>/submission/edit/`.
4. Confirms the server strictly rejects the edit at the endpoint level with **HTTP 400 Bad Request** (`Deadline Passed`).
5. Inspects the database record to confirm the submission title and data remain completely unchanged.
6. Directly POSTs to `/teams/<team_id>/submission/submit/` and confirms final submission is also rejected with **HTTP 400**.

**Expected Output:**
```text
=== Phase 5 Verification: Project Submissions & Deadline Enforcement ===

[Step 1] Creating project submission draft via POST to /teams/<id>/submission/edit/ ...
  -> HTTP Status Code: 302 (Redirect 302 to status overview expected)
  -> SUCCESS: Submission created in DB: 'Autonomous Drone Dispatcher' [Status: draft]

[Step 2] Manually manipulating event.submission_deadline to past date ...
  -> event.submission_deadline: 2026-09-27 11:28:36.798464+00:00
  -> event.is_submission_open: False (Should be False)

[Step 3] Attempting to POST edit to endpoint after deadline has passed ...
  -> HTTP Status Code: 400 (HTTP 400 expected)
  -> SUCCESS: Endpoint strictly rejected write with HTTP 400 'Submission Deadline Passed'!

[Step 4] Checking database record integrity ...
  -> DB Title: 'Autonomous Drone Dispatcher'
  -> SUCCESS: Database record is completely unchanged. Late write was rejected server-side.

[Step 5] Attempting to POST to final submit endpoint after deadline ...
  -> HTTP Status Code: 400 (HTTP 400 expected)
  -> SUCCESS: Final submit endpoint strictly rejected with HTTP 400!

========================================================
>>> ALL CHECKS PASSED: Phase 5 deadline enforcement verified! <<<
========================================================
```

### 2. Manual Browser Walkthrough
1. **Log in as a Team Member**:
   - Navigate to `/events/` and open an active hackathon where you have a team.
   - Click **👥 My Team / Form Team** or go to your team detail page.
   - Click the prominent **🚀 Project Submission** button.
2. **Drafting a Submission**:
   - Click **✏️ Start Project Submission Draft**.
   - Enter a Project Title, select a Track, and input your Repository URL and Description.
   - Click **💾 Save Project Draft**.
   - Notice the status updates to **📝 DRAFT** with a real-time readiness checklist.
3. **Submitting the Project**:
   - Ensure Title, Description, and Repo URL are provided.
   - Click **🚀 Submit Final Project**.
   - Status badge turns green: **✅ SUBMITTED**.
4. **Reverting / Editing Prior to Deadline**:
   - While the deadline is open, click **↩️ Un-submit to Edit Draft**.
   - The project safely transitions back to draft mode.
5. **Organizer Console**:
   - Log in as the Event Organizer or Platform Admin.
   - Visit `/events/<slug>/submissions/` to see the full roster of submissions, tracks, and team members in read-only mode.