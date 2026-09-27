"""
Views for project submissions in the Dogfood Platform.

Phase 5: Submissions create/edit views with server-side deadline enforcement,
team-scoped permissions, collaborative editing, submit/un-submit lifecycle,
and organizer/admin submission dashboard.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.decorators import role_required
from apps.events.models import Event
from apps.teams.models import Team, get_user_team_for_event
from .forms import SubmissionForm
from .models import Submission


@login_required
def team_submission_status_view(request, team_id):
    """
    Status and overview page for a team's submission.

    Only accessible by members of the team.
    Shows the current state (draft vs submitted), deadline countdown/notice,
    and actions to create, edit, submit, or un-submit.
    """
    team = get_object_or_404(Team, id=team_id)

    # Permission check: User must be a member of the team
    if not team.has_member(request.user):
        raise PermissionDenied("You are not a member of this team.")

    submission = getattr(team, 'submission', None)
    event = team.event

    return render(request, 'submissions/team_submission_status.html', {
        'team': team,
        'event': event,
        'submission': submission,
        'is_submission_open': event.is_submission_open,
    })


@login_required
def submission_edit_view(request, team_id):
    """
    Create or edit a team's project submission draft.

    Access:
    - Only members of the team can create or edit.
    - Multiple team members can collaboratively edit the shared draft.

    Deadline Enforcement:
    - Check event.is_submission_open on EVERY write path (POST).
    - If deadline has passed:
      - POST is rejected with HTTP 400.
      - GET renders a read-only display view (no form inputs).
    - If status is 'submitted' and deadline has not passed:
      - Edits are blocked until user un-submits back to draft.
    """
    team = get_object_or_404(Team, id=team_id)

    # Permission check: User must be a member of the team
    if not team.has_member(request.user):
        raise PermissionDenied("You are not a member of this team.")

    event = team.event

    # Retrieve existing submission or create initial draft row
    submission = getattr(team, 'submission', None)

    # Server-side deadline check
    if not event.is_submission_open:
        if request.method == 'POST':
            return render(request, 'submissions/submission_error.html', {
                'title': 'Submission Deadline Passed',
                'team': team,
                'event': event,
                'error_message': (
                    f"The submission deadline for '{event.name}' passed on "
                    f"{event.submission_deadline.strftime('%B %d, %Y at %I:%M %p')}. "
                    "Draft edits and submissions are no longer accepted."
                ),
            }, status=400)

        # GET after deadline renders as read-only view
        return render(request, 'submissions/submission_readonly.html', {
            'team': team,
            'event': event,
            'submission': submission,
            'deadline_passed': True,
        })

    # If submission already exists and is in 'submitted' state
    if submission and submission.is_submitted:
        if request.method == 'POST':
            return render(request, 'submissions/submission_error.html', {
                'title': 'Project Already Submitted',
                'team': team,
                'event': event,
                'error_message': (
                    "This project has already been submitted. Please un-submit back to "
                    "draft before making further edits."
                ),
            }, status=400)

        # On GET, inform user to un-submit before editing
        return render(request, 'submissions/submission_readonly.html', {
            'team': team,
            'event': event,
            'submission': submission,
            'deadline_passed': False,
            'can_unsubmit': True,
        })

    # Get or create submission draft
    if not submission:
        submission = Submission.objects.create(
            team=team,
            event=event,
            status=Submission.Status.DRAFT,
        )

    if request.method == 'POST':
        form = SubmissionForm(request.POST, instance=submission, event=event)
        if form.is_valid():
            form.save()
            messages.success(request, "Project submission draft saved successfully.")
            return redirect('team_submission_status', team_id=team.id)
    else:
        form = SubmissionForm(instance=submission, event=event)

    return render(request, 'submissions/submission_form.html', {
        'team': team,
        'event': event,
        'submission': submission,
        'form': form,
    })


@login_required
def submission_submit_view(request, team_id):
    """
    Finalize and submit a project (draft -> submitted).

    Enforces:
    - Member of team check
    - POST method only
    - Server-side deadline check (event.is_submission_open)
    - Required fields check (title, description, repo_url must be non-empty)
    - Sets status='submitted' and submitted_at=timezone.now()
    """
    team = get_object_or_404(Team, id=team_id)

    if not team.has_member(request.user):
        raise PermissionDenied("You are not a member of this team.")

    if request.method != 'POST':
        return redirect('team_submission_status', team_id=team.id)

    event = team.event

    # 1. Deadline check
    if not event.is_submission_open:
        return render(request, 'submissions/submission_error.html', {
            'title': 'Submission Deadline Passed',
            'team': team,
            'event': event,
            'error_message': (
                f"The submission deadline for '{event.name}' passed on "
                f"{event.submission_deadline.strftime('%B %d, %Y at %I:%M %p')}. "
                "Final project submissions can no longer be accepted."
            ),
        }, status=400)

    # 2. Check submission exists
    submission = getattr(team, 'submission', None)
    if not submission:
        return render(request, 'submissions/submission_error.html', {
            'title': 'No Submission Draft Found',
            'team': team,
            'event': event,
            'error_message': "You must create and save a draft before submitting.",
        }, status=400)

    # 3. Required fields check
    missing = []
    if not (submission.title and submission.title.strip()):
        missing.append("Project Title")
    if not (submission.description and submission.description.strip()):
        missing.append("Project Description")
    if not (submission.repo_url and submission.repo_url.strip()):
        missing.append("Repository URL")

    if missing:
        error_msg = f"Cannot submit project. The following required fields are missing: {', '.join(missing)}."
        return render(request, 'submissions/submission_error.html', {
            'title': 'Incomplete Submission',
            'team': team,
            'event': event,
            'error_message': error_msg,
            'can_edit': True,
        }, status=400)

    # 4. Mark as submitted
    submission.status = Submission.Status.SUBMITTED
    submission.submitted_at = timezone.now()
    submission.save()

    messages.success(request, f"Congratulations! Project '{submission.title}' has been successfully submitted!")
    return redirect('team_submission_status', team_id=team.id)


@login_required
def submission_unsubmit_view(request, team_id):
    """
    Revert a submitted project back to draft for further editing.

    Enforces:
    - Member of team check
    - POST method only
    - Server-side deadline check (event.is_submission_open) - cannot un-submit after deadline!
    """
    team = get_object_or_404(Team, id=team_id)

    if not team.has_member(request.user):
        raise PermissionDenied("You are not a member of this team.")

    if request.method != 'POST':
        return redirect('team_submission_status', team_id=team.id)

    event = team.event

    # Deadline check
    if not event.is_submission_open:
        return render(request, 'submissions/submission_error.html', {
            'title': 'Submission Deadline Passed',
            'team': team,
            'event': event,
            'error_message': (
                "The submission deadline has passed. Projects cannot be un-submitted "
                "or modified after the deadline."
            ),
        }, status=400)

    submission = getattr(team, 'submission', None)
    if submission and submission.is_submitted:
        submission.status = Submission.Status.DRAFT
        submission.submitted_at = None
        submission.save()
        messages.info(request, "Project un-submitted and reverted to draft. You may now continue editing.")

    return redirect('team_submission_status', team_id=team.id)


@role_required('organizer', 'admin')
def event_submissions_list_view(request, event_slug):
    """
    Organizer and Administrator view of all submissions for an event.

    - Organizers can only view submissions for events they created.
    - Platform Admins and Superusers can view submissions for any event.
    - Read-only: no editing submissions created by teams.
    """
    event = get_object_or_404(Event, slug=event_slug)

    # Authorization: Organizers can only see their own event
    is_admin = getattr(request.user, 'role', None) == 'admin' or request.user.is_superuser
    if not is_admin and event.created_by != request.user:
        raise PermissionDenied("You do not have permission to view submissions for events you do not organize.")

    submissions = event.submissions.select_related('team', 'track').prefetch_related('team__memberships__user').all()

    total_count = submissions.count()
    submitted_count = submissions.filter(status=Submission.Status.SUBMITTED).count()
    draft_count = submissions.filter(status=Submission.Status.DRAFT).count()

    return render(request, 'submissions/event_submissions_list.html', {
        'event': event,
        'submissions': submissions,
        'total_count': total_count,
        'submitted_count': submitted_count,
        'draft_count': draft_count,
    })


@login_required
def event_my_submission_redirect_view(request, event_slug):
    """
    Convenience view to route a participant directly to their team's submission status.
    """
    event = get_object_or_404(Event, slug=event_slug)
    team = get_user_team_for_event(request.user, event)
    if team:
        return redirect('team_submission_status', team_id=team.id)

    messages.info(request, "You must form or join a team for this event before working on a submission.")
    return redirect('my_team', event_slug=event.slug)
