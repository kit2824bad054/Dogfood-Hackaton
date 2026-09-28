"""
Comprehensive unit and integration test suite for Judging (Phase 7 / Tier 2).

Tests:
1. Judge can only view/score their assigned submissions (403 on others, tested directly against the endpoint).
2. Judge cannot see another judge's scores for a shared submission (query & view isolation).
3. Rubric weights not summing to 100 is rejected at save time.
4. Score exceeding rubric max_score is rejected.
5. Assignment algorithm doesn't assign a judge who is also a team member of that submission.
6. Re-running assignment doesn't duplicate JudgeAssignment rows.
7. Normalization function produces expected output on a small hand-calculated fixture (2 judges, 3 submissions).
8. Marking scoring "complete" without all criteria filled is rejected.
9. CSV export is organizer/admin-only, scoped to their own event.
"""

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.events.models import Event
from apps.judging.models import EventJudge, JudgeAssignment, Rubric, Score
from apps.judging.services import (
    assign_judges_to_event,
    get_event_rankings,
    normalize_event_scores,
)
from apps.submissions.models import Submission
from apps.teams.models import Team, TeamMembership

User = get_user_model()


class JudgingTestCaseBase(TestCase):
    """Base test case setting up common users, events, and submissions."""

    def setUp(self):
        self.client = Client()
        self.now = timezone.now()

        # Users
        self.admin = User.objects.create_superuser(
            username='judge_admin',
            email='admin@test.local',
            password='Password123!'
        )
        self.organizer1 = User.objects.create_user(
            username='judge_org1',
            email='org1@test.local',
            password='Password123!',
            role=User.Role.ORGANIZER
        )
        self.organizer2 = User.objects.create_user(
            username='judge_org2',
            email='org2@test.local',
            password='Password123!',
            role=User.Role.ORGANIZER
        )
        self.judge1 = User.objects.create_user(
            username='eval_judge1',
            email='judge1@test.local',
            password='Password123!',
            role=User.Role.JUDGE
        )
        self.judge2 = User.objects.create_user(
            username='eval_judge2',
            email='judge2@test.local',
            password='Password123!',
            role=User.Role.JUDGE
        )
        self.participant1 = User.objects.create_user(
            username='dev_part1',
            email='part1@test.local',
            password='Password123!',
            role=User.Role.PARTICIPANT
        )
        self.participant2 = User.objects.create_user(
            username='dev_part2',
            email='part2@test.local',
            password='Password123!',
            role=User.Role.PARTICIPANT
        )

        # Event
        self.event = Event.objects.create(
            name="Judging Championship 2026",
            slug="judging-championship-2026",
            description="Testing judging algorithms and isolation.",
            status=Event.Status.OPEN,
            gallery_enabled=True,
            start_date=self.now,
            registration_deadline=self.now,
            submission_deadline=self.now,
            end_date=self.now,
            created_by=self.organizer1
        )

        # EventJudge invitations (judge1 and judge2 accepted for self.event)
        self.invitation1 = EventJudge.objects.create(
            event=self.event,
            invited_by=self.organizer1,
            user=self.judge1,
            email=self.judge1.email,
            status=EventJudge.Status.ACCEPTED,
            responded_at=self.now
        )
        self.invitation2 = EventJudge.objects.create(
            event=self.event,
            invited_by=self.organizer1,
            user=self.judge2,
            email=self.judge2.email,
            status=EventJudge.Status.ACCEPTED,
            responded_at=self.now
        )

        # Rubric criteria (40% + 30% + 30% = 100%)

        self.criterion_arch = Rubric.objects.create(
            event=self.event,
            name="Architecture & Code",
            weight=Decimal('40.00'),
            max_score=10
        )
        self.criterion_inno = Rubric.objects.create(
            event=self.event,
            name="Innovation",
            weight=Decimal('30.00'),
            max_score=10
        )
        self.criterion_demo = Rubric.objects.create(
            event=self.event,
            name="Demo Polish",
            weight=Decimal('30.00'),
            max_score=10
        )

        # Team & Submission 1
        self.team1 = Team.objects.create(
            event=self.event,
            name="Team CyberPulse",
            created_by=self.participant1
        )
        TeamMembership.objects.create(team=self.team1, user=self.participant1)
        self.sub1 = Submission.objects.create(
            team=self.team1,
            event=self.event,
            title="CyberPulse Security Agent",
            description="Intelligent defense bot.",
            repo_url="https://github.com/test/cyberpulse",
            status=Submission.Status.SUBMITTED,
            submitted_at=self.now
        )

        # Team & Submission 2
        self.team2 = Team.objects.create(
            event=self.event,
            name="Team QuantumMind",
            created_by=self.participant2
        )
        TeamMembership.objects.create(team=self.team2, user=self.participant2)
        self.sub2 = Submission.objects.create(
            team=self.team2,
            event=self.event,
            title="QuantumMind Compiler",
            description="Qubit circuit optimizer.",
            repo_url="https://github.com/test/quantummind",
            status=Submission.Status.SUBMITTED,
            submitted_at=self.now
        )


class JudgeRoleIsolationAndScoringTests(JudgingTestCaseBase):
    """Test suite for backend-enforced judge role isolation and scoring permissions."""

    def test_judge_can_only_view_and_score_assigned_submissions_and_403_on_others(self):
        """
        A judge can ONLY view and score submissions they have been assigned to.
        Accessing an unassigned submission returns HTTP 403 Forbidden.
        """
        # Assign Judge 1 to Submission 1 only
        assignment1 = JudgeAssignment.objects.create(
            judge=self.judge1,
            submission=self.sub1,
            status=JudgeAssignment.Status.NOT_STARTED
        )
        # Assign Judge 2 to Submission 2 only
        assignment2 = JudgeAssignment.objects.create(
            judge=self.judge2,
            submission=self.sub2,
            status=JudgeAssignment.Status.NOT_STARTED
        )

        # 1. Judge 1 accesses assigned assignment 1 -> 200 OK
        self.client.login(username='eval_judge1', password='Password123!')
        resp_allowed = self.client.get(
            reverse('judge_score_submission', kwargs={'assignment_id': assignment1.id})
        )
        self.assertEqual(resp_allowed.status_code, 200)
        self.assertContains(resp_allowed, "CyberPulse Security Agent")

        # 2. Judge 1 directly guesses / accesses unassigned assignment 2 -> 403 Forbidden!
        resp_forbidden = self.client.get(
            reverse('judge_score_submission', kwargs={'assignment_id': assignment2.id})
        )
        self.assertEqual(resp_forbidden.status_code, 403)

        # 3. Judge 1 tries to POST score to unassigned assignment 2 -> 403 Forbidden!
        post_forbidden = self.client.post(
            reverse('judge_score_submission', kwargs={'assignment_id': assignment2.id}),
            {
                'action': 'save_draft',
                f'score_{self.criterion_arch.id}': '8.0',
            }
        )
        self.assertEqual(post_forbidden.status_code, 403)
        self.client.logout()

    def test_judge_cannot_see_another_judges_scores_for_shared_submission(self):
        """
        Judges must be evaluated in strict isolation. A judge cannot see
        another judge's scores or feedback for the same shared submission.
        """
        # Both judges assigned to Submission 1
        assign_j1 = JudgeAssignment.objects.create(judge=self.judge1, submission=self.sub1)
        assign_j2 = JudgeAssignment.objects.create(judge=self.judge2, submission=self.sub1)

        # Judge 1 scores the submission with a confidential comment
        Score.objects.create(
            assignment=assign_j1,
            rubric_criterion=self.criterion_arch,
            raw_score=Decimal('9.50'),
            comment="Confidential observation by Judge 1: Excellent architecture."
        )

        # Judge 2 visits their scoring page for the same submission
        self.client.login(username='eval_judge2', password='Password123!')
        resp = self.client.get(reverse('judge_score_submission', kwargs={'assignment_id': assign_j2.id}))
        self.assertEqual(resp.status_code, 200)

        # Judge 2 MUST NOT see Judge 1's score or comment
        self.assertNotContains(resp, "Confidential observation by Judge 1")
        self.assertNotContains(resp, "9.5")
        self.client.logout()

    def test_marking_scoring_complete_without_all_criteria_filled_is_rejected(self):
        """
        Submitting evaluation as 'complete' requires every rubric criterion to have a score.
        Partial submissions with missing criteria are rejected with HTTP 400.
        """
        assignment = JudgeAssignment.objects.create(judge=self.judge1, submission=self.sub1)
        self.client.login(username='eval_judge1', password='Password123!')

        # Attempt to mark complete with only 1 of 3 criteria scored
        post_resp = self.client.post(
            reverse('judge_score_submission', kwargs={'assignment_id': assignment.id}),
            {
                'action': 'submit_complete',
                f'score_{self.criterion_arch.id}': '8.0',
                # Missing innovation and demo polish criteria!
            }
        )
        self.assertEqual(post_resp.status_code, 400)
        self.assertContains(post_resp, "Score is required for &#x27;Innovation&#x27; to complete evaluation.", status_code=400)

        assignment.refresh_from_db()
        self.assertNotEqual(assignment.status, JudgeAssignment.Status.COMPLETED)

        # Now score all criteria
        post_complete = self.client.post(
            reverse('judge_score_submission', kwargs={'assignment_id': assignment.id}),
            {
                'action': 'submit_complete',
                f'score_{self.criterion_arch.id}': '8.0',
                f'score_{self.criterion_inno.id}': '9.0',
                f'score_{self.criterion_demo.id}': '7.5',
            }
        )
        self.assertEqual(post_complete.status_code, 302)

        assignment.refresh_from_db()
        self.assertEqual(assignment.status, JudgeAssignment.Status.COMPLETED)
        self.assertIsNotNone(assignment.completed_at)

        # Once completed, scores become read-only
        get_readonly = self.client.get(
            reverse('judge_score_submission', kwargs={'assignment_id': assignment.id})
        )
        self.assertEqual(get_readonly.status_code, 200)
        self.assertContains(get_readonly, "Evaluation Completed")
        self.client.logout()


class RubricAndScoreValidationTests(JudgingTestCaseBase):
    """Test suite for rubric weight and score boundary validations."""

    def test_rubric_weights_not_summing_to_100_rejected_at_save_time(self):
        """
        Exceeding 100% total weight for an event is rejected with ValidationError at save time.
        Incomplete rubrics (< 100%) fail validate_event_rubric().
        """
        # Current weights: 40 + 30 + 30 = 100.
        # Adding another criterion with weight 15.00 would make sum 115% > 100% -> MUST FAIL
        excess_criterion = Rubric(
            event=self.event,
            name="Excess Criterion",
            weight=Decimal('15.00'),
            max_score=10
        )
        with self.assertRaises(ValidationError):
            excess_criterion.save()

        # Incomplete rubric test: Create new event with sum != 100
        new_event = Event.objects.create(
            name="Incomplete Event",
            slug="incomplete-event",
            description="Testing incomplete rubric.",
            status=Event.Status.OPEN,
            start_date=self.now,
            registration_deadline=self.now,
            submission_deadline=self.now,
            end_date=self.now,
            created_by=self.organizer1
        )
        Rubric.objects.create(
            event=new_event,
            name="Partial",
            weight=Decimal('60.00'),
            max_score=10
        )
        with self.assertRaises(ValidationError):
            Rubric.validate_event_rubric(new_event)

    def test_score_exceeding_rubric_max_score_is_rejected(self):
        """A score exceeding criterion.max_score or less than 0 is rejected."""
        assignment = JudgeAssignment.objects.create(judge=self.judge1, submission=self.sub1)

        # Criterion max_score is 10
        invalid_score = Score(
            assignment=assignment,
            rubric_criterion=self.criterion_arch,
            raw_score=Decimal('15.00')
        )
        with self.assertRaises(ValidationError):
            invalid_score.save()

        negative_score = Score(
            assignment=assignment,
            rubric_criterion=self.criterion_arch,
            raw_score=Decimal('-2.00')
        )
        with self.assertRaises(ValidationError):
            negative_score.save()


class JudgeAssignmentAlgorithmTests(JudgingTestCaseBase):
    """Test suite for the round-robin judge assignment algorithm and conflict avoidance."""

    def test_assignment_algorithm_excludes_judge_who_is_team_member(self):
        """
        If a judge is also a participant and member of a team,
        the assignment algorithm MUST NEVER assign them to their own team's submission.
        """
        # Promote participant1 (member of Team 1) to also have judge role
        self.participant1.role = User.Role.JUDGE
        self.participant1.save()

        # Run assignment
        assign_judges_to_event(self.event, judges_per_submission=2, clear_existing=True)

        # Confirm participant1 was NOT assigned to sub1 (their own team)
        self.assertFalse(
            JudgeAssignment.objects.filter(judge=self.participant1, submission=self.sub1).exists(),
            "Judge was assigned to their own team's project! Conflict of interest violation."
        )

    def test_rerunning_assignment_does_not_duplicate_judge_assignments(self):
        """Re-running the judge assignment algorithm is idempotent and does not create duplicate rows."""
        # First assignment run
        res1 = assign_judges_to_event(self.event, judges_per_submission=2, clear_existing=False)
        count_after_first = JudgeAssignment.objects.filter(submission__event=self.event).count()
        self.assertGreater(count_after_first, 0)

        # Second assignment run (without clear_existing)
        res2 = assign_judges_to_event(self.event, judges_per_submission=2, clear_existing=False)
        count_after_second = JudgeAssignment.objects.filter(submission__event=self.event).count()

        # Must not duplicate!
        self.assertEqual(count_after_first, count_after_second)
        self.assertEqual(res2['new_assigned_count'], 0)


class NormalizationAndRankingTests(TestCase):
    """
    Test suite verifying the cross-judge z-score normalization algorithm
    against a small hand-calculated fixture.
    """

    def setUp(self):
        self.now = timezone.now()
        self.organizer = User.objects.create_user(
            username='org_norm',
            password='Password123!',
            role=User.Role.ORGANIZER
        )
        self.judge_harsh = User.objects.create_user(
            username='judge_harsh',
            password='Password123!',
            role=User.Role.JUDGE
        )
        self.judge_lenient = User.objects.create_user(
            username='judge_lenient',
            password='Password123!',
            role=User.Role.JUDGE
        )

        self.event = Event.objects.create(
            name="Normalization Benchmark",
            slug="normalization-benchmark",
            description="Testing harsh vs lenient judge normalization.",
            status=Event.Status.OPEN,
            start_date=self.now,
            registration_deadline=self.now,
            submission_deadline=self.now,
            end_date=self.now,
            created_by=self.organizer
        )
        # 1 criterion: weight = 100%, max_score = 10
        self.criterion = Rubric.objects.create(
            event=self.event,
            name="Overall Quality",
            weight=Decimal('100.00'),
            max_score=10
        )

        # 3 Submissions: A, B, C
        self.sub_a = self._create_sub("Project Alpha")
        self.sub_b = self._create_sub("Project Beta")
        self.sub_c = self._create_sub("Project Gamma")

    def _create_sub(self, title):
        p = User.objects.create_user(username=f"dev_{title.lower().replace(' ', '_')}", password='Password123!')
        team = Team.objects.create(event=self.event, name=f"Team {title}", created_by=p)
        TeamMembership.objects.create(team=team, user=p)
        return Submission.objects.create(
            team=team,
            event=self.event,
            title=title,
            description="Benchmark project",
            status=Submission.Status.SUBMITTED,
            submitted_at=self.now
        )

    def test_normalization_matches_hand_calculated_fixture(self):
        """
        Hand-calculated mathematical verification fixture:
        Judge Harsh scores:
          Sub A: 4.0
          Sub B: 6.0
          Sub C: 8.0
          Mean = 6.0, Sample Std = 2.0
          Z-scores: Sub A = -1.0, Sub B = 0.0, Sub C = +1.0

        Judge Lenient scores:
          Sub A: 7.0
          Sub B: 8.0
          Sub C: 9.0
          Mean = 8.0, Sample Std = 1.0
          Z-scores: Sub A = -1.0, Sub B = 0.0, Sub C = +1.0

        Population (all 6 scores: [4, 6, 8, 7, 8, 9]):
          Sum = 42, Mean = 7.0
          Sample variance = 16 / 5 = 3.2
          Sample Std = sqrt(3.2) = 1.788854

        Expected normalized scores:
          Sub A: 7.0 + (-1.0 * 1.788854) = 5.21
          Sub B: 7.0 + (0.0 * 1.788854)  = 7.00
          Sub C: 7.0 + (+1.0 * 1.788854) = 8.79
        """
        # Assignments for Judge Harsh
        a_h1 = JudgeAssignment.objects.create(judge=self.judge_harsh, submission=self.sub_a, status=JudgeAssignment.Status.COMPLETED)
        a_h2 = JudgeAssignment.objects.create(judge=self.judge_harsh, submission=self.sub_b, status=JudgeAssignment.Status.COMPLETED)
        a_h3 = JudgeAssignment.objects.create(judge=self.judge_harsh, submission=self.sub_c, status=JudgeAssignment.Status.COMPLETED)

        Score.objects.create(assignment=a_h1, rubric_criterion=self.criterion, raw_score=Decimal('4.00'))
        Score.objects.create(assignment=a_h2, rubric_criterion=self.criterion, raw_score=Decimal('6.00'))
        Score.objects.create(assignment=a_h3, rubric_criterion=self.criterion, raw_score=Decimal('8.00'))

        # Assignments for Judge Lenient
        a_l1 = JudgeAssignment.objects.create(judge=self.judge_lenient, submission=self.sub_a, status=JudgeAssignment.Status.COMPLETED)
        a_l2 = JudgeAssignment.objects.create(judge=self.judge_lenient, submission=self.sub_b, status=JudgeAssignment.Status.COMPLETED)
        a_l3 = JudgeAssignment.objects.create(judge=self.judge_lenient, submission=self.sub_c, status=JudgeAssignment.Status.COMPLETED)

        Score.objects.create(assignment=a_l1, rubric_criterion=self.criterion, raw_score=Decimal('7.00'))
        Score.objects.create(assignment=a_l2, rubric_criterion=self.criterion, raw_score=Decimal('8.00'))
        Score.objects.create(assignment=a_l3, rubric_criterion=self.criterion, raw_score=Decimal('9.00'))

        # Run normalization
        normalize_event_scores(self.event)

        # Verify normalized scores for Judge Harsh
        s_h1 = Score.objects.get(assignment=a_h1, rubric_criterion=self.criterion)
        s_h2 = Score.objects.get(assignment=a_h2, rubric_criterion=self.criterion)
        s_h3 = Score.objects.get(assignment=a_h3, rubric_criterion=self.criterion)

        self.assertEqual(s_h1.normalized_score, Decimal('5.21'))
        self.assertEqual(s_h2.normalized_score, Decimal('7.00'))
        self.assertEqual(s_h3.normalized_score, Decimal('8.79'))

        # Verify normalized scores for Judge Lenient
        s_l1 = Score.objects.get(assignment=a_l1, rubric_criterion=self.criterion)
        s_l2 = Score.objects.get(assignment=a_l2, rubric_criterion=self.criterion)
        s_l3 = Score.objects.get(assignment=a_l3, rubric_criterion=self.criterion)

        self.assertEqual(s_l1.normalized_score, Decimal('5.21'))
        self.assertEqual(s_l2.normalized_score, Decimal('7.00'))
        self.assertEqual(s_l3.normalized_score, Decimal('8.79'))

        # Verify final rankings
        rankings = get_event_rankings(self.event)
        self.assertEqual(rankings[0]['submission'], self.sub_c)
        self.assertEqual(rankings[0]['final_weighted_score'], Decimal('8.79'))
        self.assertEqual(rankings[0]['rank'], 1)

        self.assertEqual(rankings[1]['submission'], self.sub_b)
        self.assertEqual(rankings[1]['final_weighted_score'], Decimal('7.00'))
        self.assertEqual(rankings[1]['rank'], 2)

        self.assertEqual(rankings[2]['submission'], self.sub_a)
        self.assertEqual(rankings[2]['final_weighted_score'], Decimal('5.21'))
        self.assertEqual(rankings[2]['rank'], 3)


class CSVExportAndPermissionTests(JudgingTestCaseBase):
    """Test suite for CSV export security and scoping."""

    def setUp(self):
        super().setUp()
        self.assignment = JudgeAssignment.objects.create(
            judge=self.judge1,
            submission=self.sub1,
            status=JudgeAssignment.Status.COMPLETED
        )
        Score.objects.create(
            assignment=self.assignment,
            rubric_criterion=self.criterion_arch,
            raw_score=Decimal('8.50'),
            comment="Impressive architecture."
        )

    def test_csv_export_is_organizer_and_admin_only_scoped_to_own_event(self):
        """
        Raw and rankings CSV exports are strictly restricted to the event's creator organizer
        and platform administrators. Other users get 403 Forbidden.
        """
        raw_url = reverse('export_raw_scores_csv', kwargs={'event_slug': self.event.slug})
        rankings_url = reverse('export_rankings_csv', kwargs={'event_slug': self.event.slug})

        # 1. Participant -> 403 Forbidden
        self.client.login(username='dev_part1', password='Password123!')
        self.assertEqual(self.client.get(raw_url).status_code, 403)
        self.assertEqual(self.client.get(rankings_url).status_code, 403)
        self.client.logout()

        # 2. Judge -> 403 Forbidden
        self.client.login(username='eval_judge1', password='Password123!')
        self.assertEqual(self.client.get(raw_url).status_code, 403)
        self.assertEqual(self.client.get(rankings_url).status_code, 403)
        self.client.logout()

        # 3. Non-owner Organizer (Organizer 2) -> 403 Forbidden
        self.client.login(username='judge_org2', password='Password123!')
        self.assertEqual(self.client.get(raw_url).status_code, 403)
        self.assertEqual(self.client.get(rankings_url).status_code, 403)
        self.client.logout()

        # 4. Owner Organizer (Organizer 1) -> 200 OK with CSV attachment
        self.client.login(username='judge_org1', password='Password123!')
        resp_raw = self.client.get(raw_url)
        self.assertEqual(resp_raw.status_code, 200)
        self.assertEqual(resp_raw['Content-Type'], 'text/csv')
        self.assertIn(f'filename="{self.event.slug}_raw_scores.csv"', resp_raw['Content-Disposition'])
        self.assertContains(resp_raw, "CyberPulse Security Agent")
        self.assertContains(resp_raw, "eval_judge1")
        self.assertContains(resp_raw, "8.5")

        resp_rank = self.client.get(rankings_url)
        self.assertEqual(resp_rank.status_code, 200)
        self.assertEqual(resp_rank['Content-Type'], 'text/csv')
        self.assertContains(resp_rank, "CyberPulse Security Agent")
        self.client.logout()

        # 5. Platform Administrator -> 200 OK
        self.client.login(username='judge_admin', password='Password123!')
        self.assertEqual(self.client.get(raw_url).status_code, 200)
        self.assertEqual(self.client.get(rankings_url).status_code, 200)
        self.client.logout()


class Phase7bEventJudgeInvitationTests(JudgingTestCaseBase):
    """
    Test suite for Phase 7b: Event-Scoped Judge Invitations and Acceptance.
    """

    def test_organizer_can_create_invitation_for_own_event_not_for_other(self):
        """Organizer can create invitations for their own event, but non-owners get 403."""
        invite_url = reverse('event_judge_invitations', args=[self.event.slug])

        # 1. Owner Organizer creates invitation
        self.client.login(username='judge_org1', password='Password123!')
        resp = self.client.post(invite_url, {'email': 'invited_judge@test.local'})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(EventJudge.objects.filter(event=self.event, email='invited_judge@test.local').exists())
        self.client.logout()

        # 2. Non-owner Organizer gets 403 Forbidden
        self.client.login(username='judge_org2', password='Password123!')
        resp_forbidden = self.client.post(invite_url, {'email': 'unauthorized@test.local'})
        self.assertEqual(resp_forbidden.status_code, 403)
        self.assertFalse(EventJudge.objects.filter(email='unauthorized@test.local').exists())
        self.client.logout()

    def test_participant_or_organizer_cannot_accept_judge_invitation(self):
        """Participants and organizers get 403 when attempting to access judge acceptance link."""
        invite = EventJudge.objects.create(
            event=self.event,
            invited_by=self.organizer1,
            token='test-participant-reject-token'
        )
        respond_url = reverse('judge_invitation_respond', args=[invite.token])

        # Participant gets 403
        self.client.login(username='dev_part1', password='Password123!')
        self.assertEqual(self.client.get(respond_url).status_code, 403)
        self.assertEqual(self.client.post(respond_url, {'action': 'accept'}).status_code, 403)
        self.client.logout()

        # Organizer gets 403
        self.client.login(username='judge_org1', password='Password123!')
        self.assertEqual(self.client.get(respond_url).status_code, 403)
        self.client.logout()

    def test_judge_can_accept_and_decline_via_token_url(self):
        """A judge can accept or decline via the token URL, updating status and responded_at."""
        # 1. Accept test
        judge3 = User.objects.create_user(
            username='eval_judge3',
            email='judge3@test.local',
            password='Password123!',
            role=User.Role.JUDGE
        )
        invite_accept = EventJudge.objects.create(
            event=self.event,
            invited_by=self.organizer1,
            token='token-to-accept'
        )
        self.client.login(username='eval_judge3', password='Password123!')
        resp_acc = self.client.post(
            reverse('judge_invitation_respond', args=[invite_accept.token]),
            {'action': 'accept'}
        )
        self.assertEqual(resp_acc.status_code, 302)
        invite_accept.refresh_from_db()
        self.assertEqual(invite_accept.status, EventJudge.Status.ACCEPTED)
        self.assertEqual(invite_accept.user, judge3)
        self.assertIsNotNone(invite_accept.responded_at)
        self.client.logout()

        # 2. Decline test
        judge4 = User.objects.create_user(
            username='eval_judge4',
            email='judge4@test.local',
            password='Password123!',
            role=User.Role.JUDGE
        )
        invite_decline = EventJudge.objects.create(
            event=self.event,
            invited_by=self.organizer1,
            token='token-to-decline'
        )
        self.client.login(username='eval_judge4', password='Password123!')
        resp_dec = self.client.post(
            reverse('judge_invitation_respond', args=[invite_decline.token]),
            {'action': 'decline'}
        )
        self.assertEqual(resp_dec.status_code, 302)
        invite_decline.refresh_from_db()
        self.assertEqual(invite_decline.status, EventJudge.Status.DECLINED)
        self.assertEqual(invite_decline.user, judge4)
        self.assertIsNotNone(invite_decline.responded_at)
        self.client.logout()

    def test_revoked_or_invalid_token_is_rejected_cleanly(self):
        """Revoked, invalid, and closed event tokens are rejected cleanly without 500 errors."""
        self.client.login(username='eval_judge1', password='Password123!')

        # 1. Invalid token -> 404
        resp_404 = self.client.get(reverse('judge_invitation_respond', args=['completely-invalid-token']))
        self.assertEqual(resp_404.status_code, 404)
        self.assertContains(resp_404, "invalid", status_code=404)

        # 2. Revoked token -> 400
        revoked_invite = EventJudge.objects.create(
            event=self.event,
            invited_by=self.organizer1,
            token='revoked-test-token',
            status=EventJudge.Status.REVOKED
        )
        resp_revoked = self.client.get(reverse('judge_invitation_respond', args=[revoked_invite.token]))
        self.assertEqual(resp_revoked.status_code, 400)
        self.assertContains(resp_revoked, "revoked", status_code=400)

        # 3. Closed event -> 400
        closed_event = Event.objects.create(
            name="Concluded Hackathon",
            slug="concluded-hackathon",
            description="Concluded event.",
            status=Event.Status.CLOSED,
            start_date=self.now,
            registration_deadline=self.now,
            submission_deadline=self.now,
            end_date=self.now,
            created_by=self.organizer1
        )
        closed_invite = EventJudge.objects.create(
            event=closed_event,
            invited_by=self.organizer1,
            token='closed-event-token',
            status=EventJudge.Status.PENDING
        )
        resp_closed = self.client.get(reverse('judge_invitation_respond', args=[closed_invite.token]))
        self.assertEqual(resp_closed.status_code, 400)
        self.assertContains(resp_closed, "closed", status_code=400)
        self.client.logout()

    def test_assign_judges_only_uses_judges_with_accepted_invitations(self):
        """A role='judge' user with no accepted invitation is never assigned."""
        uninvited_judge = User.objects.create_user(
            username='uninvited_judge_user',
            email='uninvited@test.local',
            password='Password123!',
            role=User.Role.JUDGE
        )

        res = assign_judges_to_event(self.event, judges_per_submission=2, clear_existing=True)
        self.assertTrue(res['success'])

        assigned_judge_ids = set(
            JudgeAssignment.objects.filter(submission__event=self.event).values_list('judge_id', flat=True)
        )
        self.assertIn(self.judge1.id, assigned_judge_ids)
        self.assertIn(self.judge2.id, assigned_judge_ids)
        self.assertNotIn(uninvited_judge.id, assigned_judge_ids)

    def test_judge_with_pending_or_declined_invitation_is_never_assigned(self):
        """Judges with pending or declined invitations are excluded from assignment."""
        pending_judge = User.objects.create_user(
            username='pending_judge_user',
            email='pending_j@test.local',
            password='Password123!',
            role=User.Role.JUDGE
        )
        EventJudge.objects.create(
            event=self.event,
            invited_by=self.organizer1,
            user=pending_judge,
            status=EventJudge.Status.PENDING
        )

        declined_judge = User.objects.create_user(
            username='declined_judge_user',
            email='declined_j@test.local',
            password='Password123!',
            role=User.Role.JUDGE
        )
        EventJudge.objects.create(
            event=self.event,
            invited_by=self.organizer1,
            user=declined_judge,
            status=EventJudge.Status.DECLINED
        )

        assign_judges_to_event(self.event, judges_per_submission=2, clear_existing=True)

        assigned_judge_ids = set(
            JudgeAssignment.objects.filter(submission__event=self.event).values_list('judge_id', flat=True)
        )
        self.assertNotIn(pending_judge.id, assigned_judge_ids)
        self.assertNotIn(declined_judge.id, assigned_judge_ids)

    def test_revoking_accepted_judge_removes_unscored_and_preserves_scored(self):
        """Revoking an accepted invitation deletes unscored assignments but preserves completed scores flagged for review."""
        # Clean any existing assignments
        JudgeAssignment.objects.filter(submission__event=self.event).delete()

        # Assignment 1: Completed with score
        a1 = JudgeAssignment.objects.create(
            submission=self.sub1,
            judge=self.judge1,
            status=JudgeAssignment.Status.COMPLETED
        )
        Score.objects.create(
            assignment=a1,
            rubric_criterion=self.criterion_arch,
            raw_score=Decimal('9.00')
        )

        # Assignment 2: Not started, no scores
        a2 = JudgeAssignment.objects.create(
            submission=self.sub2,
            judge=self.judge1,
            status=JudgeAssignment.Status.NOT_STARTED
        )

        # Organizer revokes invitation
        self.client.login(username='judge_org1', password='Password123!')
        revoke_url = reverse('revoke_judge_invitation', args=[self.invitation1.id])
        resp = self.client.post(revoke_url)
        self.assertEqual(resp.status_code, 302)

        self.invitation1.refresh_from_db()
        self.assertEqual(self.invitation1.status, EventJudge.Status.REVOKED)

        # Unscored assignment a2 must be deleted
        self.assertFalse(JudgeAssignment.objects.filter(id=a2.id).exists())

        # Scored assignment a1 must be kept and flagged for review
        self.assertTrue(JudgeAssignment.objects.filter(id=a1.id).exists())
        a1.refresh_from_db()
        self.assertTrue(a1.is_flagged_for_review)
        self.assertIn("preserved for audit", a1.review_notes)

    def test_rerunning_seed_demo_data_does_not_duplicate_invitations(self):
        """Running seed_demo_data multiple times is idempotent and does not create duplicate invitations."""
        from django.core.management import call_command
        call_command('seed_demo_data')
        call_command('seed_demo_data')

        from apps.events.models import Event
        event1 = Event.objects.get(slug='ai-frontier-hackathon-2026')
        judge1 = User.objects.get(username='judge1')

        invites_count = EventJudge.objects.filter(event=event1, user=judge1).count()
        self.assertEqual(invites_count, 1)

