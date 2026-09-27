"""
Management command to run the judge assignment algorithm for an event.

Phase 7:
Usage: python manage.py assign_judges --event <slug> [--n 3] [--clear]
"""

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.events.models import Event
from apps.judging.services import assign_judges_to_event


class Command(BaseCommand):
    help = "Run the balanced round-robin judge assignment algorithm for an event."

    def add_arguments(self, parser):
        parser.add_argument(
            '--event',
            type=str,
            required=True,
            help='Slug of the event to assign judges for.'
        )
        parser.add_argument(
            '--n',
            type=int,
            default=3,
            help='Number of judges to assign to each submitted project (default: 3).'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing assignments for this event before re-assigning.'
        )

    def handle(self, *args, **options):
        event_slug = options['event']
        n_judges = options['n']
        clear_existing = options['clear']

        try:
            event = Event.objects.get(slug=event_slug)
        except Event.DoesNotExist:
            raise CommandError(f"Event with slug '{event_slug}' not found.")

        self.stdout.write(self.style.NOTICE(f"Assigning judges for event '{event.name}' (N={n_judges})..."))

        try:
            result = assign_judges_to_event(
                event=event,
                judges_per_submission=n_judges,
                clear_existing=clear_existing
            )
        except ValidationError as e:
            raise CommandError(str(e.message if hasattr(e, 'message') else e))

        for warning in result.get('warnings', []):
            self.stdout.write(self.style.WARNING(f"WARNING: {warning}"))

        self.stdout.write(self.style.SUCCESS(
            f"Successfully assigned {result['new_assigned_count']} new assignment(s)! "
            f"Total active assignments for event: {result['total_assigned_count']} "
            f"across {result['submissions_count']} project(s)."
        ))
