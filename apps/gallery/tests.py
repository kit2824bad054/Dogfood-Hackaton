"""
Tests for public project gallery and seed data command.

Phase 6: Public gallery visibility enforcement, filtering, search,
and seed data idempotency tests.
"""

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.events.models import Event, Track
from apps.submissions.models import Submission
from apps.teams.models import Team, TeamMembership

User = get_user_model()


class GalleryViewVisibilityTests(TestCase):
    """Test suite ensuring public visibility rules and access controls on /gallery/."""

    def setUp(self):
        self.client = Client()
        self.now = timezone.now()

        # Seed organizer
        self.organizer = User.objects.create_user(
            username='org_alice',
            password='Password123!',
            email='alice@example.com',
            role=User.Role.ORGANIZER
        )

        # Seed participant
        self.participant1 = User.objects.create_user(
            username='part_bob',
            password='Password123!',
            email='bob@example.com',
            role=User.Role.PARTICIPANT
        )
        self.participant2 = User.objects.create_user(
            username='part_charlie',
            password='Password123!',
            email='charlie@example.com',
            role=User.Role.PARTICIPANT
        )

        # Event 1: gallery_enabled = True
        self.event_gallery_on = Event.objects.create(
            name="Open AI Hackathon",
            slug="open-ai-hackathon",
            description="Frontier AI competition.",
            status=Event.Status.OPEN,
            gallery_enabled=True,
            start_date=self.now - timedelta(days=1),
            registration_deadline=self.now + timedelta(days=2),
            submission_deadline=self.now + timedelta(days=4),
            end_date=self.now + timedelta(days=5),
            created_by=self.organizer
        )
        self.track_ai = Track.objects.create(
            event=self.event_gallery_on,
            name="AI Agents",
            description="Agentic architectures."
        )

        # Event 2: gallery_enabled = False
        self.event_gallery_off = Event.objects.create(
            name="Private Security Hackathon",
            slug="private-security-hackathon",
            description="Internal security competition.",
            status=Event.Status.OPEN,
            gallery_enabled=False,
            start_date=self.now - timedelta(days=1),
            registration_deadline=self.now + timedelta(days=2),
            submission_deadline=self.now + timedelta(days=4),
            end_date=self.now + timedelta(days=5),
            created_by=self.organizer
        )

        # Team 1 in Event 1: Submitted project
        self.team1 = Team.objects.create(
            event=self.event_gallery_on,
            name="Team Neuro",
            created_by=self.participant1
        )
        TeamMembership.objects.create(team=self.team1, user=self.participant1)
        self.sub_submitted = Submission.objects.create(
            team=self.team1,
            event=self.event_gallery_on,
            track=self.track_ai,
            title="NeuroBot Agent",
            description="An autonomous reasoning agent with memory stream.",
            repo_url="https://github.com/example/neurobot",
            demo_url="https://neurobot.example.com",
            status=Submission.Status.SUBMITTED,
            submitted_at=self.now - timedelta(hours=3)
        )

        # Team 2 in Event 1: Draft project
        self.team2 = Team.objects.create(
            event=self.event_gallery_on,
            name="Team Draftsters",
            created_by=self.participant2
        )
        TeamMembership.objects.create(team=self.team2, user=self.participant2)
        self.sub_draft = Submission.objects.create(
            team=self.team2,
            event=self.event_gallery_on,
            track=self.track_ai,
            title="Draft Secret AI",
            description="Work in progress agent draft.",
            repo_url="https://github.com/example/draft",
            status=Submission.Status.DRAFT,
            submitted_at=None
        )

        # Team 3 in Event 2 (gallery_enabled=False): Submitted project
        self.team3 = Team.objects.create(
            event=self.event_gallery_off,
            name="Team Stealth",
            created_by=self.participant1
        )
        TeamMembership.objects.create(team=self.team3, user=self.participant1)
        self.sub_hidden_event = Submission.objects.create(
            team=self.team3,
            event=self.event_gallery_off,
            title="Hidden Stealth Project",
            description="Classified submission from private event.",
            repo_url="https://github.com/example/stealth",
            status=Submission.Status.SUBMITTED,
            submitted_at=self.now - timedelta(hours=1)
        )

    def test_gallery_accessible_anonymously(self):
        """Anonymous clients can access /gallery/ without logging in."""
        response = self.client.get(reverse('gallery_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gallery/gallery_list.html')

    def test_submitted_project_visible_in_gallery(self):
        """Submitted project from a gallery_enabled event appears in the gallery."""
        response = self.client.get(reverse('gallery_list'))
        self.assertContains(response, "NeuroBot Agent")
        self.assertContains(response, "Team Neuro")
        self.assertContains(response, "Open AI Hackathon")
        self.assertContains(response, "AI Agents")

    def test_draft_project_never_appears_in_gallery(self):
        """Draft projects must NEVER appear in the public gallery."""
        response = self.client.get(reverse('gallery_list'))
        self.assertNotContains(response, "Draft Secret AI")
        self.assertNotContains(response, "Team Draftsters")

    def test_disabled_gallery_event_submissions_never_appear(self):
        """Projects from events with gallery_enabled=False must NEVER appear, even if submitted."""
        response = self.client.get(reverse('gallery_list'))
        self.assertNotContains(response, "Hidden Stealth Project")
        self.assertNotContains(response, "Team Stealth")
        self.assertNotContains(response, "Private Security Hackathon")

    def test_gallery_detail_accessible_for_submitted_project(self):
        """Public detail view shows full submission details for valid submitted project."""
        url = reverse('gallery_detail', kwargs={'submission_id': self.sub_submitted.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gallery/gallery_detail.html')
        self.assertContains(response, "NeuroBot Agent")
        self.assertContains(response, "Team Neuro")
        self.assertContains(response, "part_bob")
        self.assertContains(response, "https://github.com/example/neurobot")
        self.assertContains(response, "https://neurobot.example.com")
        self.assertContains(response, "AI Agents")
        self.assertContains(response, "Open AI Hackathon")

    def test_direct_url_guess_draft_submission_returns_404(self):
        """Directly requesting a draft submission's detail URL returns 404."""
        url = reverse('gallery_detail', kwargs={'submission_id': self.sub_draft.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_direct_url_guess_disabled_gallery_event_returns_404(self):
        """Directly requesting a submission from a gallery_disabled event returns 404."""
        url = reverse('gallery_detail', kwargs={'submission_id': self.sub_hidden_event.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_direct_url_guess_nonexistent_submission_returns_404(self):
        """Directly requesting a non-existent submission ID returns 404."""
        url = reverse('gallery_detail', kwargs={'submission_id': 999999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class GalleryFilterAndSearchTests(TestCase):
    """Test suite for gallery search and filtering capabilities via GET query params."""

    def setUp(self):
        self.client = Client()
        self.now = timezone.now()

        self.organizer = User.objects.create_user(
            username='org_filter',
            password='Password123!',
            email='org_filter@example.com',
            role=User.Role.ORGANIZER
        )
        self.p1 = User.objects.create_user(username='p_alpha', password='Password123!', role=User.Role.PARTICIPANT)
        self.p2 = User.objects.create_user(username='p_beta', password='Password123!', role=User.Role.PARTICIPANT)

        # Event A
        self.event_a = Event.objects.create(
            name="Quantum Computing Clash",
            slug="quantum-computing-clash",
            description="Quantum algorithms.",
            status=Event.Status.OPEN,
            gallery_enabled=True,
            start_date=self.now - timedelta(days=2),
            registration_deadline=self.now + timedelta(days=2),
            submission_deadline=self.now + timedelta(days=3),
            end_date=self.now + timedelta(days=4),
            created_by=self.organizer
        )
        self.track_q1 = Track.objects.create(event=self.event_a, name="Quantum Simulation")
        self.track_q2 = Track.objects.create(event=self.event_a, name="Quantum Cryptography")

        # Event B
        self.event_b = Event.objects.create(
            name="BioTech Hackathon",
            slug="biotech-hackathon",
            description="Life sciences.",
            status=Event.Status.OPEN,
            gallery_enabled=True,
            start_date=self.now - timedelta(days=2),
            registration_deadline=self.now + timedelta(days=2),
            submission_deadline=self.now + timedelta(days=3),
            end_date=self.now + timedelta(days=4),
            created_by=self.organizer
        )
        self.track_bio = Track.objects.create(event=self.event_b, name="Genomic Analytics")

        # Submission 1: Event A, Track Q1
        self.team1 = Team.objects.create(event=self.event_a, name="Qubiteers", created_by=self.p1)
        self.sub1 = Submission.objects.create(
            team=self.team1,
            event=self.event_a,
            track=self.track_q1,
            title="QSim Fast Matrix Solver",
            description="Accelerated quantum state tensor network simulation.",
            repo_url="https://github.com/example/qsim",
            status=Submission.Status.SUBMITTED,
            submitted_at=self.now - timedelta(hours=5)
        )

        # Submission 2: Event A, Track Q2
        self.team2 = Team.objects.create(event=self.event_a, name="CipherGuild", created_by=self.p2)
        self.sub2 = Submission.objects.create(
            team=self.team2,
            event=self.event_a,
            track=self.track_q2,
            title="PostQuantum Key Exchange",
            description="Lattice-based cryptography for zero-trust networks.",
            repo_url="https://github.com/example/pqkey",
            status=Submission.Status.SUBMITTED,
            submitted_at=self.now - timedelta(hours=3)
        )

        # Submission 3: Event B, Track Bio
        self.team3 = Team.objects.create(event=self.event_b, name="HelixDevs", created_by=self.p1)
        self.sub3 = Submission.objects.create(
            team=self.team3,
            event=self.event_b,
            track=self.track_bio,
            title="GeneFold Deep Predictor",
            description="Protein structure folding neural network pipeline.",
            repo_url="https://github.com/example/genefold",
            status=Submission.Status.SUBMITTED,
            submitted_at=self.now - timedelta(hours=1)
        )

    def test_search_by_title_keyword(self):
        """Searching ?q=GeneFold returns only matching submission."""
        response = self.client.get(reverse('gallery_list') + '?q=GeneFold')
        self.assertContains(response, "GeneFold Deep Predictor")
        self.assertNotContains(response, "QSim Fast Matrix Solver")
        self.assertNotContains(response, "PostQuantum Key Exchange")

    def test_search_by_description_keyword(self):
        """Searching ?q=lattice matches description excerpt."""
        response = self.client.get(reverse('gallery_list') + '?q=lattice')
        self.assertContains(response, "PostQuantum Key Exchange")
        self.assertNotContains(response, "QSim Fast Matrix Solver")
        self.assertNotContains(response, "GeneFold Deep Predictor")

    def test_search_no_results(self):
        """Searching an unmatched query returns friendly empty state."""
        response = self.client.get(reverse('gallery_list') + '?q=UnmatchedTermXYZ')
        self.assertContains(response, "No Submitted Projects Found")
        self.assertNotContains(response, "QSim Fast Matrix Solver")

    def test_filter_by_event_slug(self):
        """Filtering ?event=quantum-computing-clash narrows results to Event A."""
        response = self.client.get(reverse('gallery_list') + f'?event={self.event_a.slug}')
        self.assertContains(response, "QSim Fast Matrix Solver")
        self.assertContains(response, "PostQuantum Key Exchange")
        self.assertNotContains(response, "GeneFold Deep Predictor")

    def test_filter_by_track_id(self):
        """Filtering ?track=<id> narrows results to that track."""
        response = self.client.get(reverse('gallery_list') + f'?track={self.track_q1.id}')
        self.assertContains(response, "QSim Fast Matrix Solver")
        self.assertNotContains(response, "PostQuantum Key Exchange")
        self.assertNotContains(response, "GeneFold Deep Predictor")

    def test_combined_filters(self):
        """Combined ?event=<slug>&track=<id>&q=<term> correctly narrows down."""
        url = reverse('gallery_list') + f'?event={self.event_a.slug}&track={self.track_q1.id}&q=Matrix'
        response = self.client.get(url)
        self.assertContains(response, "QSim Fast Matrix Solver")
        self.assertNotContains(response, "PostQuantum Key Exchange")


class SeedDemoDataCommandTests(TestCase):
    """Test suite verifying the seed_demo_data management command and idempotency."""

    def test_seed_demo_data_execution_and_idempotency(self):
        """Calling seed_demo_data creates expected records and runs safely multiple times."""
        # 1. First run
        call_command('seed_demo_data')

        # Verify users created
        self.assertEqual(User.objects.filter(role=User.Role.ADMIN).count(), 1)
        self.assertEqual(User.objects.filter(role=User.Role.ORGANIZER).count(), 2)
        self.assertEqual(User.objects.filter(role=User.Role.JUDGE).count(), 2)
        self.assertEqual(User.objects.filter(role=User.Role.PARTICIPANT).count(), 8)

        # Verify events
        open_event = Event.objects.get(slug='ai-frontier-hackathon-2026')
        closed_event = Event.objects.get(slug='cloud-native-summit-hackathon-2026')

        self.assertEqual(open_event.status, Event.Status.OPEN)
        self.assertTrue(open_event.gallery_enabled)
        self.assertTrue(open_event.is_submission_open)

        self.assertEqual(closed_event.status, Event.Status.CLOSED)
        self.assertTrue(closed_event.gallery_enabled)
        self.assertFalse(closed_event.is_submission_open)

        # Verify teams (4 teams, 2 per event)
        self.assertEqual(Team.objects.filter(event=open_event).count(), 2)
        self.assertEqual(Team.objects.filter(event=closed_event).count(), 2)

        # Verify submissions (2 submitted, 1 draft)
        self.assertEqual(Submission.objects.filter(status=Submission.Status.SUBMITTED).count(), 2)
        self.assertEqual(Submission.objects.filter(status=Submission.Status.DRAFT).count(), 1)

        # Verify gallery shows only the 2 submitted projects
        client = Client()
        response = client.get(reverse('gallery_list'))
        self.assertContains(response, "AgentPulse: Real-Time Autonomous Agent Monitor")
        self.assertContains(response, "KubeAutotune: AI-Powered Kubernetes Workload Optimizer")
        self.assertNotContains(response, "OmniGraph: Contextual Knowledge Reasoning Engine (Draft)")

        # 2. Second run (Idempotency test: container reboot scenario)
        call_command('seed_demo_data')

        # Counts must NOT duplicate!
        self.assertEqual(User.objects.filter(role=User.Role.ADMIN).count(), 1)
        self.assertEqual(User.objects.filter(role=User.Role.ORGANIZER).count(), 2)
        self.assertEqual(User.objects.filter(role=User.Role.JUDGE).count(), 2)
        self.assertEqual(User.objects.filter(role=User.Role.PARTICIPANT).count(), 8)
        self.assertEqual(Event.objects.count(), 2)
        self.assertEqual(Team.objects.count(), 4)
        self.assertEqual(Submission.objects.count(), 3)
