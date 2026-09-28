"""
Core business logic, anti-abuse controls, rate-limiting, and auditing for Phase 8 / T3.
"""

import time
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache
from django.db.models import Avg, Count
from django.utils import timezone

from apps.community.models import AuditLog, Comment, EventRegistration, Vote
from apps.teams.models import TeamMembership


def is_user_event_participant(event, user):
    """
    Check if a user is an eligible participant for the given event.
    Participant verification relies on:
    1. TeamMembership in any team belonging to this event, OR
    2. Explicit EventRegistration record for this event.
    """
    if not user or not user.is_authenticated:
        return False
    
    # Check TeamMembership (T1 participant registration)
    if TeamMembership.objects.filter(team__event=event, user=user).exists():
        return True

    # Check explicit EventRegistration record
    if EventRegistration.objects.filter(event=event, user=user).exists():
        return True

    return False


def check_rate_limit(user_id, action_type='vote', limit=20, window_seconds=60):
    """
    Sliding-window timestamp rate limiter backed by Django's cache framework.
    Prevents scripted rapid-fire voting or commenting abuse.

    Args:
        user_id: ID of the authenticated user
        action_type: 'vote' or 'comment'
        limit: Maximum allowed actions within window (default 20)
        window_seconds: Time window in seconds (default 60)

    Returns:
        (is_allowed: bool, current_count: int, retry_after: int)
    """
    cache_key = f"community_rate_limit:{action_type}:{user_id}"
    now = time.time()

    # Retrieve existing action timestamps list
    timestamps = cache.get(cache_key, [])
    # Retain only timestamps within the sliding window
    valid_timestamps = [ts for ts in timestamps if now - ts < window_seconds]

    if len(valid_timestamps) >= limit:
        oldest_in_window = valid_timestamps[0]
        retry_after = max(1, int(window_seconds - (now - oldest_in_window)))
        return False, len(valid_timestamps), retry_after

    # Record current action timestamp
    valid_timestamps.append(now)
    cache.set(cache_key, valid_timestamps, timeout=window_seconds + 10)
    return True, len(valid_timestamps), 0


def log_community_action(action, user, target_submission=None, metadata=None):
    """
    Create a permanent audit log entry for community actions and abuse triggers.
    """
    if metadata is None:
        metadata = {}
    return AuditLog.objects.create(
        user=user if (user and user.is_authenticated) else None,
        action=action,
        target_submission=target_submission,
        metadata=metadata
    )


def check_voting_eligibility(user, submission):
    """
    Validate that a user is permitted to vote on a specific project submission.

    Rules:
    1. User must be authenticated.
    2. Event voting must be currently active (event.is_voting_open).
    3. User cannot vote on their own team's submission.
    4. User must be a registered participant of this event.

    Returns:
        (is_eligible: bool, error_message: str)
    """
    if not user or not user.is_authenticated:
        return False, "You must be signed in to cast a community vote."

    event = submission.event
    if not event.is_voting_open:
        return False, "Community voting is not currently open for this event."

    # Prevent self-team voting (anti-collusion)
    if submission.team and TeamMembership.objects.filter(team=submission.team, user=user).exists():
        return False, "You cannot vote on your own team's submission."

    # Enforce participant-only voting (anti-Sybil)
    if not is_user_event_participant(event, user):
        return False, "Only registered participants of this hackathon can vote on submissions."

    return True, ""


def can_view_voting_results(event, user):
    """
    Determine if aggregate vote counts, averages, and rankings should be visible.

    Rules:
    1. If voting is disabled entirely: False.
    2. If voting is NOT open (i.e. voting window has closed): True (visible to all).
    3. If voting IS open:
       - If event.results_visible_during_voting is True: True (visible to all).
       - If event.results_visible_during_voting is False: ONLY organizers and admins can see results.
    """
    if not event.voting_enabled:
        return False

    if not event.is_voting_open:
        # Voting has concluded -> final results are public
        return True

    # Voting is currently open
    if event.results_visible_during_voting:
        return True

    # During hidden-results voting, restrict to organizers and admins
    if user and user.is_authenticated and (user.role in ['organizer', 'admin'] or user.is_superuser):
        return True

    return False


def detect_duplicate_comment(user, submission, body, window_minutes=15):
    """
    Detect near-identical comment bodies posted by the same user on the same submission
    within a short time window (default 15 minutes).
    Flagged for organizer review rather than hard-blocked.
    """
    if not user or not user.is_authenticated:
        return False

    cutoff = timezone.now() - timedelta(minutes=window_minutes)
    normalized_body = " ".join(body.strip().lower().split())

    recent_comments = Comment.objects.filter(
        submission=submission,
        user=user,
        created_at__gte=cutoff
    )
    for c in recent_comments:
        if " ".join(c.body.strip().lower().split()) == normalized_body:
            return True

    return False


def cast_or_update_vote(user, submission, value):
    """
    Cast or update a 1-5 star community rating on a submission.
    Enforces rate limits, eligibility, and records audit trail.

    Returns:
        (success: bool, message: str, vote_obj: Vote or None, status_code: int)
    """
    # 1. Rate Limit Enforcement (max 20 votes per 60 seconds)
    allowed, current_count, retry_after = check_rate_limit(user.id, action_type='vote', limit=20, window_seconds=60)
    if not allowed:
        log_community_action(
            action=AuditLog.Action.RATE_LIMIT_TRIGGERED,
            user=user,
            target_submission=submission,
            metadata={
                'action_type': 'vote',
                'limit': 20,
                'window_seconds': 60,
                'retry_after': retry_after,
            }
        )
        return False, f"Rate limit exceeded. Too many votes submitted. Please retry in {retry_after} seconds.", None, 429

    # 2. Eligibility & Window Check
    eligible, err_msg = check_voting_eligibility(user, submission)
    if not eligible:
        return False, err_msg, None, 403

    # 3. Value Validation
    try:
        val_int = int(value)
        if val_int < 1 or val_int > 5:
            return False, "Rating must be an integer between 1 and 5 stars.", None, 400
    except (ValueError, TypeError):
        return False, "Invalid rating value provided.", None, 400

    # 4. Check for existing vote (re-voting updates the existing row)
    existing_vote = Vote.objects.filter(submission=submission, user=user).first()
    if existing_vote:
        old_val = existing_vote.value
        existing_vote.value = val_int
        existing_vote.save()
        log_community_action(
            action=AuditLog.Action.VOTE_CHANGED,
            user=user,
            target_submission=submission,
            metadata={'old_value': old_val, 'new_value': val_int}
        )
        return True, "Your vote has been updated!", existing_vote, 200
    else:
        new_vote = Vote.objects.create(submission=submission, user=user, value=val_int)
        log_community_action(
            action=AuditLog.Action.VOTE_CAST,
            user=user,
            target_submission=submission,
            metadata={'value': val_int}
        )
        return True, "Your vote has been recorded!", new_vote, 201


def post_comment(user, submission, body):
    """
    Submit a community feedback comment on a submission.
    Enforces rate limits, participant/auth checks, duplicate detection, and audit logging.

    Returns:
        (success: bool, message: str, comment_obj: Comment or None, status_code: int)
    """
    if not user or not user.is_authenticated:
        return False, "You must be signed in to post a comment.", None, 401

    body_clean = body.strip()
    if not body_clean:
        return False, "Comment body cannot be blank.", None, 400

    # Rate limiting (max 10 comments per 60 seconds)
    allowed, current_count, retry_after = check_rate_limit(user.id, action_type='comment', limit=10, window_seconds=60)
    if not allowed:
        log_community_action(
            action=AuditLog.Action.RATE_LIMIT_TRIGGERED,
            user=user,
            target_submission=submission,
            metadata={
                'action_type': 'comment',
                'limit': 10,
                'window_seconds': 60,
                'retry_after': retry_after,
            }
        )
        return False, f"Rate limit exceeded. Please wait {retry_after} seconds before posting again.", None, 429

    # Duplicate detection (flag, don't hard block)
    is_duplicate = detect_duplicate_comment(user, submission, body_clean)

    comment = Comment.objects.create(
        submission=submission,
        user=user,
        body=body_clean,
        is_flagged_duplicate=is_duplicate
    )

    log_community_action(
        action=AuditLog.Action.COMMENT_POSTED,
        user=user,
        target_submission=submission,
        metadata={
            'comment_id': comment.id,
            'is_duplicate_flag': is_duplicate,
            'body_snippet': body_clean[:80],
        }
    )

    msg = "Comment posted successfully!"
    if is_duplicate:
        msg = "Comment posted (flagged for review as duplicate content)."
    return True, msg, comment, 201


def set_comment_hidden_status(comment, is_hidden, operator):
    """
    Organizer moderation action to soft-hide or unhide a comment.
    """
    comment.is_hidden = is_hidden
    if is_hidden:
        comment.hidden_at = timezone.now()
        comment.hidden_by = operator
        action = AuditLog.Action.COMMENT_HIDDEN
    else:
        comment.hidden_at = None
        comment.hidden_by = None
        action = AuditLog.Action.COMMENT_UNHIDDEN
    comment.save()

    log_community_action(
        action=action,
        user=operator,
        target_submission=comment.submission,
        metadata={
            'comment_id': comment.id,
            'author_username': comment.user.username,
            'body_snippet': comment.body[:80],
        }
    )
    return comment


def get_submission_community_stats(submission, viewer=None):
    """
    Compute community voting statistics for a submission, strictly respecting
    the results_visible_during_voting privacy rules.
    """
    event = submission.event
    results_visible = can_view_voting_results(event, viewer)

    if not results_visible:
        return {
            'results_visible': False,
            'vote_count': None,
            'avg_rating': None,
            'voting_open': event.is_voting_open,
            'voting_enabled': event.voting_enabled,
        }

    agg = submission.votes.aggregate(
        avg_score=Avg('value'),
        count=Count('id')
    )
    avg_score = agg['avg_score']
    if avg_score is not None:
        avg_score = round(float(avg_score), 2)

    return {
        'results_visible': True,
        'vote_count': agg['count'],
        'avg_rating': avg_score,
        'voting_open': event.is_voting_open,
        'voting_enabled': event.voting_enabled,
    }
