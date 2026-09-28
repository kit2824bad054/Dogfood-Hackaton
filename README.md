# Dogfood Platform (T1 Platform, T2 Judging & T3 Community Hub)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OSI Approved](https://img.shields.io/badge/OSI-Approved-blue.svg)](https://opensource.org/licenses/)

A 100% self-hosted hackathon operations, project showcase, peer-judging, and community voting platform built with Django 5, Django REST Framework, PostgreSQL 16, and Docker. Designed for managing complete end-to-end hackathons—from organizer event creation and multi-track definition to participant team formation with cryptographically secure invite codes, collaborative project drafting with server-side deadline enforcement, a public submission gallery, isolated rubric judging with cross-judge normalization, and community voting with anti-abuse rate limits and privacy controls.


> **T1, T2 & T3 Completed**: Foundation, RBAC, Event Lifecycles, Team Formation, Submissions with Deadline Enforcement, Public Project Gallery, Automated Demo Seeding, **T2 Judging** (Rubrics, Role Isolation, Normalization, CSV Exports), and **Phase 8 (T3 Community & Anti-Abuse)**: 1-5 Star Peer Voting, Feedback Comments, Organizer Moderation, Duplicate Comment Detection, Sliding-Window Rate Limiting, Audit Trails, and Results Privacy Controls.

---

## ⚡ Quickstart: Run in 2 Minutes

### 1. Boot with Docker Compose
Clone the repository, ensure Docker is running, and launch the platform:

```bash
docker compose up --build
```

The startup script (`entrypoint.sh`) automatically:
1. Waits for PostgreSQL to become healthy and ready.
2. Applies all database migrations (`python manage.py migrate`).
3. Seeds all demo hackathons, user accounts, teams, and submissions via `python manage.py seed_demo_data`.
4. Boots the development server at [http://localhost:8000](http://localhost:8000).

### 2. Access Links
- **Public Gallery**: [http://localhost:8000/gallery/](http://localhost:8000/gallery/) (No login required)
- **Active Hackathons**: [http://localhost:8000/events/](http://localhost:8000/events/)
- **Sign In**: [http://localhost:8000/login/](http://localhost:8000/login/)
- **Django Admin**: [http://localhost:8000/admin/](http://localhost:8000/admin/)

---

## 🔑 Seeded Demo Account Credentials

Every seeded account is pre-configured with the same password for fast local development and grading:

**Universal Password for All Demo Accounts:** `dogfood123`

| Role | Username | Email | Permissions & Access Scope |
| :--- | :--- | :--- | :--- |
| **Admin** (Superuser) | `admin` | `admin@dogfood.local` | Full platform control, Django admin access, all events/submissions |
| **Organizer** | `organizer1` | `organizer1@dogfood.local` | Event creation, track/prize editing, organizer submission console for Event 1 |
| **Organizer** | `organizer2` | `organizer2@dogfood.local` | Event creation and organizer submission console for Event 2 |
| **Judge** | `judge1` | `judge1@dogfood.local` | Judge dashboard access (ready for T2 judging workflows) |
| **Judge** | `judge2` | `judge2@dogfood.local` | Judge dashboard access (ready for T2 judging workflows) |
| **Participant** | `participant1` | `participant1@dogfood.local` | Team 'Alpha Agents' lead (submitted project: *AgentPulse*) |
| **Participant** | `participant2` | `participant2@dogfood.local` | Team 'Alpha Agents' teammate |
| **Participant** | `participant3` | `participant3@dogfood.local` | Team 'Nexus Builders' lead (draft project: *OmniGraph*) |
| **Participant** | `participant4` | `participant4@dogfood.local` | Team 'Nexus Builders' teammate |
| **Participant** | `participant5` | `participant5@dogfood.local` | Team 'KubeCommanders' lead (submitted project: *KubeAutotune*) |
| **Participant** | `participant6` | `participant6@dogfood.local` | Team 'KubeCommanders' teammate |
| **Participant** | `participant7` | `participant7@dogfood.local` | Team 'MeshMasters' lead (no submission) |
| **Participant** | `participant8` | `participant8@dogfood.local` | Team 'MeshMasters' teammate |

---

## 🎯 Verification & Acceptance Guide

### 1. Confirm Seed Data and Gallery Visibility Rules
Visit **[http://localhost:8000/gallery/](http://localhost:8000/gallery/)** as an anonymous visitor (no login required):
- **Visible Projects (Exactly 2)**:
  1. *AgentPulse: Real-Time Autonomous Agent Monitor* (from *AI Frontier Hackathon 2026*, status: `submitted`)
  2. *KubeAutotune: AI-Powered Kubernetes Workload Optimizer* (from *Cloud Native Summit Hackathon 2026*, status: `submitted`)
- **Hidden Projects (Exactly 1)**:
  - *OmniGraph: Contextual Knowledge Reasoning Engine (Draft)* (status: `draft`) does **NOT** appear in the gallery list.
- **Direct URL-Guessing Protection**:
  - Visiting the detail page of the draft submission directly (`/gallery/<draft_id>/`) returns **HTTP 404 Not Found**.
  - Direct URL access to submissions from events with `gallery_enabled=False` also returns **HTTP 404 Not Found**.

### 2. Test Multi-Attribute Filtering & Keyword Search
- **Search by Keyword**: Enter `Pulse` or `Kubernetes` into the search field &rarr; instant matching on project title and description.
- **Filter by Event**: Select *Cloud Native Summit Hackathon 2026* &rarr; narrows to that event's submitted project.
- **Filter by Track**: Dependent on the chosen event &rarr; narrows to submissions assigned to that specific track.
- **Shareable URLs**: Filters are reflected in GET query parameters (`?q=...&event=...&track=...`), enabling bookmarkable and shareable filtered views.

### 3. Run Automated Tests
Execute the complete test suite (78 automated tests covering all 8 phases, community voting, anti-abuse safeguards, judging isolation, normalization, and end-to-end integration):
```bash
# Inside Docker container
docker compose exec web python manage.py test

# Or locally with virtual environment
python manage.py test
```

---

## 🏗️ Architecture & Completed Phases

### Phase 1: Foundation Skeleton
- Docker Compose orchestrating `web` (Django 5) and `db` (PostgreSQL 16) with healthchecks.
- Modular architecture with segregated apps: `accounts`, `events`, `teams`, `submissions`, `gallery`, `judging`.
- Environment variable configuration via `django-environ`.

### Phase 2: Custom Authentication & RBAC
- Custom `User` model extending `AbstractUser` with platform roles: `admin`, `organizer`, `judge`, `participant`.
- Reusable `@role_required` decorator enforcing server-side permission barriers.
- Dedicated dashboards per role with contextual navigation chips.

### Phase 3: Event Lifecycles & Deadlines
- `Event`, `Track`, and `Prize` models with inline formsets and automatic slug generation.
- Public visibility rules: Draft events are hidden from non-creators/non-admins (HTTP 404).
- Core date editing protection: start date and submission deadline locked once an open event starts.
- Server-side deadline evaluation: `event.is_registration_open` and `event.is_submission_open`.

### Phase 4: Team Formation & Membership
- `Team` and `TeamMembership` models with cryptographically secure, URL-safe invite codes (`secrets.token_urlsafe`).
- Strictly enforces the **one-team-per-participant-per-event** constraint across both team creation and invite code joining.
- Capacity limits (`max_members`) and creator-only member removal prior to submission deadline.

### Phase 5: Project Submissions & Deadline Enforcement
- `Submission` model with `OneToOneField` to `Team` (one submission per team) and automatic event denormalization.
- Collaborative team draft editing with live readiness checklists.
- Server-side deadline enforcement on **EVERY write path** (POST attempts after deadline return HTTP 400).
- Submit & un-submit lifecycle allowing revisions before the deadline.
- Read-only Organizer Console at `/events/<slug>/submissions/`.

### Phase 6: Public Gallery & Demo Data Seeding
- Public project gallery at `/gallery/` displaying submitted projects from gallery-enabled events.
- Multi-criteria filtering by event, track, and case-insensitive keyword search (`icontains`).
- Individual project detail page (`/gallery/<submission_id>/`) showcasing description, team roster, repo link, and demo URL.
- Strict visibility enforcement preventing drafts and gallery-disabled submissions from appearing or being directly guessed (HTTP 404).
- Idempotent `seed_demo_data` management command producing 13 accounts, 2 events, 4 teams, 3 submissions, rubric criteria, and judge assignments.
- Automated seeding wired into `entrypoint.sh` for zero-touch setup upon fresh container boot.
- Comprehensive end-to-end integration lifecycle test (`tests/test_integration.py`).

### Phase 7: Judging (T2) — Isolation, Workflows & Cross-Judge Normalization
- **Rubric Model** (`apps/judging/models.py`):
  - Weighted evaluation criteria summing to exactly 100% per event with validation on save.
  - Configurable max score (default 10) per criterion.
- **JudgeAssignment & Conflict Avoidance**:
  - Deterministic round-robin assignment assigning $N$ judges (default 3) per submitted project.
  - Automatically avoids conflicts of interest: judges who are team members on that event's projects are strictly excluded.
  - Idempotent assignment management command: `python manage.py assign_judges --event <slug> [--n 3] [--clear]`.
- **Backend Role Isolation**:
  - Judges can **ONLY** view and score submissions they are assigned to (HTTP 403 on unassigned submissions, enforced at database query level).
  - Judges cannot see peer judges' scores or comments (prevents anchoring bias).
  - Organizers/admins have platform-wide oversight but cannot submit scores unless assigned.
- **Scoring Lifecycle**:
  - Judge Dashboard with live status cards: *Not Started*, *In Progress*, *Completed*.
  - Draft saving vs. Final Submission (requires every rubric criterion to be scored).
  - Tamper-proofing: evaluations become locked/read-only once submitted. Reopening requires organizer intervention.
- **Cross-Judge Score Normalization**:
  - Calculates per-judge mean ($\mu_j$) and standard deviation ($\sigma_j$) per criterion across all their evaluations.
  - Standardizes raw scores to z-scores: $z = \frac{x - \mu_j}{\sigma_j}$.
  - Rescales to global criterion range $[0, \text{max\_score}]$ using event-wide population parameters.
  - Edge-case fallback: judges with single evaluations or zero standard deviation fall back gracefully to raw score.
  - Final weighted score computed as $\sum (\bar{S}_{\text{norm}, c} \times \frac{\text{weight}_c}{100})$.
- **Organizer Progress Dashboard & CSV Exports**:
  - Event progress overview at `/judging/events/<slug>/progress/`.
  - Export raw scores CSV (`/judging/events/<slug>/export/raw/`).
  - Export final normalized rankings CSV (`/judging/events/<slug>/export/rankings/`).

### Phase 8: Community (T3) — Peer Voting, Comments, Anti-Abuse & Privacy Controls
- **Vote Model** (`apps/community/models.py`):
  - 1-5 star peer rating per participant per submission.
  - Re-voting updates the existing row instead of creating duplicates (`Vote.objects.update_or_create`).
- **Comment Model**:
  - Participant feedback discussions per submission.
  - Organizer soft-hiding (`is_hidden=True`) for moderation without database destruction.
  - Duplicate detection flags (`is_flagged_duplicate=True`) marking near-identical comments within 15 minutes.
- **Voting Configuration & Lifecycles**:
  - `voting_enabled`, `voting_opens_at`, `voting_closes_at`, and `results_visible_during_voting` fields on `Event`.
  - Server-side `is_voting_open` property evaluating active window and draft exclusions.
- **Strict Anti-Collusion & Anti-Sybil Safeguards**:
  - Participant-only voting: voters must be registered participants in the event (`EventRegistration` or `TeamMembership`).
  - Self-team voting prohibition: team members are rejected with HTTP 403 when attempting to vote on their own submission.
  - Voting outside the window is rejected with HTTP 403.
- **Results Privacy During Voting**:
  - If `results_visible_during_voting=False`, aggregate scores, averages, and vote counts are hidden from participants and anonymous users while voting is open.
  - Results automatically unlock for public viewing once the voting window closes.
  - Organizers and admins maintain full oversight access at all times.
- **Anti-Bias Randomized Submission Order**:
  - When voting is active for an event, gallery displays submissions in randomized order (`order_by('?')`) to eliminate positional selection bias.
- **Sliding-Window Rate Limiting**:
  - In-memory cache tracking action timestamps per user.
  - Rejects bursts exceeding 20 votes or 10 comments in 60 seconds with HTTP 429.
- **Tamper-Evident Audit Trail**:
  - `AuditLog` records every vote cast, vote change, comment posted, comment hidden/restored, and rate-limit trigger.
  - Organizer audit browser at `/community/events/<slug>/audit-logs/` with filtering by action type, username, and project.

---

## 📁 Repository Structure

```text
.
├── docker-compose.yml     # Compose configuration for web and PostgreSQL
├── Dockerfile             # Python 3.12-slim container specification
├── entrypoint.sh          # PostgreSQL wait loop, migrate, seed_demo_data, and boot
├── .env.example           # Template for environment variables
├── requirements.txt       # Dependencies (Django, DRF, psycopg2-binary, django-environ)
├── manage.py              # Django management script
├── config/                # Django configuration and root routing
├── apps/                  # Modular application domain packages
│   ├── accounts/          # User model, RBAC decorators, auth, seed_demo_data command
│   ├── events/            # Events, tracks, prizes, formsets, and lifecycle management
│   ├── teams/             # Teams, memberships, invite codes, and roster views
│   ├── submissions/       # Submissions, drafts, deadline enforcement, organizer console
│   ├── gallery/           # Public gallery, detail showcase, search and filtering
│   ├── judging/           # Rubrics, judge assignments, isolated scoring, normalization, CSV
│   └── community/         # Peer voting, comments, rate limiting, moderation, and audit logs
├── templates/             # HTML templates styled with custom dark-tech theme
│   ├── accounts/          # Login, signup, role dashboards
│   ├── events/            # Event list, detail, create, edit
│   ├── teams/             # Team detail, create, join
│   ├── submissions/       # Submission forms, status overview, organizer console
│   ├── gallery/           # Public gallery list and detail views
│   ├── judging/           # Judge dashboard, scoring form, readonly view, organizer progress
│   └── community/         # Audit log browser, voting configuration management
├── static/                # Modern CSS design system (dark tech theme, glassmorphism)
└── tests/                 # End-to-end integration lifecycle test suite
```

---

## ⚖️ Phase 7 Verification Walkthrough: Testing Judge Bias Normalization

Follow these steps to verify cross-judge scoring, role isolation, and score normalization:

### 1. Assign Judges to Demo Event
Execute the assignment command (already automatically run during seeding):
```bash
python manage.py assign_judges --event ai-frontier-hackathon-2026 --n 2
```

### 2. Log In as Judge 1 (Lenient Judge)
1. Open a browser window (or standard tab) at [http://localhost:8000/login/](http://localhost:8000/login/).
2. Log in with **Username:** `judge1` | **Password:** `dogfood123`.
3. You will land on the **Judge Dashboard** (`/judging/`).
4. Click **Score Project** on *AgentPulse: Real-Time Autonomous Agent Monitor*.
5. Submit high/lenient scores:
   - *Architecture & Technical Depth (40%)*: `9.5`
   - *Innovation & Problem Solving (30%)*: `9.0`
   - *Impact, Execution & Polish (30%)*: `10.0`
6. Click **Finalize & Complete Evaluation**.
7. Confirm status changes to **Completed** and the page becomes locked/read-only.

### 3. Log In as Judge 2 (Harsh Judge)
1. Open an Incognito/Private window (or separate browser) at [http://localhost:8000/login/](http://localhost:8000/login/).
2. Log in with **Username:** `judge2` | **Password:** `dogfood123`.
3. You will land on the **Judge Dashboard** (`/judging/`). Notice: **judge2 CANNOT see judge1's scores or feedback**.
4. Score *AgentPulse* harshly:
   - *Architecture & Technical Depth (40%)*: `5.0`
   - *Innovation & Problem Solving (30%)*: `4.5`
   - *Impact, Execution & Polish (30%)*: `5.5`
5. Click **Finalize & Complete Evaluation**.

### 4. Verify Role Isolation Endpoint Protection
While logged in as `judge1`, attempt to access unassigned submissions or other events:
- Visiting an unassigned assignment ID returns **HTTP 403 Forbidden**.
- Visiting another judge's score directly returns **HTTP 403 Forbidden**.

### 5. Verify Normalized Rankings as Organizer
1. Log in as **Username:** `organizer1` | **Password:** `dogfood123`.
2. Visit the **Judging Progress & Rankings Console**:
   [http://localhost:8000/judging/events/ai-frontier-hackathon-2026/progress/](http://localhost:8000/judging/events/ai-frontier-hackathon-2026/progress/)
3. Observe:
   - **Progress Status**: 100% completion for fully evaluated submissions.
   - **Scores Table**: Both Raw Average and Normalized Final Scores are displayed side-by-side.
   - **CSV Export**: Click **Export Raw Scores (CSV)** and **Export Normalized Rankings (CSV)** to download audit logs.

---

## 🌟 Phase 8 Verification Walkthrough: Testing Community Voting & Results Privacy

Follow these steps to verify peer voting, anti-collusion protection, results withholding, and public disclosure:

### 1. Ensure Voting Is Enabled on the Demo Event
Run the management command to open voting with results hidden:
```powershell
python manage.py configure_voting --event ai-frontier-hackathon-2026 --open-now --hide-results
```

### 2. Verify Anti-Collusion: Self-Team Voting Is Prohibited
1. Open [http://localhost:8000/login/](http://localhost:8000/login/) and log in as:
   - **Username:** `participant1` | **Password:** `dogfood123` *(Lead for Team Alpha Agents)*
2. Visit their own team's submission:
   [http://localhost:8000/gallery/1/](http://localhost:8000/gallery/1/) (*AgentPulse*)
3. Observe the anti-collusion notice:
   `⚠️ Anti-Collusion Rule: You cannot vote on your own team's submission.`
   *(Any POST request to the vote endpoint returns HTTP 403 Forbidden).*

### 3. Cast Vote as Participant 3 (Different Team)
1. Open an Incognito/Private window (or log out and log in) as:
   - **Username:** `participant3` | **Password:** `dogfood123` *(Member of Team Nexus Builders)*
2. Visit *AgentPulse*: [http://localhost:8000/gallery/1/](http://localhost:8000/gallery/1/)
3. Notice that voting is available! Select **★★★★★ (5 Stars)** and click **Submit Vote**.
4. Observe the green confirmation message and indicator:
   `✓ You previously rated this project 5★`.
5. Now re-vote with **★★★★☆ (4 Stars)** and click **Update Rating**.
   Confirm that the vote updates seamlessly without creating duplicate database rows.

### 4. Cast Vote as Participant 4
1. In another session, log in as:
   - **Username:** `participant4` | **Password:** `dogfood123`
2. Visit *AgentPulse* and vote **★★★★☆ (4 Stars)**.

### 5. Confirm Results Are Hidden While Voting Is Open
1. As `participant3` or as an anonymous visitor, look at the project header on [http://localhost:8000/gallery/1/](http://localhost:8000/gallery/1/):
   - Notice the badge: `🔒 Results Hidden — Withheld until voting closes`.
   - The average rating and total vote counts are completely withheld from the public/participants.

### 6. Close Voting & Confirm Public Results Disclosure
1. Close the voting window via management command (or via organizer UI):
   ```powershell
   python manage.py configure_voting --event ai-frontier-hackathon-2026 --close-now
   ```
2. Refresh [http://localhost:8000/gallery/1/](http://localhost:8000/gallery/1/) as an anonymous visitor or participant:
   - Notice that the results are now unlocked and visible:
     `★ 4.0 / 5.0 (2 peer votes)`
   - On the gallery list [http://localhost:8000/gallery/](http://localhost:8000/gallery/), the gold rating badge appears on the project card.

### 7. Inspect Community Audit Logs as Organizer
1. Log in as **Username:** `organizer1` | **Password:** `dogfood123`.
2. Visit the **Community Audit Logs**:
   [http://localhost:8000/community/events/ai-frontier-hackathon-2026/audit-logs/](http://localhost:8000/community/events/ai-frontier-hackathon-2026/audit-logs/)
3. Observe the complete chronological activity trail:
   - `⭐ Vote Cast` by `@participant3`
   - `🔄 Vote Changed` from 5 to 4 by `@participant3`
   - `⭐ Vote Cast` by `@participant4`
   - Filter by action type or username to verify audit query controls.

---

## 📄 Open-Source License

This project is open-source software licensed under the [MIT License](LICENSE), an **OSI-approved** open-source license.
See the [`LICENSE`](LICENSE) file for complete rights and terms.