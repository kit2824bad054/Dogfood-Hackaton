"""Tests for Phase 4: Team formation, invite code joins, and roster management."""

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.events.models import Event
from .models import Team, TeamMembership, user_has_team_in_event

User = get_user_model()


class TeamFormationTests(TestCase):
    """Test suite covering Phase 4 team formation and membership rules."""

    def setUp(self):
        self.password = "DogfoodTeamTest2026!"

        # Users
        self.organizer = User.objects.create_user(
            username="org_dave",
            email="dave@hackathon.org",
            password=self.password,
            role=User.Role.ORGANIZER
        )
        self.participant1 = User.objects.create_user(
            username="part_alex",
            email="alex@team.com",
            password=self.password,
            role=User.Role.PARTICIPANT
        )
        self.participant2 = User.objects.create_user(
            username="part_beth",
            email="beth@team.com",
            password=self.password,
            role=User.Role.PARTICIPANT
        )
        self.participant3 = User.objects.create_user(
            username="part_carl",
            email="carl@team.com",
            password=self.password,
            role=User.Role.PARTICIPANT
        )

        # Baseline dates
        self.now = timezone.now()
        self.open_event = Event.objects.create(
            name="Open Hackathon 2026",
            description="Testing teams",
            start_date=self.now + timedelta(days=2),
            end_date=self.now + timedelta(days=5),
            registration_deadline=self.now + timedelta(days=1),
            submission_deadline=self.now + timedelta(days=4),
            status=Event.Status.OPEN,
            created_by=self.organizer
        )

    # 1. Team Creation & Automatic Membership
    def test_participant_can_create_team_and_membership_is_auto_created(self):
        """A participant can create a team; membership for the creator is automatically created."""
        self.client.login(username="part_alex", password=self.password)
        create_url = reverse('team_create', kwargs={'event_slug': self.open_event.slug})

        post_data = {
            'name': 'Alpha Squad',
            'max_members': 4,
        }
        response = self.client.post(create_url, post_data)
        self.assertEqual(response.status_code, 302)

        # Verify team exists
        team = Team.objects.get(name='Alpha Squad', event=self.open_event)
        self.assertEqual(team.created_by, self.participant1)
        self.assertTrue(len(team.invite_code) >= 8)

        # Verify creator membership
        self.assertTrue(team.has_member(self.participant1))
        self.assertEqual(team.member_count, 1)
        self.assertTrue(user_has_team_in_event(self.participant1, self.open_event))

    def test_creating_team_after_registration_deadline_is_rejected(self):
        """Creating a team after the registration deadline has passed is rejected with HTTP 400."""
        closed_reg_event = Event.objects.create(
            name="Past Reg Event",
            description="Testing deadline",
            start_date=self.now + timedelta(days=1),
            end_date=self.now + timedelta(days=3),
            registration_deadline=self.now - timedelta(hours=2),  # In the past
            submission_deadline=self.now + timedelta(days=2),
            status=Event.Status.OPEN,
            created_by=self.organizer
        )

        self.client.login(username="part_alex", password=self.password)
        create_url = reverse('team_create', kwargs={'event_slug': closed_reg_event.slug})

        response = self.client.post(create_url, {'name': 'Late Squad', 'max_members': 4})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Team.objects.filter(name='Late Squad').exists())

    # 2. Join via Invite Code
    def test_second_participant_can_join_via_invite_code(self):
        """A second participant can join a team using its valid invite code."""
        # Alex creates a team
        team = Team.objects.create(
            event=self.open_event,
            name="Beta Squad",
            max_members=4,
            created_by=self.participant1
        )
        TeamMembership.objects.create(team=team, user=self.participant1)

        # Beth joins via invite code
        self.client.login(username="part_beth", password=self.password)
        join_url = reverse('team_join_code', kwargs={'invite_code': team.invite_code})

        response = self.client.post(join_url)
        self.assertEqual(response.status_code, 302)

        team.refresh_from_db()
        self.assertEqual(team.member_count, 2)
        self.assertTrue(team.has_member(self.participant2))

    def test_joining_full_team_is_rejected(self):
        """Joining a team that has already reached max_members is rejected."""
        team = Team.objects.create(
            event=self.open_event,
            name="Tiny Squad",
            max_members=2,
            created_by=self.participant1
        )
        TeamMembership.objects.create(team=team, user=self.participant1)
        TeamMembership.objects.create(team=team, user=self.participant2)
        self.assertTrue(team.is_full)

        # Carl tries to join full team
        self.client.login(username="part_carl", password=self.password)
        join_url = reverse('team_join_code', kwargs={'invite_code': team.invite_code})

        response = self.client.post(join_url)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Team Full", status_code=400)
        self.assertFalse(team.has_member(self.participant3))

    def test_joining_when_already_on_team_for_same_event_is_rejected(self):
        """A participant cannot belong to multiple teams within the same hackathon event."""
        # Team 1
        team1 = Team.objects.create(
            event=self.open_event,
            name="Squad One",
            max_members=4,
            created_by=self.participant1
        )
        TeamMembership.objects.create(team=team1, user=self.participant1)

        # Team 2
        team2 = Team.objects.create(
            event=self.open_event,
            name="Squad Two",
            max_members=4,
            created_by=self.participant2
        )
        TeamMembership.objects.create(team=team2, user=self.participant2)

        # Carl joins Team 1
        TeamMembership.objects.create(team=team1, user=self.participant3)

        # Carl attempts to join Team 2 for the same event
        self.client.login(username="part_carl", password=self.password)
        join_url = reverse('team_join_code', kwargs={'invite_code': team2.invite_code})

        response = self.client.post(join_url)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Already On a Team", status_code=400)
        self.assertFalse(team2.has_member(self.participant3))

    def test_invalid_invite_code_returns_clear_error_not_500(self):
        """Navigating to an invalid or malformed invite code returns 404, not a 500 server error."""
        self.client.login(username="part_alex", password=self.password)
        join_url = reverse('team_join_code', kwargs={'invite_code': 'completely_bogus_code_123'})

        response = self.client.get(join_url)
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Invalid Invite Code", status_code=404)

    # 3. Member Removal Rules
    def test_team_creator_can_remove_member_before_submission_deadline(self):
        """Team creator can remove a non-creator member before the submission deadline."""
        team = Team.objects.create(
            event=self.open_event,
            name="Modifiable Squad",
            max_members=4,
            created_by=self.participant1
        )
        TeamMembership.objects.create(team=team, user=self.participant1)
        TeamMembership.objects.create(team=team, user=self.participant2)

        self.client.login(username="part_alex", password=self.password)
        remove_url = reverse('team_remove_member', kwargs={'team_id': team.id, 'user_id': self.participant2.id})

        response = self.client.post(remove_url)
        self.assertEqual(response.status_code, 302)

        team.refresh_from_db()
        self.assertEqual(team.member_count, 1)
        self.assertFalse(team.has_member(self.participant2))

    def test_removal_is_rejected_after_submission_deadline(self):
        """Member removal is rejected after the project submission deadline has passed."""
        sub_passed_event = Event.objects.create(
            name="Submissions Closed Event",
            description="Testing removal lock",
            start_date=self.now - timedelta(days=3),
            end_date=self.now + timedelta(days=1),
            registration_deadline=self.now - timedelta(days=2),
            submission_deadline=self.now - timedelta(hours=1),  # In the past
            status=Event.Status.OPEN,
            created_by=self.organizer
        )
        team = Team.objects.create(
            event=sub_passed_event,
            name="Locked Squad",
            max_members=4,
            created_by=self.participant1
        )
        TeamMembership.objects.create(team=team, user=self.participant1)
        TeamMembership.objects.create(team=team, user=self.participant2)

        self.client.login(username="part_alex", password=self.password)
        remove_url = reverse('team_remove_member', kwargs={'team_id': team.id, 'user_id': self.participant2.id})

        response = self.client.post(remove_url, follow=True)
        self.assertEqual(response.status_code, 200)

        # Beth should still be on the team
        team.refresh_from_db()
        self.assertTrue(team.has_member(self.participant2))

    def test_creator_cannot_remove_self(self):
        """The team founder cannot remove themselves from their own team."""
        team = Team.objects.create(
            event=self.open_event,
            name="Owner Squad",
            max_members=4,
            created_by=self.participant1
        )
        TeamMembership.objects.create(team=team, user=self.participant1)

        self.client.login(username="part_alex", password=self.password)
        remove_url = reverse('team_remove_member', kwargs={'team_id': team.id, 'user_id': self.participant1.id})

        response = self.client.post(remove_url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(team.has_member(self.participant1))

    # 4. Role Restrictions (Non-participants cannot form/join teams)
    def test_non_participant_role_cannot_create_or_join_team(self):
        """Organizers and judges cannot create or join teams; HTTP 403 Forbidden is returned."""
        team = Team.objects.create(
            event=self.open_event,
            name="Target Squad",
            max_members=4,
            created_by=self.participant1
        )

        # Organizer attempts to create a team
        self.client.login(username="org_dave", password=self.password)
        create_url = reverse('team_create', kwargs={'event_slug': self.open_event.slug})
        resp_create = self.client.get(create_url)
        self.assertEqual(resp_create.status_code, 403)

        # Organizer attempts to join via invite code
        join_url = reverse('team_join_code', kwargs={'invite_code': team.invite_code})
        resp_join = self.client.get(join_url)
        self.assertEqual(resp_join.status_code, 403)
