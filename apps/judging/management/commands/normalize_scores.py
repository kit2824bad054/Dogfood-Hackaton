"""
Management command to run cross-judge score normalization for an event.

Phase 7:
Usage: python manage.py normalize_scores --event <slug>
"""

from django.core.management.base import BaseCommand, CommandError

from apps.events.models import Event
from apps.judging.services import normalize_event_scores


class Command(BaseCommand):
    help = "Run cross-judge z-score normalization for an event."

    def add_arguments(self, parser):
        parser.add_argument(
            '--event',
            type=str,
            required=True,
            help='Slug of the event to normalize scores for.'
        )

    def handle(self, *args, **options):
        event_slug = options['event']

        try:
            event = Event.objects.get(slug=event_slug)
        except Event.DoesNotExist:
            raise CommandError(f"Event with slug '{event_slug}' not found.")

        self.stdout.write(self.style.NOTICE(f"Calculating cross-judge normalization for '{event.name}'..."))

        result = normalize_event_scores(event)

        self.stdout.write(self.style.SUCCESS(
            f"Successfully normalized {result['updated_scores_count']} score record(s)!"
        ))
