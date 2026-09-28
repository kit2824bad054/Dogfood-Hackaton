"""
Views for community voting, comments, moderation, and organizer audit logs.
"""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.decorators import role_required
from apps.community.models import AuditLog, Comment, Vote
from apps.community.services import (
    cast_or_update_vote,
    get_submission_community_stats,
    post_comment,
    set_comment_hidden_status,
)
from apps.events.models import Event
from apps.submissions.models import Submission

User = get_user_model()


@require_POST
def cast_vote_view(request, submission_id):
    """
    Endpoint for participants to cast or change a 1-5 star community vote.
    Supports both traditional form submissions and AJAX/JSON requests.
    """
    submission = get_object_or_404(
        Submission.objects.select_related('event', 'team'),
        id=submission_id
    )

    if not request.user.is_authenticated:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({'error': "Authentication required to vote."}, status=401)
        messages.error(request, "You must be signed in to vote.")
        return redirect('gallery_detail', submission_id=submission.id)

    raw_value = request.POST.get('value', '').strip()
    success, message, vote_obj, status_code = cast_or_update_vote(request.user, submission, raw_value)

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json'

    if not success:
        if is_ajax:
            return JsonResponse({'error': message}, status=status_code)
        if status_code == 429:
            return HttpResponse(message, status=429)
        if status_code == 403:
            return HttpResponseForbidden(message)
        if status_code == 400:
            return HttpResponseBadRequest(message)
        messages.error(request, message)
        return redirect('gallery_detail', submission_id=submission.id)

    if is_ajax:
        stats = get_submission_community_stats(submission, viewer=request.user)
        return JsonResponse({
            'success': True,
            'message': message,
            'user_vote': vote_obj.value,
            'stats': stats,
        }, status=status_code)

    messages.success(request, message)
    return redirect('gallery_detail', submission_id=submission.id)


@require_POST
def post_comment_view(request, submission_id):
    """
    Endpoint for users to submit feedback comments on a project submission.
    """
    submission = get_object_or_404(
        Submission.objects.select_related('event'),
        id=submission_id
    )

    if not request.user.is_authenticated:
        messages.error(request, "You must be signed in to post a comment.")
        return redirect('gallery_detail', submission_id=submission.id)

    body = request.POST.get('body', '').strip()
    success, message, comment_obj, status_code = post_comment(request.user, submission, body)

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json'

    if not success:
        if is_ajax:
            return JsonResponse({'error': message}, status=status_code)
        if status_code == 429:
            return HttpResponse(message, status=429)
        if status_code == 400:
            return HttpResponseBadRequest(message)
        messages.error(request, message)
        return redirect('gallery_detail', submission_id=submission.id)

    if is_ajax:
        return JsonResponse({
            'success': True,
            'message': message,
            'comment': {
                'id': comment_obj.id,
                'author': comment_obj.user.username,
                'body': comment_obj.body,
                'created_at': comment_obj.created_at.strftime('%b %d, %Y %H:%M'),
                'is_flagged_duplicate': comment_obj.is_flagged_duplicate,
            }
        }, status=201)

    messages.success(request, message)
    return redirect('gallery_detail', submission_id=submission.id)


@require_POST
@login_required
@role_required(User.Role.ORGANIZER, User.Role.ADMIN)
def moderate_comment_view(request, comment_id):
    """
    Organizer moderation endpoint to soft-hide or unhide comments.
    """
    comment = get_object_or_404(
        Comment.objects.select_related('submission__event', 'user'),
        id=comment_id
    )
    event = comment.submission.event

    # Scoped authorization: organizers can only moderate comments in events they own
    if request.user.role == User.Role.ORGANIZER and not request.user.is_superuser:
        if event.created_by != request.user:
            return HttpResponseForbidden("You are not authorized to moderate comments for this event.")

    action = request.POST.get('action', 'hide').lower().strip()
    should_hide = (action == 'hide')

    set_comment_hidden_status(comment, is_hidden=should_hide, operator=request.user)

    action_label = "hidden" if should_hide else "restored"
    messages.success(request, f"Comment by @{comment.user.username} has been {action_label}.")

    next_url = request.POST.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('gallery_detail', submission_id=comment.submission.id)


@login_required
@role_required(User.Role.ORGANIZER, User.Role.ADMIN)
def audit_log_view(request, event_slug=None):
    """
    Organizer audit log browser.
    Displays all votes, changes, comments, rate limits, and moderation actions.
    Filterable by user and action type.
    """
    qs = AuditLog.objects.select_related('user', 'target_submission__event').order_by('-timestamp')

    selected_event = None
    if event_slug:
        selected_event = get_object_or_404(Event, slug=event_slug)
        # Event ownership restriction for organizers
        if request.user.role == User.Role.ORGANIZER and not request.user.is_superuser:
            if selected_event.created_by != request.user:
                raise PermissionDenied("You do not have permission to view audit logs for this event.")
        qs = qs.filter(target_submission__event=selected_event)
    elif request.user.role == User.Role.ORGANIZER and not request.user.is_superuser:
        # Limit to events created by this organizer
        qs = qs.filter(target_submission__event__created_by=request.user)

    # Filter by action type
    action_filter = request.GET.get('action', '').strip()
    if action_filter:
        qs = qs.filter(action=action_filter)

    # Filter by username
    user_filter = request.GET.get('user', '').strip()
    if user_filter:
        qs = qs.filter(user__username__icontains=user_filter)

    # Filter by submission ID/title
    query = request.GET.get('q', '').strip()
    if query:
        qs = qs.filter(target_submission__title__icontains=query)

    # Pagination or top 100 entries for audit inspection
    audit_logs = qs[:150]

    context = {
        'audit_logs': audit_logs,
        'action_choices': AuditLog.Action.choices,
        'selected_action': action_filter,
        'selected_user': user_filter,
        'search_query': query,
        'event': selected_event,
        'total_count': qs.count(),
    }
    return render(request, 'community/audit_logs.html', context)


@login_required
@role_required(User.Role.ORGANIZER, User.Role.ADMIN)
def manage_event_voting_view(request, event_slug):
    """
    Organizer configuration view to toggle voting, adjust time window,
    and configure results visibility during voting.
    """
    event = get_object_or_404(Event, slug=event_slug)

    if request.user.role == User.Role.ORGANIZER and not request.user.is_superuser:
        if event.created_by != request.user:
            raise PermissionDenied("You can only configure voting for your own events.")

    if request.method == 'POST':
        event.voting_enabled = (request.POST.get('voting_enabled') == 'on')
        event.results_visible_during_voting = (request.POST.get('results_visible_during_voting') == 'on')

        opens_at_str = request.POST.get('voting_opens_at', '').strip()
        closes_at_str = request.POST.get('voting_closes_at', '').strip()

        event.voting_opens_at = opens_at_str if opens_at_str else None
        event.voting_closes_at = closes_at_str if closes_at_str else None

        event.save()
        messages.success(request, f"Voting configuration for '{event.name}' updated successfully.")
        return redirect('event_voting_manage', event_slug=event.slug)

    context = {
        'event': event,
        'is_voting_open': event.is_voting_open,
    }
    return render(request, 'community/voting_manage.html', context)
