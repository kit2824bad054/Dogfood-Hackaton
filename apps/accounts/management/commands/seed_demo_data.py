"""
Seed demo data management command for the Dogfood Platform.

Phase 6: Automatic demo data seeding with full idempotency.
Populates standard roles (admin, organizers, judges, participants),
events (open and closed with gallery_enabled=True), tracks, prizes,
teams, and submissions (both submitted and draft states).
"""

from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.events.models import Event, Prize, Track
from apps.submissions.models import Submission
from apps.teams.models import Team, TeamMembership

User = get_user_model()

DEFAULT_PASSWORD = "dogfood123"


class Command(BaseCommand):
    help = "Idempotently seed demo data for Dogfood Platform hackathons, teams, and submissions."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Purge all seeded demo data before creating new records.'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=== Dogfood Platform: Seeding Demo Data ==="))

        if options.get('clear'):
            self.stdout.write(self.style.WARNING("Clearing existing demo data..."))
            demo_usernames = [
                'admin',
                'organizer1', 'organizer2',
                'judge1', 'judge2',
                'participant1', 'participant2', 'participant3', 'participant4',
                'participant5', 'participant6', 'participant7', 'participant8'
            ]
            demo_event_slugs = [
                'ai-frontier-hackathon-2026',
                'cloud-native-summit-hackathon-2026'
            ]
            Event.objects.filter(slug__in=demo_event_slugs).delete()
            User.objects.filter(username__in=demo_usernames).delete()
            self.stdout.write(self.style.SUCCESS("Existing demo data purged successfully."))

        now = timezone.now()

        # ---------------------------------------------------------------------
        # 1. Seed Users (1 Admin, 2 Organizers, 2 Judges, 8 Participants)
        # ---------------------------------------------------------------------
        self.stdout.write("1. Seeding User Accounts...")

        # 1 Admin (Superuser)
        admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@dogfood.local',
                'first_name': 'System',
                'last_name': 'Admin',
                'role': User.Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
            }
        )
        admin_user.set_password(DEFAULT_PASSWORD)
        admin_user.role = User.Role.ADMIN
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()

        # 2 Organizers
        organizers_data = [
            ('organizer1', 'organizer1@dogfood.local', 'Olivia', 'Organizer'),
            ('organizer2', 'organizer2@dogfood.local', 'Owen', 'Organizer'),
        ]
        organizer_users = []
        for username, email, first_name, last_name in organizers_data:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'role': User.Role.ORGANIZER,
                }
            )
            user.set_password(DEFAULT_PASSWORD)
            user.role = User.Role.ORGANIZER
            user.first_name = first_name
            user.last_name = last_name
            user.save()
            organizer_users.append(user)

        # 2 Judges
        judges_data = [
            ('judge1', 'judge1@dogfood.local', 'Julia', 'Judge'),
            ('judge2', 'judge2@dogfood.local', 'James', 'Judge'),
        ]
        judge_users = []
        for username, email, first_name, last_name in judges_data:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'role': User.Role.JUDGE,
                }
            )
            user.set_password(DEFAULT_PASSWORD)
            user.role = User.Role.JUDGE
            user.first_name = first_name
            user.last_name = last_name
            user.save()
            judge_users.append(user)

        # 8 Participants
        participant_names = [
            ('participant1', 'Priya', 'Patel'),
            ('participant2', 'Marcus', 'Chen'),
            ('participant3', 'Elena', 'Rostova'),
            ('participant4', 'David', 'Kim'),
            ('participant5', 'Amina', 'Diallo'),
            ('participant6', 'Lucas', 'Silva'),
            ('participant7', 'Sofia', 'Garcia'),
            ('participant8', 'Zack', 'Taylor'),
        ]
        participant_users = []
        for username, first_name, last_name in participant_names:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': f"{username}@dogfood.local",
                    'first_name': first_name,
                    'last_name': last_name,
                    'role': User.Role.PARTICIPANT,
                }
            )
            user.set_password(DEFAULT_PASSWORD)
            user.role = User.Role.PARTICIPANT
            user.first_name = first_name
            user.last_name = last_name
            user.save()
            participant_users.append(user)

        # ---------------------------------------------------------------------
        # 2. Seed 2 Events (1 Open, 1 Closed, both gallery_enabled=True)
        # ---------------------------------------------------------------------
        self.stdout.write("2. Seeding Hackathon Events...")

        # Event 1: Open event with future deadlines
        event1, _ = Event.objects.get_or_create(
            slug='ai-frontier-hackathon-2026',
            defaults={
                'name': 'AI Frontier Hackathon 2026',
                'description': (
                    'Build next-generation autonomous agents, generative AI tools, and '
                    'multimodal developer workflows. Compete with top builders worldwide '
                    'to prototype frontier AI applications.'
                ),
                'status': Event.Status.OPEN,
                'gallery_enabled': True,
                'start_date': now - timedelta(days=2),
                'registration_deadline': now + timedelta(days=5),
                'submission_deadline': now + timedelta(days=7),
                'end_date': now + timedelta(days=8),
                'created_by': organizer_users[0],
            }
        )
        event1.name = 'AI Frontier Hackathon 2026'
        event1.status = Event.Status.OPEN
        event1.gallery_enabled = True
        event1.start_date = now - timedelta(days=2)
        event1.registration_deadline = now + timedelta(days=5)
        event1.submission_deadline = now + timedelta(days=7)
        event1.end_date = now + timedelta(days=8)
        event1.created_by = organizer_users[0]
        event1.save()

        # Event 1 Tracks (3 tracks)
        e1_t1, _ = Track.objects.get_or_create(
            event=event1,
            name='Autonomous Agents & LLMs',
            defaults={'description': 'Self-directing agent architectures, tool use, and multi-agent coordination.'}
        )
        e1_t2, _ = Track.objects.get_or_create(
            event=event1,
            name='Developer Tools & Infra',
            defaults={'description': 'AI-assisted developer tooling, code analysis, CI/CD, and productivity enhancers.'}
        )
        e1_t3, _ = Track.objects.get_or_create(
            event=event1,
            name='Multimodal Experience',
            defaults={'description': 'Vision, audio, spatial computing, and interactive multimodal UX.'}
        )

        # Event 1 Prizes (3 prizes)
        Prize.objects.get_or_create(
            event=event1,
            rank=1,
            defaults={'title': 'Grand Champion', 'description': '$10,000 Cash + Cloud Credits'}
        )
        Prize.objects.get_or_create(
            event=event1,
            rank=2,
            defaults={'title': 'Runner-Up', 'description': '$5,000 Cash'}
        )
        Prize.objects.get_or_create(
            event=event1,
            rank=3,
            defaults={'title': 'Best Technical Innovation', 'description': '$2,500 Cash + Swag'}
        )

        # Event 2: Closed event with past deadlines (realistic completed showcase)
        event2, _ = Event.objects.get_or_create(
            slug='cloud-native-summit-hackathon-2026',
            defaults={
                'name': 'Cloud Native Summit Hackathon 2026',
                'description': (
                    'High-throughput microservices, Kubernetes management, and resilient '
                    'distributed systems showcase. Concluded event with verified public '
                    'project submissions.'
                ),
                'status': Event.Status.CLOSED,
                'gallery_enabled': True,
                'start_date': now - timedelta(days=30),
                'registration_deadline': now - timedelta(days=10),
                'submission_deadline': now - timedelta(days=5),
                'end_date': now - timedelta(days=3),
                'created_by': organizer_users[1],
            }
        )
        event2.name = 'Cloud Native Summit Hackathon 2026'
        event2.status = Event.Status.CLOSED
        event2.gallery_enabled = True
        event2.start_date = now - timedelta(days=30)
        event2.registration_deadline = now - timedelta(days=10)
        event2.submission_deadline = now - timedelta(days=5)
        event2.end_date = now - timedelta(days=3)
        event2.created_by = organizer_users[1]
        event2.save()

        # Event 2 Tracks (3 tracks)
        e2_t1, _ = Track.objects.get_or_create(
            event=event2,
            name='Kubernetes & Service Mesh',
            defaults={'description': 'Container orchestration, autoscaling, and zero-trust service mesh networking.'}
        )
        e2_t2, _ = Track.objects.get_or_create(
            event=event2,
            name='Distributed Observability',
            defaults={'description': 'Real-time telemetry, tracing, and automated incident diagnosis.'}
        )
        e2_t3, _ = Track.objects.get_or_create(
            event=event2,
            name='Cost Optimization & Green Tech',
            defaults={'description': 'Carbon-aware computing, power efficiency, and cloud spend control.'}
        )

        # Event 2 Prizes (3 prizes)
        Prize.objects.get_or_create(
            event=event2,
            rank=1,
            defaults={'title': 'First Place - Gold', 'description': '$8,000 Cash'}
        )
        Prize.objects.get_or_create(
            event=event2,
            rank=2,
            defaults={'title': 'Second Place - Silver', 'description': '$4,000 Cash'}
        )
        Prize.objects.get_or_create(
            event=event2,
            rank=3,
            defaults={'title': 'Third Place - Bronze', 'description': '$2,000 Cash'}
        )

        # ---------------------------------------------------------------------
        # 3. Seed 4 Teams (2 per event, 2 members each drawn from 8 participants)
        # ---------------------------------------------------------------------
        self.stdout.write("3. Seeding Teams & Memberships...")

        # Team 1 (Event 1): participant1, participant2
        team1, _ = Team.objects.get_or_create(
            event=event1,
            name='Alpha Agents',
            defaults={
                'created_by': participant_users[0],
                'invite_code': 'alpha2026',
            }
        )
        TeamMembership.objects.get_or_create(team=team1, user=participant_users[0])
        TeamMembership.objects.get_or_create(team=team1, user=participant_users[1])

        # Team 2 (Event 1): participant3, participant4
        team2, _ = Team.objects.get_or_create(
            event=event1,
            name='Nexus Builders',
            defaults={
                'created_by': participant_users[2],
                'invite_code': 'nexus2026',
            }
        )
        TeamMembership.objects.get_or_create(team=team2, user=participant_users[2])
        TeamMembership.objects.get_or_create(team=team2, user=participant_users[3])

        # Team 3 (Event 2): participant5, participant6
        team3, _ = Team.objects.get_or_create(
            event=event2,
            name='KubeCommanders',
            defaults={
                'created_by': participant_users[4],
                'invite_code': 'kube2026',
            }
        )
        TeamMembership.objects.get_or_create(team=team3, user=participant_users[4])
        TeamMembership.objects.get_or_create(team=team3, user=participant_users[5])

        # Team 4 (Event 2): participant7, participant8
        team4, _ = Team.objects.get_or_create(
            event=event2,
            name='MeshMasters',
            defaults={
                'created_by': participant_users[6],
                'invite_code': 'mesh2026',
            }
        )
        TeamMembership.objects.get_or_create(team=team4, user=participant_users[6])
        TeamMembership.objects.get_or_create(team=team4, user=participant_users[7])

        # ---------------------------------------------------------------------
        # 4. Seed 3 Submissions (2 Submitted, 1 Draft)
        # ---------------------------------------------------------------------
        self.stdout.write("4. Seeding Submissions...")

        # Submission 1: SUBMITTED (Team 1, Event 1)
        sub1, _ = Submission.objects.get_or_create(
            team=team1,
            defaults={
                'event': event1,
                'track': e1_t1,
                'title': 'AgentPulse: Real-Time Autonomous Agent Monitor',
                'description': (
                    'AgentPulse delivers streaming telemetry, distributed tracing, and interactive '
                    'topology graphs for multi-agent LLM systems with proactive latency alerts and '
                    'live debugging. Enables engineering teams to trace token usage, agent decisions, '
                    'and tool invocations in real time.'
                ),
                'repo_url': 'https://github.com/dogfood-demo/agent-pulse',
                'demo_url': 'https://agentpulse.demo.dev',
                'status': Submission.Status.SUBMITTED,
                'submitted_at': now - timedelta(days=1),
            }
        )
        sub1.event = event1
        sub1.track = e1_t1
        sub1.title = 'AgentPulse: Real-Time Autonomous Agent Monitor'
        sub1.description = (
            'AgentPulse delivers streaming telemetry, distributed tracing, and interactive '
            'topology graphs for multi-agent LLM systems with proactive latency alerts and '
            'live debugging. Enables engineering teams to trace token usage, agent decisions, '
            'and tool invocations in real time.'
        )
        sub1.repo_url = 'https://github.com/dogfood-demo/agent-pulse'
        sub1.demo_url = 'https://agentpulse.demo.dev'
        sub1.status = Submission.Status.SUBMITTED
        sub1.submitted_at = now - timedelta(days=1)
        sub1.save()

        # Submission 2: DRAFT (Team 2, Event 1) -> Must NOT appear in gallery!
        sub2, _ = Submission.objects.get_or_create(
            team=team2,
            defaults={
                'event': event1,
                'track': e1_t2,
                'title': 'OmniGraph: Contextual Knowledge Reasoning Engine (Draft)',
                'description': (
                    'A prototype graph neural network designed for instant cross-document reasoning '
                    'and semantic link prediction across enterprise document repositories. Currently '
                    'in active draft development.'
                ),
                'repo_url': 'https://github.com/dogfood-demo/omnigraph',
                'demo_url': '',
                'status': Submission.Status.DRAFT,
                'submitted_at': None,
            }
        )
        sub2.event = event1
        sub2.track = e1_t2
        sub2.title = 'OmniGraph: Contextual Knowledge Reasoning Engine (Draft)'
        sub2.description = (
            'A prototype graph neural network designed for instant cross-document reasoning '
            'and semantic link prediction across enterprise document repositories. Currently '
            'in active draft development.'
        )
        sub2.repo_url = 'https://github.com/dogfood-demo/omnigraph'
        sub2.demo_url = ''
        sub2.status = Submission.Status.DRAFT
        sub2.submitted_at = None
        sub2.save()

        # Submission 3: SUBMITTED (Team 3, Event 2) -> Realistic completed event project
        sub3, _ = Submission.objects.get_or_create(
            team=team3,
            defaults={
                'event': event2,
                'track': e2_t1,
                'title': 'KubeAutotune: AI-Powered Kubernetes Workload Optimizer',
                'description': (
                    'An autonomous Kubernetes operator that analyzes historical resource consumption '
                    'metrics and dynamically tunes CPU/memory requests to eliminate cloud over-provisioning '
                    'and prevent out-of-memory evictions. Tested on clusters with 500+ pods.'
                ),
                'repo_url': 'https://github.com/dogfood-demo/kube-autotune',
                'demo_url': 'https://kubeautotune.demo.dev',
                'status': Submission.Status.SUBMITTED,
                'submitted_at': now - timedelta(days=6),
            }
        )
        sub3.event = event2
        sub3.track = e2_t1
        sub3.title = 'KubeAutotune: AI-Powered Kubernetes Workload Optimizer'
        sub3.description = (
            'An autonomous Kubernetes operator that analyzes historical resource consumption '
            'metrics and dynamically tunes CPU/memory requests to eliminate cloud over-provisioning '
            'and prevent out-of-memory evictions. Tested on clusters with 500+ pods.'
        )
        sub3.repo_url = 'https://github.com/dogfood-demo/kube-autotune'
        sub3.demo_url = 'https://kubeautotune.demo.dev'
        sub3.status = Submission.Status.SUBMITTED
        sub3.submitted_at = now - timedelta(days=6)
        sub3.save()

        # ---------------------------------------------------------------------
        # 5. Seed Rubric Criteria (Weights summing to exactly 100% per event)
        # ---------------------------------------------------------------------
        self.stdout.write("5. Seeding Rubric Criteria...")
        from apps.judging.models import Rubric
        from apps.judging.services import assign_judges_to_event

        # Event 1 Rubric Criteria (40% + 30% + 30% = 100%)
        Rubric.objects.get_or_create(
            event=event1,
            name="Technical Architecture & Execution",
            defaults={'weight': Decimal('40.00'), 'max_score': 10, 'description': 'Code quality, system design, and correctness.'}
        )
        Rubric.objects.get_or_create(
            event=event1,
            name="Innovation & Novelty",
            defaults={'weight': Decimal('30.00'), 'max_score': 10, 'description': 'Originality and frontier problem-solving.'}
        )
        Rubric.objects.get_or_create(
            event=event1,
            name="UI/UX & Developer Experience",
            defaults={'weight': Decimal('30.00'), 'max_score': 10, 'description': 'Interface polish, ease of use, and live demo.'}
        )

        # Event 2 Rubric Criteria (40% + 35% + 25% = 100%)
        Rubric.objects.get_or_create(
            event=event2,
            name="System Scalability & Performance",
            defaults={'weight': Decimal('40.00'), 'max_score': 10, 'description': 'High-throughput scaling and resource efficiency.'}
        )
        Rubric.objects.get_or_create(
            event=event2,
            name="Reliability & Fault Tolerance",
            defaults={'weight': Decimal('35.00'), 'max_score': 10, 'description': 'Graceful failure recovery and resilience.'}
        )
        Rubric.objects.get_or_create(
            event=event2,
            name="Documentation & Operational Usability",
            defaults={'weight': Decimal('25.00'), 'max_score': 10, 'description': 'Clarity of guides, metrics, and monitoring.'}
        )

        # ---------------------------------------------------------------------
        # 6. Assign Judges to Events
        # ---------------------------------------------------------------------
        self.stdout.write("6. Assigning Judges to Submitted Projects...")
        assign_judges_to_event(event1, judges_per_submission=2)
        assign_judges_to_event(event2, judges_per_submission=2)

        # ---------------------------------------------------------------------
        # 7. Output Summary Report to stdout
        # ---------------------------------------------------------------------
        self.stdout.write(self.style.SUCCESS("\n[SUCCESS] Seed Demo Data Completed Successfully!"))
        self.stdout.write(self.style.NOTICE("=" * 76))
        self.stdout.write(self.style.NOTICE("         DOGFOOD PLATFORM - SEEDED DEMO CREDENTIALS & DATA"))
        self.stdout.write(self.style.NOTICE("=" * 76))

        self.stdout.write("\n--- USER ACCOUNTS (Password for all accounts: " + self.style.WARNING(DEFAULT_PASSWORD) + ") ---")
        self.stdout.write(f"  {'ROLE':<15} {'USERNAME':<16} {'EMAIL':<30}")
        self.stdout.write("  " + "-" * 62)
        self.stdout.write(f"  {'Admin':<15} {admin_user.username:<16} {admin_user.email:<30}")
        for org in organizer_users:
            self.stdout.write(f"  {'Organizer':<15} {org.username:<16} {org.email:<30}")
        for jdg in judge_users:
            self.stdout.write(f"  {'Judge':<15} {jdg.username:<16} {jdg.email:<30}")
        for ptp in participant_users:
            self.stdout.write(f"  {'Participant':<15} {ptp.username:<16} {ptp.email:<30}")

        self.stdout.write("\n--- HACKATHON EVENTS ---")
        self.stdout.write(f"  1. {event1.name} (status='{event1.status}', gallery_enabled={event1.gallery_enabled})")
        self.stdout.write(f"     Tracks: {e1_t1.name}, {e1_t2.name}, {e1_t3.name}")
        self.stdout.write(f"  2. {event2.name} (status='{event2.status}', gallery_enabled={event2.gallery_enabled})")
        self.stdout.write(f"     Tracks: {e2_t1.name}, {e2_t2.name}, {e2_t3.name}")

        self.stdout.write("\n--- TEAMS (4 teams, 2 per event) ---")
        self.stdout.write(f"  - Team '{team1.name}' ({event1.name}) -> Members: {participant_users[0].username}, {participant_users[1].username}")
        self.stdout.write(f"  - Team '{team2.name}' ({event1.name}) -> Members: {participant_users[2].username}, {participant_users[3].username}")
        self.stdout.write(f"  - Team '{team3.name}' ({event2.name}) -> Members: {participant_users[4].username}, {participant_users[5].username}")
        self.stdout.write(f"  - Team '{team4.name}' ({event2.name}) -> Members: {participant_users[6].username}, {participant_users[7].username}")

        self.stdout.write("\n--- SUBMISSIONS (3 seeded submissions) ---")
        self.stdout.write(f"  1. [SUBMITTED -> VISIBLE IN GALLERY] '{sub1.title}' (Team: {team1.name}, Event: {event1.name})")
        self.stdout.write(f"  2. [DRAFT     -> HIDDEN FROM GALLERY]  '{sub2.title}' (Team: {team2.name}, Event: {event1.name})")
        self.stdout.write(f"  3. [SUBMITTED -> VISIBLE IN GALLERY] '{sub3.title}' (Team: {team3.name}, Event: {event2.name})")
        self.stdout.write(f"  4. [NO SUBMISSION] Team '{team4.name}'")

        self.stdout.write(self.style.NOTICE("\n" + "=" * 76))
        self.stdout.write(f"  Gallery URL: http://localhost:8000/gallery/")
        self.stdout.write(f"  Visible in Gallery: Exactly 2 projects ({sub1.title}, {sub3.title})")
        self.stdout.write(f"  Hidden in Gallery:  Exactly 1 draft project ({sub2.title})")
        self.stdout.write(self.style.NOTICE("=" * 76 + "\n"))
