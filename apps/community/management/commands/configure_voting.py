"""
Management command to configure and toggle community voting on an event.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta

from apps.events.models import Event


class Command(BaseCommand):
    help = "Enable, disable, or adjust community voting settings for an event."

    def add_arguments(self, parser):
        parser.add_argument('--event', type=str, required=True, help="Slug of the event.")
        parser.add_argument('--enable', action='store_true', help="Enable community voting.")
        parser.add_argument('--disable', action='store_true', help="Disable community voting.")
        parser.add_argument('--show-results', action='store_true', help="Make results visible live during voting.")
        parser.add_argument('--hide-results', action='store_true', help="Hide results until voting closes.")
        parser.add_argument('--open-now', action='store_true', help="Set voting_opens_at to now and voting_closes_at to future.")
        parser.add_argument('--close-now', action='store_true', help="Set voting_closes_at to now (closing voting).")

    def handle(self, *args, **options):
        event_slug = options['event']
        try:
            event = Event.objects.get(slug=event_slug)
        except Event.DoesNotExist:
            raise CommandError(f"Event with slug '{event_slug}' does not exist.")

        now = timezone.now()

        if options['enable']:
            event.voting_enabled = True
            self.stdout.write(self.style.SUCCESS(f"Enabled community voting on '{event.name}'."))

        if options['disable']:
            event.voting_enabled = False
            self.stdout.write(self.style.WARNING(f"Disabled community voting on '{event.name}'."))

        if options['show_results']:
            event.results_visible_during_voting = True
            self.stdout.write(self.style.SUCCESS("Results set to VISIBLE live during voting."))

        if options['hide_results']:
            event.results_visible_during_voting = False
            self.stdout.write(self.style.SUCCESS("Results set to HIDDEN during voting until closed."))

        if options['open_now']:
            event.voting_enabled = True
            event.voting_opens_at = now - timedelta(minutes=5)
            event.voting_closes_at = now + timedelta(days=7)
            self.stdout.write(self.style.SUCCESS(f"Opened voting window: {event.voting_opens_at} to {event.voting_closes_at}."))

        if options['close_now']:
            event.voting_closes_at = now - timedelta(seconds=1)
            self.stdout.write(self.style.WARNING(f"Closed voting window (closed at {event.voting_closes_at})."))

        event.save()

        status = "OPEN" if event.is_voting_open else "CLOSED"
        self.stdout.write(
            f"Event '{event.name}' Voting Status: {status} (voting_enabled={event.voting_enabled}, "
            f"results_visible_during_voting={event.results_visible_during_voting})"
        )
