"""Views for hackathon events listing, detail, creation, and editing."""

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.decorators import role_required
from .forms import EventForm, TrackFormSet, PrizeFormSet
from .models import Event


def get_visible_events_queryset(user):
    """
    Return queryset of events that the given user has permission to see.

    Rules:
    - Open and Closed events are visible to all users (including anonymous visitors).
    - Draft events are visible ONLY to the organizer who created them or administrators.
    """
    public_status = [Event.Status.OPEN, Event.Status.CLOSED]
    if user.is_authenticated:
        if getattr(user, 'role', None) == 'admin' or user.is_superuser:
            return Event.objects.all()
        return Event.objects.filter(
            Q(status__in=public_status) |
            Q(status=Event.Status.DRAFT, created_by=user)
        )
    return Event.objects.filter(status__in=public_status)


def event_list_view(request):
    """
    Public listing of all available hackathons.
    Applies draft visibility rules based on current user role and ownership.
    """
    events = get_visible_events_queryset(request.user).distinct()
    return render(request, 'events/event_list.html', {
        'events': events,
    })


def event_detail_view(request, slug):
    """
    Detailed view of a single hackathon, including tracks, prizes, and deadlines.
    Returns 404 if a non-owner, non-admin user attempts to view a draft event.
    """
    visible_events = get_visible_events_queryset(request.user)
    event = get_object_or_404(visible_events.prefetch_related('tracks', 'prizes'), slug=slug)

    is_creator_or_admin = (
        request.user.is_authenticated and (
            request.user == event.created_by or
            getattr(request.user, 'role', None) == 'admin' or
            request.user.is_superuser
        )
    )

    return render(request, 'events/event_detail.html', {
        'event': event,
        'tracks': event.tracks.all(),
        'prizes': event.prizes.all(),
        'is_creator_or_admin': is_creator_or_admin,
    })


@role_required('organizer', 'admin')
def event_create_view(request):
    """
    Create a new hackathon with inline tracks and prizes.
    Restricted to organizers and administrators.
    """
    if request.method == 'POST':
        form = EventForm(request.POST)
        track_formset = TrackFormSet(request.POST, prefix='tracks')
        prize_formset = PrizeFormSet(request.POST, prefix='prizes')

        if form.is_valid() and track_formset.is_valid() and prize_formset.is_valid():
            event = form.save(commit=False)
            event.created_by = request.user
            event.save()

            track_formset.instance = event
            track_formset.save()

            prize_formset.instance = event
            prize_formset.save()

            return redirect('event_detail', slug=event.slug)
    else:
        form = EventForm()
        track_formset = TrackFormSet(prefix='tracks')
        prize_formset = PrizeFormSet(prefix='prizes')

    return render(request, 'events/event_form.html', {
        'form': form,
        'track_formset': track_formset,
        'prize_formset': prize_formset,
        'title': 'Create New Hackathon Event',
        'button_text': 'Create Event',
    })


@role_required('organizer', 'admin')
def event_edit_view(request, slug):
    """
    Edit an existing event.
    Restricted to the event creator or administrators.
    Rejects modification of start_date and submission_deadline once an event is open and started.
    """
    event = get_object_or_404(Event, slug=slug)

    # Permission check: Creator or Admin only
    if not (request.user == event.created_by or getattr(request.user, 'role', None) == 'admin' or request.user.is_superuser):
        raise PermissionDenied("You do not have permission to edit this event.")

    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        track_formset = TrackFormSet(request.POST, instance=event, prefix='tracks')
        prize_formset = PrizeFormSet(request.POST, instance=event, prefix='prizes')

        if form.is_valid() and track_formset.is_valid() and prize_formset.is_valid():
            form.save()
            track_formset.save()
            prize_formset.save()
            return redirect('event_detail', slug=event.slug)
    else:
        form = EventForm(instance=event)
        track_formset = TrackFormSet(instance=event, prefix='tracks')
        prize_formset = PrizeFormSet(instance=event, prefix='prizes')

    return render(request, 'events/event_form.html', {
        'form': form,
        'track_formset': track_formset,
        'prize_formset': prize_formset,
        'event': event,
        'title': f'Edit Event: {event.name}',
        'button_text': 'Save Changes',
    })
