"""Tests for Phase 3: Events, tracks, prizes, RBAC, and deadline enforcement."""

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Event, Track, Prize

User = get_user_model()


class EventManagementTests(TestCase):
    """Test suite covering Phase 3 hackathon event management."""

    def setUp(self):
        self.password = "DogfoodEventTest2026!"
        self.organizer1 = User.objects.create_user(
            username="org_alice",
            email="alice@event.com",
            password=self.password,
            role=User.Role.ORGANIZER
        )
        self.organizer2 = User.objects.create_user(
            username="org_bob",
            email="bob@event.com",
            password=self.password,
            role=User.Role.ORGANIZER
        )
        self.participant = User.objects.create_user(
            username="part_charlie",
            email="charlie@event.com",
            password=self.password,
            role=User.Role.PARTICIPANT
        )
        self.admin_user = User.objects.create_superuser(
            username="admin_dana",
            email="dana@event.com",
            password=self.password,
        )

        # Standard baseline dates
        self.now = timezone.now()
        self.future_start = self.now + timedelta(days=2)
        self.future_end = self.now + timedelta(days=5)
        self.future_reg_deadline = self.now + timedelta(days=1)
        self.future_sub_deadline = self.now + timedelta(days=4)

    # 1. Creation & Inline Formsets Tests
    def test_organizer_can_create_event_with_tracks_and_prizes(self):
        """An organizer can create a new hackathon with inline tracks and prizes."""
        self.client.login(username="org_alice", password=self.password)

        post_data = {
            'name': 'AI Innovation Hackathon 2026',
            'description': 'A competitive hackathon focused on building intelligent autonomous agents.',
            'status': Event.Status.OPEN,
            'start_date': self.future_start.strftime('%Y-%m-%d %H:%M:%S'),
            'end_date': self.future_end.strftime('%Y-%m-%d %H:%M:%S'),
            'registration_deadline': self.future_reg_deadline.strftime('%Y-%m-%d %H:%M:%S'),
            'submission_deadline': self.future_sub_deadline.strftime('%Y-%m-%d %H:%M:%S'),
            'gallery_enabled': True,

            # Tracks Formset
            'tracks-TOTAL_FORMS': '2',
            'tracks-INITIAL_FORMS': '0',
            'tracks-MIN_NUM_FORMS': '0',
            'tracks-MAX_NUM_FORMS': '1000',
            'tracks-0-name': 'Agentic AI',
            'tracks-0-description': 'Autonomous multi-agent workflows',
            'tracks-1-name': 'Open Innovation',
            'tracks-1-description': 'Any domain utilizing frontier LLMs',

            # Prizes Formset
            'prizes-TOTAL_FORMS': '2',
            'prizes-INITIAL_FORMS': '0',
            'prizes-MIN_NUM_FORMS': '0',
            'prizes-MAX_NUM_FORMS': '1000',
            'prizes-0-rank': '1',
            'prizes-0-title': 'Grand Champion',
            'prizes-0-description': '₹1,00,000 Cash Prize',
            'prizes-1-rank': '2',
            'prizes-1-title': 'Runner Up',
            'prizes-1-description': '₹50,000 Cash Prize',
        }

        response = self.client.post(reverse('event_create'), post_data)
        self.assertEqual(response.status_code, 302)

        # Confirm Event created in DB
        event = Event.objects.get(name='AI Innovation Hackathon 2026')
        self.assertEqual(event.created_by, self.organizer1)
        self.assertTrue(event.slug.startswith('ai-innovation-hackathon-2026'))
        self.assertEqual(event.status, Event.Status.OPEN)
        self.assertTrue(event.gallery_enabled)

        # Confirm Tracks created
        self.assertEqual(event.tracks.count(), 2)
        self.assertTrue(event.tracks.filter(name='Agentic AI').exists())
        self.assertTrue(event.tracks.filter(name='Open Innovation').exists())

        # Confirm Prizes created
        self.assertEqual(event.prizes.count(), 2)
        self.assertTrue(event.prizes.filter(title='Grand Champion', rank=1).exists())
        self.assertTrue(event.prizes.filter(title='Runner Up', rank=2).exists())

    # 2. RBAC Access Control Tests
    def test_participant_cannot_access_create_event_view(self):
        """A participant attempting to access event creation receives HTTP 403."""
        self.client.login(username="part_charlie", password=self.password)
        response = self.client.get(reverse('event_create'))
        self.assertEqual(response.status_code, 403)

    def test_logged_out_user_redirected_to_login_on_create_event(self):
        """An anonymous user attempting to access event creation is redirected to login."""
        response = self.client.get(reverse('event_create'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login')))

    # 3. Draft Visibility in Event Listing Tests
    def test_draft_event_visibility_in_listing(self):
        """
        Draft events are visible only to their creator organizer or administrators.
        Anonymous users, participants, and other organizers cannot see draft events in the listing.
        """
        # Create one open event and one draft event
        open_event = Event.objects.create(
            name="Open Public Hackathon",
            description="Open event visible to all",
            start_date=self.future_start,
            end_date=self.future_end,
            registration_deadline=self.future_reg_deadline,
            submission_deadline=self.future_sub_deadline,
            status=Event.Status.OPEN,
            created_by=self.organizer1
        )
        draft_event = Event.objects.create(
            name="Secret Draft Hackathon",
            description="Draft event hidden from public",
            start_date=self.future_start,
            end_date=self.future_end,
            registration_deadline=self.future_reg_deadline,
            submission_deadline=self.future_sub_deadline,
            status=Event.Status.DRAFT,
            created_by=self.organizer1
        )

        # A. Anonymous user
        self.client.logout()
        resp_anon = self.client.get(reverse('event_list'))
        self.assertEqual(resp_anon.status_code, 200)
        self.assertContains(resp_anon, "Open Public Hackathon")
        self.assertNotContains(resp_anon, "Secret Draft Hackathon")

        # B. Participant user
        self.client.login(username="part_charlie", password=self.password)
        resp_part = self.client.get(reverse('event_list'))
        self.assertEqual(resp_part.status_code, 200)
        self.assertContains(resp_part, "Open Public Hackathon")
        self.assertNotContains(resp_part, "Secret Draft Hackathon")

        # C. Different organizer (Bob)
        self.client.login(username="org_bob", password=self.password)
        resp_bob = self.client.get(reverse('event_list'))
        self.assertEqual(resp_bob.status_code, 200)
        self.assertContains(resp_bob, "Open Public Hackathon")
        self.assertNotContains(resp_bob, "Secret Draft Hackathon")

        # D. Creator organizer (Alice)
        self.client.login(username="org_alice", password=self.password)
        resp_alice = self.client.get(reverse('event_list'))
        self.assertEqual(resp_alice.status_code, 200)
        self.assertContains(resp_alice, "Open Public Hackathon")
        self.assertContains(resp_alice, "Secret Draft Hackathon")

        # E. Administrator (Dana)
        self.client.login(username="admin_dana", password=self.password)
        resp_admin = self.client.get(reverse('event_list'))
        self.assertEqual(resp_admin.status_code, 200)
        self.assertContains(resp_admin, "Open Public Hackathon")
        self.assertContains(resp_admin, "Secret Draft Hackathon")

    # 4. Draft Event Detail Page 404 Tests
    def test_draft_event_detail_page_404_for_unauthorized_users(self):
        """
        Attempting to view a draft event detail page returns 404 for non-owners and non-admins.
        """
        draft_event = Event.objects.create(
            name="Confidential Planning",
            description="Draft event details",
            start_date=self.future_start,
            end_date=self.future_end,
            registration_deadline=self.future_reg_deadline,
            submission_deadline=self.future_sub_deadline,
            status=Event.Status.DRAFT,
            created_by=self.organizer1
        )
        url = reverse('event_detail', kwargs={'slug': draft_event.slug})

        # Anonymous user gets 404
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 404)

        # Participant user gets 404
        self.client.login(username="part_charlie", password=self.password)
        self.assertEqual(self.client.get(url).status_code, 404)

        # Another organizer gets 404
        self.client.login(username="org_bob", password=self.password)
        self.assertEqual(self.client.get(url).status_code, 404)

        # Event creator gets 200
        self.client.login(username="org_alice", password=self.password)
        self.assertEqual(self.client.get(url).status_code, 200)

        # Admin gets 200
        self.client.login(username="admin_dana", password=self.password)
        self.assertEqual(self.client.get(url).status_code, 200)

    # 5. Core Date Editing Rules Tests
    def test_editing_core_dates_after_event_opened_and_started_is_rejected(self):
        """
        Modifying start_date or submission_deadline after an event is 'open' and has already started
        must be rejected with a clear validation error.
        """
        # Event opened and started in the past
        past_start = self.now - timedelta(hours=3)
        future_end = self.now + timedelta(days=2)
        future_sub = self.now + timedelta(days=1)

        active_event = Event.objects.create(
            name="Ongoing Active Hackathon",
            description="Hackathon currently underway",
            start_date=past_start,
            end_date=future_end,
            registration_deadline=past_start,
            submission_deadline=future_sub,
            status=Event.Status.OPEN,
            created_by=self.organizer1
        )

        self.client.login(username="org_alice", password=self.password)
        edit_url = reverse('event_edit', kwargs={'slug': active_event.slug})

        # Attempt to change start_date and submission_deadline
        new_start = self.now - timedelta(hours=10)
        new_sub = self.now + timedelta(days=5)

        post_data = {
            'name': active_event.name,
            'description': active_event.description,
            'status': active_event.status,
            'start_date': new_start.strftime('%Y-%m-%d %H:%M:%S'),
            'end_date': future_end.strftime('%Y-%m-%d %H:%M:%S'),
            'registration_deadline': active_event.registration_deadline.strftime('%Y-%m-%d %H:%M:%S'),
            'submission_deadline': new_sub.strftime('%Y-%m-%d %H:%M:%S'),
            'gallery_enabled': False,

            'tracks-TOTAL_FORMS': '0',
            'tracks-INITIAL_FORMS': '0',
            'tracks-MIN_NUM_FORMS': '0',
            'tracks-MAX_NUM_FORMS': '1000',

            'prizes-TOTAL_FORMS': '0',
            'prizes-INITIAL_FORMS': '0',
            'prizes-MIN_NUM_FORMS': '0',
            'prizes-MAX_NUM_FORMS': '1000',
        }

        response = self.client.post(edit_url, post_data)
        self.assertEqual(response.status_code, 200)

        form = response.context['form']
        self.assertIn('start_date', form.errors)
        self.assertIn('submission_deadline', form.errors)
        self.assertIn("Cannot modify start date after the event has opened and started", str(form.errors['start_date']))
        self.assertIn("Cannot modify submission deadline after the event has opened and started", str(form.errors['submission_deadline']))

        # Ensure database values remain unchanged
        active_event.refresh_from_db()
        self.assertEqual(active_event.start_date, past_start)
        self.assertEqual(active_event.submission_deadline, future_sub)

    # 6. Deadline Helper Methods Tests
    def test_deadline_enforcement_properties(self):
        """
        Verify that is_registration_open and is_submission_open accurately reflect current time vs deadlines.
        """
        # Case A: Event is OPEN, deadlines in future
        event_open_future = Event.objects.create(
            name="Future Deadlines Event",
            description="Testing deadlines",
            start_date=self.now + timedelta(days=1),
            end_date=self.now + timedelta(days=4),
            registration_deadline=self.now + timedelta(hours=5),
            submission_deadline=self.now + timedelta(days=3),
            status=Event.Status.OPEN,
            created_by=self.organizer1
        )
        self.assertTrue(event_open_future.is_registration_open)
        self.assertTrue(event_open_future.is_submission_open)

        # Case B: Event is OPEN, registration deadline has passed, submission deadline is future
        event_reg_passed = Event.objects.create(
            name="Reg Passed Event",
            description="Testing past registration",
            start_date=self.now - timedelta(hours=2),
            end_date=self.now + timedelta(days=2),
            registration_deadline=self.now - timedelta(minutes=10),
            submission_deadline=self.now + timedelta(days=1),
            status=Event.Status.OPEN,
            created_by=self.organizer1
        )
        self.assertFalse(event_reg_passed.is_registration_open)
        self.assertTrue(event_reg_passed.is_submission_open)

        # Case C: Event is OPEN, submission deadline has passed
        event_sub_passed = Event.objects.create(
            name="Submissions Passed Event",
            description="Testing past submissions",
            start_date=self.now - timedelta(days=2),
            end_date=self.now + timedelta(days=1),
            registration_deadline=self.now - timedelta(days=1),
            submission_deadline=self.now - timedelta(hours=1),
            status=Event.Status.OPEN,
            created_by=self.organizer1
        )
        self.assertFalse(event_sub_passed.is_registration_open)
        self.assertFalse(event_sub_passed.is_submission_open)

        # Case D: Event is DRAFT or CLOSED, even with future deadlines, properties return False
        event_draft = Event.objects.create(
            name="Draft Future Event",
            description="Testing draft state",
            start_date=self.now + timedelta(days=1),
            end_date=self.now + timedelta(days=4),
            registration_deadline=self.now + timedelta(hours=5),
            submission_deadline=self.now + timedelta(days=3),
            status=Event.Status.DRAFT,
            created_by=self.organizer1
        )
        self.assertFalse(event_draft.is_registration_open)
        self.assertFalse(event_draft.is_submission_open)

        event_closed = Event.objects.create(
            name="Closed Event",
            description="Testing closed state",
            start_date=self.now - timedelta(days=5),
            end_date=self.now - timedelta(days=1),
            registration_deadline=self.now - timedelta(days=4),
            submission_deadline=self.now - timedelta(days=2),
            status=Event.Status.CLOSED,
            created_by=self.organizer1
        )
        self.assertFalse(event_closed.is_registration_open)
        self.assertFalse(event_closed.is_submission_open)
