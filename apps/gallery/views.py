"""
Views for the public project gallery in the Dogfood Platform.

Phase 6: Public gallery listing with multi-attribute filtering (event, track, keyword search)
and individual project showcase pages, strictly enforcing public visibility rules
(submitted status + parent event gallery_enabled=True).

Phase 8 / T3:
- Dynamic project ordering: Randomizes submission order (order_by('?')) when voting is active
  for an event, reducing position bias.
- Hidden results enforcement: Aggregates and rankings are hidden from non-organizers while voting
  is active with results_visible_during_voting=False.
- Community voting widget and comments section with organizer moderation controls.
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from apps.community.models import Comment, Vote
from apps.community.services import (
    can_view_voting_results,
    check_voting_eligibility,
    get_submission_community_stats,
)
from apps.events.models import Event, Track
from apps.submissions.models import Submission
from apps.teams.models import TeamMembership


def gallery_list_view(request):
    """
    Public project gallery view displaying submitted projects from gallery-enabled events.

    Visibility Rules:
    - Only submissions with status='submitted'
    - Only submissions whose parent event has gallery_enabled=True
    - Draft submissions and submissions from gallery_disabled events NEVER appear.

    Ordering Rule (Phase 8):
    - When voting is active for the selected event (event.is_voting_open),
      results are ordered randomly ('?') to eliminate positional selection bias.
    - Otherwise, ordered by submission timestamp.
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
            base_qs = base_qs.none()

    # 4. Available tracks for the filter dropdown
    if selected_event:
        available_tracks = Track.objects.filter(event=selected_event).order_by('name')
    else:
        available_tracks = Track.objects.filter(event__gallery_enabled=True).distinct().order_by('name')

    selected_track = None
    if track_param:
        if track_param.isdigit():
            selected_track = available_tracks.filter(id=int(track_param)).first()
            if not selected_track:
                selected_track = Track.objects.filter(id=int(track_param), event__gallery_enabled=True).first()
        else:
            selected_track = available_tracks.filter(name__iexact=track_param).first()

        if selected_track:
            base_qs = base_qs.filter(track=selected_track)
        elif track_param:
            base_qs = base_qs.none()

    # 5. Simple keyword search across title and description
    if search_query:
        base_qs = base_qs.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    # 6. Ordering: randomize order if voting is open to prevent positional bias
    is_randomized = False
    if selected_event and selected_event.is_voting_open:
        submissions = list(base_qs.order_by('?'))
        is_randomized = True
    else:
        submissions = list(base_qs.order_by('-submitted_at', '-created_at'))

    # 7. Attach community statistics respecting results privacy
    for sub in submissions:
        sub.community_stats = get_submission_community_stats(sub, viewer=request.user)

    context = {
        'submissions': submissions,
        'available_events': available_events,
        'available_tracks': available_tracks,
        'selected_event': selected_event,
        'selected_event_param': event_param,
        'selected_track': selected_track,
        'selected_track_param': track_param,
        'search_query': search_query,
        'total_count': len(submissions),
        'is_randomized_order': is_randomized,
    }
    return render(request, 'gallery/gallery_list.html', context)


def gallery_detail_view(request, submission_id):
    """
    Public project showcase detail view.
    Includes community voting form, feedback comments, and organizer moderation.

    Visibility Rule:
    - Returns 404 if the submission does not exist, is in draft state,
      or belongs to an event with gallery_enabled=False.
    """
    submission = get_object_or_404(
        Submission.objects.select_related('team', 'event', 'track').prefetch_related('team__memberships__user'),
        id=submission_id,
        status=Submission.Status.SUBMITTED,
        event__gallery_enabled=True,
    )

    team_members = [membership.user for membership in submission.team.memberships.all()]
    event = submission.event

    # Determine organizer / admin oversight permission
    is_organizer_or_admin = (
        request.user.is_authenticated and (
            request.user.role == 'admin' or
            request.user.is_superuser or
            (request.user.role == 'organizer' and event.created_by == request.user)
        )
    )

    # Comments: organizers see all (including hidden & duplicate-flagged), public sees only non-hidden
    if is_organizer_or_admin:
        comments = submission.comments.select_related('user', 'hidden_by').order_by('created_at')
    else:
        comments = submission.comments.filter(is_hidden=False).select_related('user').order_by('created_at')

    # Community voting statistics (respecting results privacy)
    community_stats = get_submission_community_stats(submission, viewer=request.user)

    # Existing vote by this user
    user_vote = None
    can_vote = False
    ineligibility_reason = ""
    is_own_team = False

    if request.user.is_authenticated:
        user_vote = Vote.objects.filter(submission=submission, user=request.user).first()
        can_vote, ineligibility_reason = check_voting_eligibility(request.user, submission)
        is_own_team = (
            submission.team and
            TeamMembership.objects.filter(team=submission.team, user=request.user).exists()
        )
    else:
        ineligibility_reason = "Sign in as a registered participant to vote."

    context = {
        'submission': submission,
        'event': event,
        'track': submission.track,
        'team': submission.team,
        'team_members': team_members,
        'comments': comments,
        'community_stats': community_stats,
        'user_vote': user_vote,
        'can_vote': can_vote,
        'ineligibility_reason': ineligibility_reason,
        'is_own_team': is_own_team,
        'is_organizer_or_admin': is_organizer_or_admin,
    }
    return render(request, 'gallery/gallery_detail.html', context)
