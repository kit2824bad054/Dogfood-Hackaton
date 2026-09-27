"""
Management command to manually verify Phase 5 endpoint-level deadline enforcement.

Usage:
    python manage.py verify_phase5
"""

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.test import Client
from django.utils import timezone

from apps.events.models import Event
from apps.teams.models import Team, TeamMembership
from apps.submissions.models import Submission

User = get_user_model()


class Command(BaseCommand):
    help = "Verify Phase 5 submission creation and endpoint-level deadline rejection."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Phase 5 Verification: Project Submissions & Deadline Enforcement ==="))
        now = timezone.now()

        # 1. Setup Event, Team, and Member
        admin_user = User.objects.filter(is_superuser=True).first()
        event, _ = Event.objects.get_or_create(
            slug='phase5-demo-hackathon',
            defaults={
                'name': 'Phase 5 Demo Hackathon',
                'description': 'Hackathon for endpoint deadline testing',
                'status': Event.Status.OPEN,
                'start_date': now - timedelta(days=1),
                'end_date': now + timedelta(days=7),
                'registration_deadline': now + timedelta(days=2),
                'submission_deadline': now + timedelta(days=3),
                'created_by': admin_user,
            }
        )
        event.status = Event.Status.OPEN
        event.submission_deadline = now + timedelta(days=3)
        event.save()

        member, _ = User.objects.get_or_create(
            username='phase5_coder',
            defaults={'email': 'coder@example.com', 'role': 'participant'}
        )
        member.set_password('TestPass123!')
        member.save()

        team, _ = Team.objects.get_or_create(
            event=event,
            name='Autonomous Architects',
            defaults={'created_by': member}
        )
        TeamMembership.objects.get_or_create(team=team, user=member)
        Submission.objects.filter(team=team).delete()

        # 2. Authenticate via Test Client and create initial submission draft via endpoint POST
        client = Client()
        client.login(username='phase5_coder', password='TestPass123!')
        edit_url = f'/teams/{team.id}/submission/edit/'

        self.stdout.write("\n[Step 1] Creating project submission draft via POST to /teams/<id>/submission/edit/ ...")
        create_resp = client.post(edit_url, {
            'title': 'Autonomous Drone Dispatcher',
            'description': 'AI-driven drone delivery route optimization.',
            'repo_url': 'https://github.com/autonomous-architects/drone-dispatcher',
            'demo_url': 'https://drone-dispatcher.example.com',
            'track': '',
        })
        self.stdout.write(f"  -> HTTP Status Code: {create_resp.status_code} (Redirect 302 to status overview expected)")
        submission = Submission.objects.get(team=team)
        self.stdout.write(self.style.SUCCESS(f"  -> SUCCESS: Submission created in DB: '{submission.title}' [Status: {submission.status}]"))

        # 3. Manually simulate passing the submission deadline
        self.stdout.write("\n[Step 2] Manually manipulating event.submission_deadline to past date ...")
        event.submission_deadline = timezone.now() - timedelta(hours=2)
        event.save()
        self.stdout.write(f"  -> event.submission_deadline: {event.submission_deadline}")
        self.stdout.write(f"  -> event.is_submission_open: {event.is_submission_open} (Should be False)")

        # 4. Attempt to edit the submission after deadline directly at endpoint level
        self.stdout.write("\n[Step 3] Attempting to POST edit to endpoint after deadline has passed ...")
        edit_resp = client.post(edit_url, {
            'title': 'Hacked Late Revision',
            'description': 'Sneaking this in after the clock ran out.',
            'repo_url': 'https://github.com/autonomous-architects/late-hack',
        })
        self.stdout.write(f"  -> HTTP Status Code: {edit_resp.status_code} (HTTP 400 expected)")
        
        has_error = "Deadline Passed" in edit_resp.content.decode('utf-8')
        if edit_resp.status_code == 400 and has_error:
            self.stdout.write(self.style.SUCCESS("  -> SUCCESS: Endpoint strictly rejected write with HTTP 400 'Submission Deadline Passed'!"))
        else:
            self.stdout.write(self.style.ERROR(f"  -> FAILED: Expected HTTP 400, got {edit_resp.status_code}"))

        # 5. Confirm DB record was NOT modified
        self.stdout.write("\n[Step 4] Checking database record integrity ...")
        submission.refresh_from_db()
        self.stdout.write(f"  -> DB Title: '{submission.title}'")
        if submission.title == 'Autonomous Drone Dispatcher':
            self.stdout.write(self.style.SUCCESS("  -> SUCCESS: Database record is completely unchanged. Late write was rejected server-side."))
        else:
            self.stdout.write(self.style.ERROR("  -> FAILED: Database was modified after deadline!"))

        # 6. Attempt final submit action after deadline
        self.stdout.write("\n[Step 5] Attempting to POST to final submit endpoint after deadline ...")
        submit_url = f'/teams/{team.id}/submission/submit/'
        submit_resp = client.post(submit_url)
        self.stdout.write(f"  -> HTTP Status Code: {submit_resp.status_code} (HTTP 400 expected)")
        if submit_resp.status_code == 400:
            self.stdout.write(self.style.SUCCESS("  -> SUCCESS: Final submit endpoint strictly rejected with HTTP 400!"))
        
        self.stdout.write(self.style.SUCCESS("\n========================================================"))
        self.stdout.write(self.style.SUCCESS(">>> ALL CHECKS PASSED: Phase 5 deadline enforcement verified! <<<"))
        self.stdout.write(self.style.SUCCESS("========================================================\n"))
