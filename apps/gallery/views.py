"""
Views for the public project gallery in the Dogfood Platform.

Phase 6: Public gallery listing with multi-attribute filtering (event, track, keyword search)
and individual project showcase pages, strictly enforcing public visibility rules
(submitted status + parent event gallery_enabled=True).
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from apps.events.models import Event, Track
from apps.submissions.models import Submission


def gallery_list_view(request):
    """
    Public project gallery view displaying submitted projects from gallery-enabled events.

    Visibility Rules:
    - Only submissions with status='submitted'
    - Only submissions whose parent event has gallery_enabled=True
    - Draft submissions and submissions from gallery_disabled events NEVER appear.

    Filtering/Search (via GET query parameters):
    - 'event': event ID or slug to filter submissions by specific event
    - 'track': track ID or name to filter submissions by specific track
    - 'q': keyword search matching project title or description (icontains)
    """
    # 1. Base Queryset: strictly filter by submitted status and gallery_enabled
    base_qs = Submission.objects.filter(
        status=Submission.Status.SUBMITTED,
        event__gallery_enabled=True,
    ).select_related('team', 'event', 'track').prefetch_related('team__memberships__user')

    # 2. Extract GET query parameters for shareable/bookmarkable URLs
    event_param = request.GET.get('event', '').strip()
    track_param = request.GET.get('track', '').strip()
    search_query = request.GET.get('q', '').strip()

    # 3. Available events for the filter dropdown (only gallery_enabled=True)
    available_events = Event.objects.filter(gallery_enabled=True).order_by('name')

    selected_event = None
    if event_param:
        if event_param.isdigit():
            selected_event = available_events.filter(id=int(event_param)).first()
        else:
            selected_event = available_events.filter(slug=event_param).first()

        if selected_event:
            base_qs = base_qs.filter(event=selected_event)
        elif event_param:
            # If an invalid event was specified, return empty queryset
            base_qs = base_qs.none()

    # 4. Available tracks for the filter dropdown
    # Dependent on selected event if one is chosen, otherwise all tracks from gallery-enabled events
    if selected_event:
        available_tracks = Track.objects.filter(event=selected_event).order_by('name')
    else:
        available_tracks = Track.objects.filter(event__gallery_enabled=True).distinct().order_by('name')

    selected_track = None
    if track_param:
        if track_param.isdigit():
            selected_track = available_tracks.filter(id=int(track_param)).first()
            if not selected_track:
                # Also check general Track model in case track belongs to selected event
                selected_track = Track.objects.filter(id=int(track_param), event__gallery_enabled=True).first()
        else:
            selected_track = available_tracks.filter(name__iexact=track_param).first()

        if selected_track:
            base_qs = base_qs.filter(track=selected_track)
        elif track_param:
            # If an invalid track was specified, return empty queryset
            base_qs = base_qs.none()

    # 5. Simple keyword search across title and description
    if search_query:
        base_qs = base_qs.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    # Order submissions chronologically by submission date
    submissions = base_qs.order_by('-submitted_at', '-created_at')

    context = {
        'submissions': submissions,
        'available_events': available_events,
        'available_tracks': available_tracks,
        'selected_event': selected_event,
        'selected_event_param': event_param,
        'selected_track': selected_track,
        'selected_track_param': track_param,
        'search_query': search_query,
        'total_count': submissions.count(),
    }
    return render(request, 'gallery/gallery_list.html', context)


def gallery_detail_view(request, submission_id):
    """
    Public project showcase detail view.

    Visibility Rule:
    - Returns 404 if the submission does not exist, is in draft state,
      or belongs to an event with gallery_enabled=False.
    - Direct URL guessing cannot bypass the visibility rule.
    """
    submission = get_object_or_404(
        Submission.objects.select_related('team', 'event', 'track').prefetch_related('team__memberships__user'),
        id=submission_id,
        status=Submission.Status.SUBMITTED,
        event__gallery_enabled=True,
    )

    team_members = [membership.user for membership in submission.team.memberships.all()]

    context = {
        'submission': submission,
        'event': submission.event,
        'track': submission.track,
        'team': submission.team,
        'team_members': team_members,
    }
    return render(request, 'gallery/gallery_detail.html', context)
