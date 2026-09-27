"""
End-to-End Integration Lifecycle Test for the Dogfood Platform.

Phase 6: Full hackathon lifecycle using Django's test client:
1. Organizer creates an event (with tracks, prizes, gallery_enabled=True)
2. Two participants sign up, one creates a team, the other joins via invite code
3. A team member creates and submits a project before the deadline
4. The submitted project appears in /gallery/ for an anonymous client
5. A draft-status project does NOT appear in /gallery/
6. A submission for an event with gallery_enabled=False does NOT appear in /gallery/, even if status='submitted'
7. Gallery search and filtering tests (keyword search, track filtering)
8. Direct-URL-guess test: requesting a draft submission's detail URL returns 404
"""

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.events.models import Event, Track
from apps.submissions.models import Submission
from apps.teams.models import Team, TeamMembership

User = get_user_model()


class EndToEndHackathonLifecycleIntegrationTest(TestCase):
    """End-to-end integration test validating the complete platform user journey."""

    def setUp(self):
        self.client = Client()
        self.now = timezone.now()

    def test_full_hackathon_lifecycle_end_to_end(self):
        """
        Execute the complete multi-actor lifecycle:
        Organizer -> Participants -> Team -> Submission -> Public Gallery.
        """
        # =====================================================================
        # STEP 1: Organizer creates an event
        # =====================================================================
        organizer = User.objects.create_user(
            username='e2e_organizer',
            email='organizer@e2e.test',
            password='Password123!',
            role=User.Role.ORGANIZER
        )
        self.client.login(username='e2e_organizer', password='Password123!')

        # Create the event
        event = Event.objects.create(
            name="Frontier AI Championship 2026",
            slug="frontier-ai-championship-2026",
            description="Global competition building autonomous agent workflows.",
            status=Event.Status.OPEN,
            gallery_enabled=True,
            start_date=self.now - timedelta(days=1),
            registration_deadline=self.now + timedelta(days=3),
            submission_deadline=self.now + timedelta(days=5),
            end_date=self.now + timedelta(days=6),
            created_by=organizer
        )
        track_agents = Track.objects.create(
            event=event,
            name="Autonomous Multi-Agent Systems",
            description="Agentic frameworks with tool use and self-correction."
        )
        track_infra = Track.objects.create(
            event=event,
            name="Developer Tooling & Observability",
            description="Profiling, tracing, and debugging toolsets."
        )

        self.assertTrue(event.is_registration_open)
        self.assertTrue(event.is_submission_open)
        self.client.logout()

        # =====================================================================
        # STEP 2: Two participants sign up, one creates team, other joins via code
        # =====================================================================
        # Participant 1 signs up
        signup_resp1 = self.client.post(reverse('signup'), {
            'username': 'e2e_builder_one',
            'email': 'builder1@e2e.test',
            'role': User.Role.PARTICIPANT,
            'password': 'StrongSecurePass123!',
            'password_confirm': 'StrongSecurePass123!',
        })
        self.assertEqual(signup_resp1.status_code, 302)  # Redirects to dashboard after signup

        part1 = User.objects.get(username='e2e_builder_one')
        self.assertEqual(part1.role, User.Role.PARTICIPANT)

        # Participant 1 creates a team for the event
        self.client.login(username='e2e_builder_one', password='StrongSecurePass123!')
        team_create_resp = self.client.post(
            reverse('team_create', kwargs={'event_slug': event.slug}),
            {
                'name': 'Starlight Innovators',
                'max_members': 4,
            }
        )
        self.assertEqual(team_create_resp.status_code, 302)

        team = Team.objects.get(name='Starlight Innovators', event=event)
        self.assertTrue(team.has_member(part1))
        self.assertEqual(team.member_count, 1)
        invite_code = team.invite_code
        self.assertTrue(invite_code)
        self.client.logout()

        # Participant 2 signs up
        signup_resp2 = self.client.post(reverse('signup'), {
            'username': 'e2e_builder_two',
            'email': 'builder2@e2e.test',
            'role': User.Role.PARTICIPANT,
            'password': 'StrongSecurePass123!',
            'password_confirm': 'StrongSecurePass123!',
        })
        self.assertEqual(signup_resp2.status_code, 302)

        part2 = User.objects.get(username='e2e_builder_two')
        self.client.login(username='e2e_builder_two', password='StrongSecurePass123!')

        # Participant 2 joins the team using the invite code
        join_resp = self.client.post(reverse('team_join_code', kwargs={'invite_code': invite_code}))
        self.assertEqual(join_resp.status_code, 302)

        # Confirm team now has 2 members
        team.refresh_from_db()
        self.assertEqual(team.member_count, 2)
        self.assertTrue(team.has_member(part2))
        self.client.logout()

        # =====================================================================
        # STEP 3: A team member creates and submits a project
        # =====================================================================
        self.client.login(username='e2e_builder_one', password='StrongSecurePass123!')

        # 3a. Save draft submission
        edit_resp = self.client.post(
            reverse('submission_edit', kwargs={'team_id': team.id}),
            {
                'title': 'Starlight Cognition Engine',
                'description': 'A decentralized reasoning framework coordinating multi-agent swarms.',
                'repo_url': 'https://github.com/starlight/cognition-engine',
                'demo_url': 'https://starlight-demo.io',
                'track': track_agents.id,
            }
        )
        self.assertEqual(edit_resp.status_code, 302)

        submission = Submission.objects.get(team=team)
        self.assertEqual(submission.status, Submission.Status.DRAFT)
        self.assertEqual(submission.title, 'Starlight Cognition Engine')

        # 3b. Finalize and submit the project
        submit_resp = self.client.post(reverse('submission_submit', kwargs={'team_id': team.id}))
        self.assertEqual(submit_resp.status_code, 302)

        submission.refresh_from_db()
        self.assertEqual(submission.status, Submission.Status.SUBMITTED)
        self.assertIsNotNone(submission.submitted_at)
        self.client.logout()

        # =====================================================================
        # STEP 4: The submitted project appears in /gallery/ for anonymous client
        # =====================================================================
        gallery_resp = self.client.get(reverse('gallery_list'))
        self.assertEqual(gallery_resp.status_code, 200)
        self.assertContains(gallery_resp, "Starlight Cognition Engine")
        self.assertContains(gallery_resp, "Starlight Innovators")
        self.assertContains(gallery_resp, "Frontier AI Championship 2026")
        self.assertContains(gallery_resp, "Autonomous Multi-Agent Systems")

        # Check detail page
        detail_resp = self.client.get(reverse('gallery_detail', kwargs={'submission_id': submission.id}))
        self.assertEqual(detail_resp.status_code, 200)
        self.assertContains(detail_resp, "Starlight Cognition Engine")
        self.assertContains(detail_resp, "e2e_builder_one")
        self.assertContains(detail_resp, "e2e_builder_two")
        self.assertContains(detail_resp, "https://github.com/starlight/cognition-engine")
        self.assertContains(detail_resp, "https://starlight-demo.io")

        # =====================================================================
        # STEP 5: A draft-status project does NOT appear in /gallery/
        # =====================================================================
        part3 = User.objects.create_user(username='e2e_builder_three', password='Password123!', role=User.Role.PARTICIPANT)
        team_draft = Team.objects.create(event=event, name="Draft Innovators", created_by=part3)
        TeamMembership.objects.create(team=team_draft, user=part3)

        draft_sub = Submission.objects.create(
            team=team_draft,
            event=event,
            track=track_infra,
            title="Unfinished Stealth Analyzer",
            description="Work in progress draft project that must remain hidden.",
            repo_url="https://github.com/draft/stealth",
            status=Submission.Status.DRAFT,
            submitted_at=None
        )

        gallery_resp2 = self.client.get(reverse('gallery_list'))
        self.assertNotContains(gallery_resp2, "Unfinished Stealth Analyzer")
        self.assertNotContains(gallery_resp2, "Draft Innovators")

        # =====================================================================
        # STEP 6: Submission for event with gallery_enabled=False does NOT appear
        # =====================================================================
        private_event = Event.objects.create(
            name="Classified Internal Hackathon",
            slug="classified-internal-hackathon",
            description="Proprietary closed competition.",
            status=Event.Status.OPEN,
            gallery_enabled=False,  # <--- gallery disabled!
            start_date=self.now - timedelta(days=1),
            registration_deadline=self.now + timedelta(days=2),
            submission_deadline=self.now + timedelta(days=3),
            end_date=self.now + timedelta(days=4),
            created_by=organizer
        )
        part4 = User.objects.create_user(username='e2e_builder_four', password='Password123!', role=User.Role.PARTICIPANT)
        team_private = Team.objects.create(event=private_event, name="BlackOps Team", created_by=part4)
        TeamMembership.objects.create(team=team_private, user=part4)

        hidden_sub = Submission.objects.create(
            team=team_private,
            event=private_event,
            title="Confidential Defense Core",
            description="Fully submitted but belonging to a gallery-disabled event.",
            repo_url="https://github.com/internal/defense-core",
            status=Submission.Status.SUBMITTED,
            submitted_at=self.now - timedelta(hours=2)
        )

        gallery_resp3 = self.client.get(reverse('gallery_list'))
        self.assertNotContains(gallery_resp3, "Confidential Defense Core")
        self.assertNotContains(gallery_resp3, "BlackOps Team")
        self.assertNotContains(gallery_resp3, "Classified Internal Hackathon")

        # =====================================================================
        # STEP 7: Direct-URL-guess protection
        # =====================================================================
        # Attempting to access draft submission detail returns 404
        guess_draft_resp = self.client.get(reverse('gallery_detail', kwargs={'submission_id': draft_sub.id}))
        self.assertEqual(guess_draft_resp.status_code, 404)

        # Attempting to access gallery_disabled event submission detail returns 404
        guess_private_resp = self.client.get(reverse('gallery_detail', kwargs={'submission_id': hidden_sub.id}))
        self.assertEqual(guess_private_resp.status_code, 404)

        # =====================================================================
        # STEP 8: Gallery search and filtering
        # =====================================================================
        # Search keyword match
        search_resp1 = self.client.get(reverse('gallery_list') + '?q=Cognition')
        self.assertContains(search_resp1, "Starlight Cognition Engine")

        # Search non-matching keyword
        search_resp2 = self.client.get(reverse('gallery_list') + '?q=NonExistentMatch')
        self.assertContains(search_resp2, "No Submitted Projects Found")
        self.assertNotContains(search_resp2, "Starlight Cognition Engine")

        # Track filter match
        track_resp = self.client.get(reverse('gallery_list') + f'?track={track_agents.id}')
        self.assertContains(track_resp, "Starlight Cognition Engine")

        # Different track filter mismatch
        other_track_resp = self.client.get(reverse('gallery_list') + f'?track={track_infra.id}')
        self.assertNotContains(other_track_resp, "Starlight Cognition Engine")
