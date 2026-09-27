"""
Automated test suite for Phase 5: Project Submissions.

Verifies:
1. Team members can create and collaboratively edit draft submissions.
2. Non-team-members cannot create or edit submissions for teams they don't belong to (HTTP 403).
3. Saving a draft after the submission deadline is rejected server-side (HTTP 400).
4. Submitting requires non-empty title, description, and repo_url.
5. Submitting after the submission deadline is rejected server-side (HTTP 400).
6. Read-only view (no editable form) is rendered when the deadline has passed.
7. Successful submit and un-submit lifecycle prior to deadline.
8. Organizers can only view submissions for their own events (HTTP 403 for events owned by others, HTTP 200 for admins).
9. OneToOneField constraint prevents a team from having multiple submissions (IntegrityError).
"""

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.events.models import Event, Track
from apps.submissions.models import Submission
from apps.teams.models import Team, TeamMembership

User = get_user_model()


class SubmissionTests(TestCase):
    def setUp(self):
        self.password = "TestPass123!"
        self.now = timezone.now()

        # Users
        self.organizer1 = User.objects.create_user(
            username="org_dave",
            email="dave@example.com",
            role="organizer",
            password=self.password
        )
        self.organizer2 = User.objects.create_user(
            username="org_emma",
            email="emma@example.com",
            role="organizer",
            password=self.password
        )
        self.admin = User.objects.create_user(
            username="admin_user",
            email="admin@example.com",
            role="admin",
            password=self.password
        )
        self.member1 = User.objects.create_user(
            username="member_frank",
            email="frank@example.com",
            role="participant",
            password=self.password
        )
        self.member2 = User.objects.create_user(
            username="member_grace",
            email="grace@example.com",
            role="participant",
            password=self.password
        )
        self.outsider = User.objects.create_user(
            username="outsider_harry",
            email="harry@example.com",
            role="participant",
            password=self.password
        )

        # Open Event 1 (Owned by organizer1)
        self.event1 = Event.objects.create(
            name="Alpha AI Hackathon",
            description="Autonomous agents hackathon",
            start_date=self.now - timedelta(days=2),
            end_date=self.now + timedelta(days=5),
            registration_deadline=self.now + timedelta(days=1),
            submission_deadline=self.now + timedelta(days=3),
            status=Event.Status.OPEN,
            created_by=self.organizer1
        )
        self.track1 = Track.objects.create(
            event=self.event1,
            name="Autonomous Agents",
            description="Agentic workflows and reasoning"
        )

        # Event 2 (Owned by organizer2)
        self.event2 = Event.objects.create(
            name="Beta Web3 Hackathon",
            description="Decentralized identity hackathon",
            start_date=self.now - timedelta(days=2),
            end_date=self.now + timedelta(days=5),
            registration_deadline=self.now + timedelta(days=1),
            submission_deadline=self.now + timedelta(days=3),
            status=Event.Status.OPEN,
            created_by=self.organizer2
        )

        # Team for Event 1
        self.team = Team.objects.create(
            event=self.event1,
            name="Neural Navigators",
            created_by=self.member1,
            max_members=4
        )
        TeamMembership.objects.create(team=self.team, user=self.member1)
        TeamMembership.objects.create(team=self.team, user=self.member2)

        self.client = Client()

    # 1. Team member can create a draft submission
    def test_team_member_can_create_draft_submission(self):
        """A team member can save an initial project submission draft."""
        self.client.login(username="member_frank", password=self.password)
        edit_url = reverse('submission_edit', kwargs={'team_id': self.team.id})

        response = self.client.post(edit_url, {
            'title': 'AI Coding Assistant',
            'description': 'An intelligent agent for developer automation.',
            'repo_url': 'https://github.com/neural-nav/assistant',
            'demo_url': 'https://assistant.demo.com',
            'track': self.track1.id,
        })
        self.assertEqual(response.status_code, 302)

        submission = Submission.objects.get(team=self.team)
        self.assertEqual(submission.title, 'AI Coding Assistant')
        self.assertEqual(submission.status, Submission.Status.DRAFT)
        self.assertEqual(submission.event, self.event1)
        self.assertIsNone(submission.submitted_at)

    # 2. Collaborative draft editing by another team member
    def test_collaborative_draft_editing_by_other_team_member(self):
        """Another member of the same team can edit the shared draft."""
        submission = Submission.objects.create(
            team=self.team,
            event=self.event1,
            title='Initial Title',
            description='Initial description',
            repo_url='https://github.com/neural-nav/assistant',
            status=Submission.Status.DRAFT
        )

        self.client.login(username="member_grace", password=self.password)
        edit_url = reverse('submission_edit', kwargs={'team_id': self.team.id})

        response = self.client.post(edit_url, {
            'title': 'Updated Title by Grace',
            'description': 'Updated description with new architecture details.',
            'repo_url': 'https://github.com/neural-nav/assistant-v2',
            'demo_url': '',
            'track': '',
        })
        self.assertEqual(response.status_code, 302)

        submission.refresh_from_db()
        self.assertEqual(submission.title, 'Updated Title by Grace')
        self.assertEqual(submission.repo_url, 'https://github.com/neural-nav/assistant-v2')

    # 3. Non-team-member cannot create or edit a submission
    def test_non_team_member_cannot_edit_submission(self):
        """A user not in the team is rejected with HTTP 403 Forbidden."""
        self.client.login(username="outsider_harry", password=self.password)
        edit_url = reverse('submission_edit', kwargs={'team_id': self.team.id})

        response = self.client.get(edit_url)
        self.assertEqual(response.status_code, 403)

        response = self.client.post(edit_url, {
            'title': 'Hacked Title',
            'description': 'Malicious edit attempt',
            'repo_url': 'https://github.com/evil/repo',
        })
        self.assertEqual(response.status_code, 403)

    # 4. Saving draft after submission deadline is rejected server-side
    def test_saving_draft_after_submission_deadline_is_rejected(self):
        """POSTing to edit endpoint after submission deadline expires returns HTTP 400."""
        # Manipulate deadline to the past
        self.event1.submission_deadline = self.now - timedelta(hours=2)
        self.event1.save()
        self.assertFalse(self.event1.is_submission_open)

        self.client.login(username="member_frank", password=self.password)
        edit_url = reverse('submission_edit', kwargs={'team_id': self.team.id})

        response = self.client.post(edit_url, {
            'title': 'Late Project Draft',
            'description': 'Trying to sneak this in late.',
            'repo_url': 'https://github.com/neural-nav/late',
        })
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Deadline Passed", status_code=400)
        self.assertFalse(Submission.objects.filter(team=self.team).exists())

    # 5. Submitting requires title, description, and repo_url
    def test_submitting_requires_title_description_and_repo_url(self):
        """Final submission requires title, description, and repo_url to be non-empty."""
        # Incomplete draft (missing repo_url and description)
        submission = Submission.objects.create(
            team=self.team,
            event=self.event1,
            title='Incomplete Project',
            description='',
            repo_url='',
            status=Submission.Status.DRAFT
        )

        self.client.login(username="member_frank", password=self.password)
        submit_url = reverse('submission_submit', kwargs={'team_id': self.team.id})

        response = self.client.post(submit_url)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Incomplete Submission", status_code=400)

        submission.refresh_from_db()
        self.assertEqual(submission.status, Submission.Status.DRAFT)
        self.assertIsNone(submission.submitted_at)

    # 6. Submitting after deadline is rejected
    def test_submitting_after_deadline_is_rejected(self):
        """Final submit action after deadline expires returns HTTP 400."""
        submission = Submission.objects.create(
            team=self.team,
            event=self.event1,
            title='Complete Project',
            description='Ready to go.',
            repo_url='https://github.com/neural-nav/ready',
            status=Submission.Status.DRAFT
        )

        # Move deadline to past
        self.event1.submission_deadline = self.now - timedelta(minutes=30)
        self.event1.save()
        self.assertFalse(self.event1.is_submission_open)

        self.client.login(username="member_frank", password=self.password)
        submit_url = reverse('submission_submit', kwargs={'team_id': self.team.id})

        response = self.client.post(submit_url)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Deadline Passed", status_code=400)

        submission.refresh_from_db()
        self.assertEqual(submission.status, Submission.Status.DRAFT)
        self.assertIsNone(submission.submitted_at)

    # 7. Read-only view shown once deadline passed
    def test_readonly_view_rendered_when_deadline_passed(self):
        """When deadline has passed, visiting the edit view renders read-only display without form inputs."""
        submission = Submission.objects.create(
            team=self.team,
            event=self.event1,
            title='Existing Project',
            description='Good description',
            repo_url='https://github.com/neural-nav/existing',
            status=Submission.Status.DRAFT
        )

        # Expire deadline
        self.event1.submission_deadline = self.now - timedelta(minutes=5)
        self.event1.save()

        self.client.login(username="member_frank", password=self.password)
        edit_url = reverse('submission_edit', kwargs={'team_id': self.team.id})

        response = self.client.get(edit_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Submission Deadline Has Passed")
        self.assertContains(response, "Existing Project")
        # Ensure edit form action is NOT present
        self.assertNotContains(response, 'method="POST" action="')

    # 8. Successful submit and un-submit lifecycle
    def test_successful_submit_and_unsubmit_before_deadline(self):
        """Team member can submit a completed project and un-submit back to draft prior to deadline."""
        submission = Submission.objects.create(
            team=self.team,
            event=self.event1,
            title='Winner Project',
            description='Complete and tested.',
            repo_url='https://github.com/neural-nav/winner',
            status=Submission.Status.DRAFT
        )

        self.client.login(username="member_frank", password=self.password)
        submit_url = reverse('submission_submit', kwargs={'team_id': self.team.id})

        # Submit
        response = self.client.post(submit_url)
        self.assertEqual(response.status_code, 302)

        submission.refresh_from_db()
        self.assertEqual(submission.status, Submission.Status.SUBMITTED)
        self.assertIsNotNone(submission.submitted_at)

        # Un-submit back to draft
        unsubmit_url = reverse('submission_unsubmit', kwargs={'team_id': self.team.id})
        response = self.client.post(unsubmit_url)
        self.assertEqual(response.status_code, 302)

        submission.refresh_from_db()
        self.assertEqual(submission.status, Submission.Status.DRAFT)
        self.assertIsNone(submission.submitted_at)

    # 9. Organizer can view submissions for own event but not for events they don't own
    def test_organizer_event_isolation(self):
        """An organizer can only view submissions for events they created; admins can view all."""
        Submission.objects.create(
            team=self.team,
            event=self.event1,
            title='Event 1 Project',
            description='Project for Event 1',
            repo_url='https://github.com/team/proj',
            status=Submission.Status.SUBMITTED
        )

        event1_subs_url = reverse('event_submissions_list', kwargs={'event_slug': self.event1.slug})

        # Organizer 1 (owner) can view
        self.client.login(username="org_dave", password=self.password)
        response = self.client.get(event1_subs_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Neural Navigators")

        # Organizer 2 (non-owner) is rejected with 403
        self.client.login(username="org_emma", password=self.password)
        response = self.client.get(event1_subs_url)
        self.assertEqual(response.status_code, 403)

        # Admin can view any event
        self.client.login(username="admin_user", password=self.password)
        response = self.client.get(event1_subs_url)
        self.assertEqual(response.status_code, 200)

    # 10. One team cannot have two submissions
    def test_one_team_cannot_have_two_submissions(self):
        """Database OneToOneField constraint prevents duplicate submissions for the same team."""
        Submission.objects.create(
            team=self.team,
            event=self.event1,
            title='First Submission',
            description='First',
            repo_url='https://github.com/team/first',
            status=Submission.Status.DRAFT
        )

        with self.assertRaises(IntegrityError):
            Submission.objects.create(
                team=self.team,
                event=self.event1,
                title='Second Submission',
                description='Second',
                repo_url='https://github.com/team/second',
                status=Submission.Status.DRAFT
            )
