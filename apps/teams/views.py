"""Views for hackathon team formation, invite code joins, and roster management."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.accounts.decorators import role_required
from apps.events.models import Event
from .forms import TeamCreateForm, JoinInviteForm
from .models import (
    Team,
    TeamMembership,
    get_user_team_for_event,
    user_has_team_in_event,
    validate_user_can_join_event_team,
)

User = get_user_model()


@role_required('participant')
def team_create_view(request, event_slug):
    """
    Allow a participant to create a team for an event.
    Automatically adds creator as the first member.
    Enforces registration deadline and one-team-per-event constraint.
    """
    event = get_object_or_404(Event, slug=event_slug)

    # 1. Validate eligibility (role, registration deadline, one-team constraint)
    can_join, err_msg = validate_user_can_join_event_team(request.user, event)
    if not can_join:
        return render(request, 'teams/team_error.html', {
            'event': event,
            'title': 'Cannot Form Team',
            'error_message': err_msg,
        }, status=400)

    if request.method == 'POST':
        form = TeamCreateForm(request.POST, event=event)
        if form.is_valid():
            team = form.save(commit=False)
            team.event = event
            team.created_by = request.user
            team.save()

            # Automatically create creator membership
            TeamMembership.objects.create(team=team, user=request.user)

            messages.success(request, f"Team '{team.name}' created successfully! Share your invite code with teammates.")
            return redirect('team_detail', team_id=team.id)
    else:
        form = TeamCreateForm(event=event)

    return render(request, 'teams/team_form.html', {
        'form': form,
        'event': event,
        'title': f'Create Team for {event.name}',
    })


@login_required
def team_join_view(request, invite_code=None):
    """
    Join a team via an invite code.
    Validates:
    - User is logged in and role is 'participant'
    - Invite code is valid
    - Event registration deadline is open
    - Team is not already full
    - User does not already belong to ANY team in this event
    """
    # 1. Role validation
    if getattr(request.user, 'role', None) != 'participant':
        raise PermissionDenied("Only participants can create or join hackathon teams.")

    # If code was submitted via manual input form
    if request.method == 'POST' and not invite_code:
        form = JoinInviteForm(request.POST)
        if form.is_valid():
            return redirect('team_join_code', invite_code=form.cleaned_data['invite_code'])
        return render(request, 'teams/team_join_input.html', {'form': form})

    if not invite_code:
        return render(request, 'teams/team_join_input.html', {'form': JoinInviteForm()})

    # Look up team by invite code
    team = Team.objects.filter(invite_code=invite_code).select_related('event', 'created_by').first()
    if not team:
        return render(request, 'teams/team_error.html', {
            'title': 'Invalid Invite Code',
            'error_message': f"The invite code '{invite_code}' does not exist or has expired.",
        }, status=404)

    event = team.event

    # Check if user is already in this team
    if team.has_member(request.user):
        messages.info(request, "You are already a registered member of this team.")
        return redirect('team_detail', team_id=team.id)

    # Check registration deadline
    if not event.is_registration_open:
        return render(request, 'teams/team_error.html', {
            'event': event,
            'team': team,
            'title': 'Registration Closed',
            'error_message': f"Registration for '{event.name}' closed on {event.registration_deadline.strftime('%B %d, %Y at %I:%M %p')}. New team members cannot join.",
        }, status=400)

    # Check if team is full
    if team.is_full:
        return render(request, 'teams/team_error.html', {
            'event': event,
            'team': team,
            'title': 'Team Full',
            'error_message': f"Team '{team.name}' has already reached its maximum capacity of {team.max_members} members.",
        }, status=400)

    # Check one-team-per-event constraint
    if user_has_team_in_event(request.user, event):
        current_team = get_user_team_for_event(request.user, event)
        return render(request, 'teams/team_error.html', {
            'event': event,
            'team': team,
            'title': 'Already On a Team',
            'error_message': f"You are already a member of team '{current_team.name}' in this hackathon. Participants may only belong to one team per event.",
        }, status=400)

    # Handle confirmation POST or preview GET
    if request.method == 'POST':
        TeamMembership.objects.create(team=team, user=request.user)
        messages.success(request, f"You have successfully joined '{team.name}' for {event.name}!")
        return redirect('team_detail', team_id=team.id)

    return render(request, 'teams/team_join_confirm.html', {
        'team': team,
        'event': event,
        'member_count': team.member_count,
    })


@login_required
def team_detail_view(request, team_id):
    """
    Roster & team management view.
    Displays current members, invite code, and actions.
    Restricts member deletion to team creator before submission deadline.
    """
    team = get_object_or_404(Team.objects.select_related('event', 'created_by').prefetch_related('memberships__user'), pk=team_id)
    event = team.event

    is_creator = (request.user == team.created_by)
    is_member = team.has_member(request.user)
    is_admin_or_organizer = (
        getattr(request.user, 'role', None) in ['organizer', 'admin'] or
        request.user.is_superuser or
        event.created_by == request.user
    )

    # Permission: team roster view is accessible to members, event organizers, and admins
    if not (is_member or is_admin_or_organizer):
        raise PermissionDenied("You do not have permission to view this team's roster.")

    # Full invite URL
    invite_url = request.build_absolute_uri(reverse('team_join_code', kwargs={'invite_code': team.invite_code}))

    return render(request, 'teams/team_detail.html', {
        'team': team,
        'event': event,
        'memberships': team.memberships.select_related('user').all(),
        'is_creator': is_creator,
        'is_member': is_member,
        'is_admin_or_organizer': is_admin_or_organizer,
        'invite_url': invite_url,
        'can_remove_members': is_creator and event.is_submission_open,
    })


@login_required
def team_remove_member_view(request, team_id, user_id):
    """
    Allow team creator to remove a member before the submission deadline.
    Rejects removal if:
    - User is not the creator
    - Creator tries to remove themselves
    - Submission deadline has passed
    """
    if request.method != 'POST':
        return redirect('team_detail', team_id=team_id)

    team = get_object_or_404(Team.objects.select_related('event', 'created_by'), pk=team_id)
    event = team.event

    # 1. Creator permission check
    if request.user != team.created_by:
        raise PermissionDenied("Only the team creator can remove team members.")

    # 2. Cannot remove self
    if request.user.id == user_id:
        messages.error(request, "Team creator cannot remove themselves from the team.")
        return redirect('team_detail', team_id=team.id)

    # 3. Submission deadline check
    if not event.is_submission_open:
        messages.error(request, "Team members cannot be removed after the project submission deadline has passed.")
        return redirect('team_detail', team_id=team.id)

    membership = TeamMembership.objects.filter(team=team, user_id=user_id).first()
    if membership:
        removed_username = membership.user.username
        membership.delete()
        messages.success(request, f"Removed '{removed_username}' from the team.")

    return redirect('team_detail', team_id=team.id)


@login_required
def my_team_view(request, event_slug):
    """
    Show current user's team for an event, or options to create/join if they don't have one.
    """
    event = get_object_or_404(Event, slug=event_slug)
    team = get_user_team_for_event(request.user, event)

    if team:
        return redirect('team_detail', team_id=team.id)

    return render(request, 'teams/my_team_empty.html', {
        'event': event,
        'is_participant': getattr(request.user, 'role', None) == 'participant',
    })
