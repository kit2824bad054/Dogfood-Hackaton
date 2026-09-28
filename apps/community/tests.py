"""
Automated test suite for Phase 8 / T3 Community Voting, Comments, and Anti-Abuse.

Covers:
1. User cannot vote on their own team's submission (anti-collusion)
2. Voting outside voting window rejected (tested directly against endpoint)
3. Results hidden from non-organizers while voting is open and results_visible_during_voting=False
4. Results become visible once voting closes or results_visible_during_voting=True
5. Re-voting updates existing row, doesn't create duplicate rows (DB count assertion)
6. Rate limiting triggers HTTP 429 when threshold exceeded
7. Duplicate comments flagged for review rather than hard-blocked
8. AuditLog entries created for votes, changes, comments, moderation, and rate limits
9. Comment moderation: hidden comments excluded from public view but visible to organizers
10. Gallery ordering is randomized while voting is open
11. Audit log view restricted to organizer and admin roles
"""

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.community.models import AuditLog, Comment, EventRegistration, Vote
from apps.events.models import Event, Track
from apps.submissions.models import Submission
from apps.teams.models import Team, TeamMembership

User = get_user_model()


class CommunityVotingTestCaseBase(TestCase):
    """Base setup for community voting tests."""

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.now = timezone.now()

        # Users
        self.admin = User.objects.create_superuser(
            username='comm_admin',
            email='admin@test.local',
            password='Password123!'
        )
        self.organizer = User.objects.create_user(
            username='comm_organizer',
            email='org@test.local',
            password='Password123!',
            role=User.Role.ORGANIZER
        )
        self.participant1 = User.objects.create_user(
            username='comm_part1',
            email='part1@test.local',
            password='Password123!',
            role=User.Role.PARTICIPANT
        )
        self.participant2 = User.objects.create_user(
            username='comm_part2',
            email='part2@test.local',
            password='Password123!',
            role=User.Role.PARTICIPANT
        )
        self.participant3 = User.objects.create_user(
            username='comm_part3',
            email='part3@test.local',
            password='Password123!',
            role=User.Role.PARTICIPANT
        )
        self.unregistered_user = User.objects.create_user(
            username='comm_outsider',
            email='outsider@test.local',
            password='Password123!',
            role=User.Role.PARTICIPANT
        )

        # Event with voting enabled and results hidden during voting
        self.event = Event.objects.create(
            name="Community Hackathon 2026",
            slug="community-hackathon-2026",
            description="Testing peer voting and anti-abuse safeguards.",
            status=Event.Status.OPEN,
            gallery_enabled=True,
            voting_enabled=True,
            voting_opens_at=self.now - timedelta(days=1),
            voting_closes_at=self.now + timedelta(days=5),
            results_visible_during_voting=False,
            start_date=self.now - timedelta(days=2),
            registration_deadline=self.now + timedelta(days=5),
            submission_deadline=self.now + timedelta(days=6),
            end_date=self.now + timedelta(days=7),
            created_by=self.organizer
        )

        self.track = Track.objects.create(event=self.event, name="General Track")

        # Team A (participant 1)
        self.teamA = Team.objects.create(event=self.event, name="Team Alpha", created_by=self.participant1)
        TeamMembership.objects.create(team=self.teamA, user=self.participant1)
        EventRegistration.objects.create(event=self.event, user=self.participant1)

        self.subA = Submission.objects.create(
            team=self.teamA,
            event=self.event,
            track=self.track,
            title="Alpha Project Showcase",
            description="High performance caching engine.",
            status=Submission.Status.SUBMITTED,
            submitted_at=self.now - timedelta(hours=5)
        )

        # Team B (participant 2)
        self.teamB = Team.objects.create(event=self.event, name="Team Beta", created_by=self.participant2)
        TeamMembership.objects.create(team=self.teamB, user=self.participant2)
        EventRegistration.objects.create(event=self.event, user=self.participant2)

        self.subB = Submission.objects.create(
            team=self.teamB,
            event=self.event,
            track=self.track,
            title="Beta Autonomous Workflow",
            description="AI orchestrator for cloud pipelines.",
            status=Submission.Status.SUBMITTED,
            submitted_at=self.now - timedelta(hours=4)
        )

        # Team C (participant 3)
        self.teamC = Team.objects.create(event=self.event, name="Team Gamma", created_by=self.participant3)
        TeamMembership.objects.create(team=self.teamC, user=self.participant3)
        EventRegistration.objects.create(event=self.event, user=self.participant3)

        self.subC = Submission.objects.create(
            team=self.teamC,
            event=self.event,
            track=self.track,
            title="Gamma Observability Tool",
            description="Telemetry agent with real-time graphs.",
            status=Submission.Status.SUBMITTED,
            submitted_at=self.now - timedelta(hours=3)
        )

    def tearDown(self):
        cache.clear()


class CommunityVotingRestrictionsTests(CommunityVotingTestCaseBase):
    """Test suite for voting restrictions, self-team blocking, and window enforcement."""

    def test_user_cannot_vote_on_their_own_teams_submission(self):
        """
        Participants must be blocked from voting on their own team's project.
        Tested directly against the POST endpoint.
        """
        self.client.login(username='comm_part1', password='Password123!')
        url = reverse('community_vote', kwargs={'submission_id': self.subA.id})

        response = self.client.post(url, {'value': '5'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Vote.objects.filter(submission=self.subA).count(), 0)

        # Now test voting on another team's project (should succeed)
        url_other = reverse('community_vote', kwargs={'submission_id': self.subB.id})
        resp_success = self.client.post(url_other, {'value': '4'})
        self.assertIn(resp_success.status_code, [200, 201, 302])
        self.assertEqual(Vote.objects.filter(submission=self.subB, user=self.participant1).count(), 1)
        self.client.logout()

    def test_unregistered_user_cannot_vote(self):
        """Users who are not registered participants of the event are rejected."""
        self.client.login(username='comm_outsider', password='Password123!')
        url = reverse('community_vote', kwargs={'submission_id': self.subA.id})

        response = self.client.post(url, {'value': '5'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Vote.objects.filter(submission=self.subA, user=self.unregistered_user).count(), 0)
        self.client.logout()

    def test_voting_outside_voting_window_is_rejected(self):
        """
        Voting attempts when voting is closed must be rejected directly by the endpoint.
        """
        # Case A: voting_enabled = False
        self.event.voting_enabled = False
        self.event.save()

        self.client.login(username='comm_part2', password='Password123!')
        url = reverse('community_vote', kwargs={'submission_id': self.subA.id})
        resp1 = self.client.post(url, {'value': '5'})
        self.assertEqual(resp1.status_code, 403)
        self.assertEqual(Vote.objects.count(), 0)

        # Case B: voting_closes_at in the past
        self.event.voting_enabled = True
        self.event.voting_closes_at = self.now - timedelta(minutes=10)
        self.event.save()

        resp2 = self.client.post(url, {'value': '5'})
        self.assertEqual(resp2.status_code, 403)
        self.assertEqual(Vote.objects.count(), 0)
        self.client.logout()

    def test_revoting_updates_existing_vote_no_duplicate_rows(self):
        """
        Re-voting on the same submission updates the existing row and does not create duplicates.
        """
        self.client.login(username='comm_part2', password='Password123!')
        url = reverse('community_vote', kwargs={'submission_id': self.subA.id})

        # Cast first vote: 4 stars
        resp1 = self.client.post(url, {'value': '4'})
        self.assertIn(resp1.status_code, [200, 201, 302])
        self.assertEqual(Vote.objects.filter(submission=self.subA, user=self.participant2).count(), 1)
        vote_obj = Vote.objects.get(submission=self.subA, user=self.participant2)
        self.assertEqual(vote_obj.value, 4)

        # Re-vote: change to 5 stars
        resp2 = self.client.post(url, {'value': '5'})
        self.assertIn(resp2.status_code, [200, 201, 302])
        self.assertEqual(Vote.objects.filter(submission=self.subA, user=self.participant2).count(), 1)
        vote_obj.refresh_from_db()
        self.assertEqual(vote_obj.value, 5)

        # Audit logs recorded vote_cast then vote_changed
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.VOTE_CAST, user=self.participant2).exists())
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.VOTE_CHANGED, user=self.participant2).exists())
        self.client.logout()


class CommunityResultsPrivacyTests(CommunityVotingTestCaseBase):
    """Test suite for results visibility during and after voting."""

    def setUp(self):
        super().setUp()
        # Seed some votes on subA
        Vote.objects.create(submission=self.subA, user=self.participant2, value=5)
        Vote.objects.create(submission=self.subA, user=self.participant3, value=4)

    def test_results_hidden_from_non_organizers_while_voting_open(self):
        """
        When results_visible_during_voting=False and voting is open,
        public gallery detail does NOT display vote counts or average rating to participants or anonymous users.
        """
        self.event.results_visible_during_voting = False
        self.event.save()

        # Anonymous user visit
        anon_resp = self.client.get(reverse('gallery_detail', kwargs={'submission_id': self.subA.id}))
        self.assertEqual(anon_resp.status_code, 200)
        self.assertContains(anon_resp, "Results Hidden")
        self.assertNotContains(anon_resp, "4.50")
        self.assertFalse(anon_resp.context['community_stats']['results_visible'])
        self.assertIsNone(anon_resp.context['community_stats']['avg_rating'])
        self.assertIsNone(anon_resp.context['community_stats']['vote_count'])

        # Participant visit
        self.client.login(username='comm_part1', password='Password123!')
        part_resp = self.client.get(reverse('gallery_detail', kwargs={'submission_id': self.subA.id}))
        self.assertContains(part_resp, "Results Hidden")
        self.assertFalse(part_resp.context['community_stats']['results_visible'])
        self.client.logout()

        # Organizer visit: CAN see results
        self.client.login(username='comm_organizer', password='Password123!')
        org_resp = self.client.get(reverse('gallery_detail', kwargs={'submission_id': self.subA.id}))
        self.assertTrue(org_resp.context['community_stats']['results_visible'])
        self.assertEqual(org_resp.context['community_stats']['vote_count'], 2)
        self.assertEqual(org_resp.context['community_stats']['avg_rating'], 4.5)
        self.client.logout()

    def test_results_become_visible_once_voting_closes(self):
        """
        Once voting closes, results become visible to all users (public disclosure).
        """
        self.event.voting_closes_at = self.now - timedelta(hours=1)
        self.event.save()
        self.assertFalse(self.event.is_voting_open)

        # Anonymous visitor sees final aggregate results
        anon_resp = self.client.get(reverse('gallery_detail', kwargs={'submission_id': self.subA.id}))
        self.assertEqual(anon_resp.status_code, 200)
        self.assertTrue(anon_resp.context['community_stats']['results_visible'])
        self.assertEqual(anon_resp.context['community_stats']['avg_rating'], 4.5)
        self.assertEqual(anon_resp.context['community_stats']['vote_count'], 2)
        self.assertContains(anon_resp, "4.5")
        self.assertContains(anon_resp, "2 peer votes")


class AntiAbuseAndModerationTests(CommunityVotingTestCaseBase):
    """Test suite for rate limiting, duplicate detection, comment moderation, and audit logs."""

    def test_rate_limiting_triggers_429(self):
        """
        Rapid-fire action attempts beyond threshold trigger HTTP 429 and are logged.
        """
        self.client.login(username='comm_part2', password='Password123!')
        url = reverse('community_vote', kwargs={'submission_id': self.subA.id})

        # Threshold is 20 votes per 60 seconds
        for i in range(20):
            r = self.client.post(url, {'value': '4'})
            self.assertIn(r.status_code, [200, 201, 302])

        # 21st attempt exceeds limit
        exceeded_resp = self.client.post(url, {'value': '5'})
        self.assertEqual(exceeded_resp.status_code, 429)
        self.assertContains(exceeded_resp, "Rate limit exceeded", status_code=429)

        # Verify rate limit trigger recorded in AuditLog
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.RATE_LIMIT_TRIGGERED,
                user=self.participant2
            ).exists()
        )
        self.client.logout()

    def test_duplicate_comments_flagged_for_review_not_hard_blocked(self):
        """
        Near-identical repeated comments from the same user are flagged, not hard-blocked.
        """
        self.client.login(username='comm_part2', password='Password123!')
        url = reverse('community_comment', kwargs={'submission_id': self.subA.id})

        # Post first comment
        r1 = self.client.post(url, {'body': 'Great architectural design and clean code!'})
        self.assertIn(r1.status_code, [200, 201, 302])
        self.assertEqual(Comment.objects.filter(submission=self.subA).count(), 1)
        c1 = Comment.objects.first()
        self.assertFalse(c1.is_flagged_duplicate)

        # Post duplicate comment within 15 minutes
        r2 = self.client.post(url, {'body': 'Great architectural design and clean code!'})
        self.assertIn(r2.status_code, [200, 201, 302])
        self.assertEqual(Comment.objects.filter(submission=self.subA).count(), 2)

        c2 = Comment.objects.order_by('-created_at').first()
        self.assertTrue(c2.is_flagged_duplicate)
        self.client.logout()

    def test_comment_moderation_soft_hides_from_public(self):
        """
        Organizers can soft-hide abusive comments.
        Hidden comments are excluded from public display but remain in DB and organizer view.
        """
        comment = Comment.objects.create(
            submission=self.subA,
            user=self.participant2,
            body="Suspicious comment needing review."
        )

        # Public user sees it initially
        anon_resp1 = self.client.get(reverse('gallery_detail', kwargs={'submission_id': self.subA.id}))
        self.assertContains(anon_resp1, "Suspicious comment needing review.")

        # Organizer hides comment
        self.client.login(username='comm_organizer', password='Password123!')
        mod_url = reverse('community_moderate_comment', kwargs={'comment_id': comment.id})
        mod_resp = self.client.post(mod_url, {'action': 'hide'})
        self.assertIn(mod_resp.status_code, [200, 302])

        comment.refresh_from_db()
        self.assertTrue(comment.is_hidden)
        self.assertIsNotNone(comment.hidden_at)
        self.assertEqual(comment.hidden_by, self.organizer)

        # Organizer sees it with hidden indicator
        org_resp = self.client.get(reverse('gallery_detail', kwargs={'submission_id': self.subA.id}))
        self.assertContains(org_resp, "Hidden by Organizer")
        self.client.logout()

        # Public user CANNOT see the hidden comment anymore
        anon_resp2 = self.client.get(reverse('gallery_detail', kwargs={'submission_id': self.subA.id}))
        self.assertNotContains(anon_resp2, "Suspicious comment needing review.")

        # Verify audit log
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.COMMENT_HIDDEN,
                user=self.organizer
            ).exists()
        )

    def test_audit_log_view_permissions(self):
        """Audit log browser is restricted to organizers and admins."""
        url = reverse('event_audit_logs', kwargs={'event_slug': self.event.slug})

        # Participant forbidden
        self.client.login(username='comm_part1', password='Password123!')
        p_resp = self.client.get(url)
        self.assertEqual(p_resp.status_code, 403)
        self.client.logout()

        # Organizer allowed
        self.client.login(username='comm_organizer', password='Password123!')
        org_resp = self.client.get(url)
        self.assertEqual(org_resp.status_code, 200)
        self.assertContains(org_resp, "Community Audit Logs")
        self.client.logout()

    def test_gallery_ordering_randomized_when_voting_open(self):
        """
        When voting is open for an event, gallery displays submissions with randomize mechanism.
        """
        self.event.voting_enabled = True
        self.event.save()
        self.assertTrue(self.event.is_voting_open)

        url = reverse('gallery_list') + f"?event={self.event.slug}"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['is_randomized_order'])
        self.assertContains(resp, "Anti-Bias Shuffle Active")
