# Agent Tool Contract

Status: production tool names and interfaces are **PROPOSED**. The local
experiment includes a CP-SAT adapter and deterministic validator, but no
server-authoritative tools or API integration.

## 1. Capability classes

### Qwen-visible interpretation tools

Qwen receives no direct database, optimizer, approval, or persistence tools.
It may be used through a constrained parser call that returns a
`ConstraintProposal`:

```text
propose_constraint_delta(
  userRequest,
  meetingSummary,
  allowedDates,
  durationMinutes,
  timeZone = "Asia/Seoul",
  participantDisplayNames
) -> {
  proposedChanges: ConstraintChange[],
  ambiguities: string[],
  userSummary: string
}
```

The call is read-only. Do not send secrets, unrelated personal data, raw
checkpoints, or all participant records where a bounded summary is sufficient.
Participant names are context for clarification only; name-to-ID resolution
must be an explicit user/server operation and must not be guessed by the model.
The local adapter may additionally expose only these snapshot-scoped,
read-only interpretation tools:

| Tool | Purpose | Boundary |
|---|---|---|
| `get_availability(participant_id)` | Read an accepted participant's submitted slots by authoritative ID. | Same snapshot only; no mutation |
| `get_meeting_constraints()` | Read the current revision, configured dates, duration, and exact conditions. | Same snapshot only; no mutation |
| `find_common_slots(date)` | Read common availability windows. | Does not create candidates or imply feasibility/approval |

These are not optimizer or persistence tools. The model cannot invoke the
internal deterministic tools listed below, and unknown tool names or invalid
arguments fail closed.

For the local `RescheduleProposalDraft` adapter, distinguish a meeting duration
from clock-time constraints:

| User intent | Change type | Required interpretation |
|---|---|---|
| "소요시간을 45분으로 줄여줘" | `SET_DURATION` | Set `duration_minutes` to 45; do not infer a date or clock time. |
| "모임 시간을 30분 늘려줘" | `SET_DURATION` | Read current duration; if it is 60, set `duration_minutes` to 90. |
| "11월 8일 오후 8시부터 9시까지 조건을 삭제해줘" | `REMOVE_TIME_WINDOW` | Remove only an exact existing date/start/end tuple copied from meeting constraints. |

`REMOVE_TIME_WINDOW` is not a synonym for shortening a meeting's duration.
The deterministic validator rejects any removal that does not match an
existing exact condition. If schema or domain validation fails, the local
adapter may request one corrected draft, supplying only the error code and
permitted change types. The retry cannot relax validation; a second failure
terminates with an explicit error and leaves the snapshot unchanged.

The model cannot call the internal deterministic tools below. Implementations
may expose the three read-only context tools above, then must validate every
returned proposal field as untrusted input.

### Internal deterministic policy tools

| Tool | Purpose | Authorization / side effects |
|---|---|---|
| `load_meeting_snapshot(meetingId, actorId)` | Load current authoritative meeting, member, response, availability, and versions. | Authenticated member access; read-only |
| `validate_readiness(snapshot)` | Classify missing RSVP, missing availability, invalid slots, and ready state. | Deterministic; read-only |
| `set_or_extend_rsvp_deadline(meetingId, deadlineAt, expectedInputRevision, hostId)` | Set or extend the RSVP deadline. | Host-only; compare-and-swap; audit; invalidates candidates if the meeting input changes |
| `exclude_pending_invitee(meetingId, participantId, reason, expectedInputRevision, hostId)` | Explicitly exclude a sent invitee who remains pending after the deadline. | Host-only; deadline must have passed; preserve pending RSVP; audit; increment input revision and invalidate candidates |
| `set_minimum_attendee_count(meetingId, minimumAttendeeCount, expectedInputRevision, hostId)` | Set this meeting's minimum partial attendance. | Host-only; `2 <= value <= eligible roster size`; compare-and-swap; audit; increment input revision and invalidate candidates |
| `resolve_confirmed_participant_reference(reference, actorConfirmation)` | Resolve a selected participant only after explicit user confirmation. | Same-meeting membership; audit resolution |
| `validate_constraint_delta(delta, snapshot)` | Strictly validate dates, minute ranges, duration, timezone, hard/soft distinctions, and revision. | Deterministic; no mutation |
| `apply_confirmed_constraint_delta(delta, expectedInputRevision, actorId)` | Persist only a user-confirmed valid delta. | Authenticated authority, revision compare-and-swap, audit, idempotent |
| `build_solver_input(snapshot)` | Normalize validated inputs for the solver. | Deterministic; read-only |
| `solve_all_attendees(input)` | Search for every active accepted participant. | OR-Tools only; bounded runtime; no DB mutation |
| `solve_partial_attendees(input, minimumAttendeeCount)` | Search partial alternatives after proven all-attendee infeasibility. | OR-Tools only; configured minimum and all absolute constraints remain fixed |
| `validate_candidate(input, rawCandidate, solverStatus)` | Verify exact feasibility, all absolute constraints, interval/duration, roster partition, and revision. | Deterministic; fail closed |
| `persist_verified_candidates(runId, revision, candidates)` | Persist immutable verified candidate records and opaque IDs. | Server transaction; revision recheck; idempotent |
| `record_candidate_selection(runId, candidateId, revision, actorId)` | Record candidate selection. | Authenticated member; does not imply consent |
| `record_participant_consent(runId, candidateId, round, decision, actorId)` | Record one actual candidate attendee's own consent. | Actor must be in the stored candidate's `attendeeIds`; non-attendees cannot consent for others; unique/idempotent per decision key |
| `record_host_decision(runId, candidateId, round, decision, hostId)` | Record host approval/rejection and resume checkpoint. | Host-only; compare-and-swap; idempotent |
| `request_run_cancellation(runId, actorId)` | Request cooperative stop. | Authorized member/host policy; idempotent |

No tool may convert a missing submission to an empty/unavailable interval or
automatically exclude a pending invitee when the RSVP deadline passes. Every
mutating tool accepts an expected input revision and idempotency key.
Participant exclusion preserves `responseStatus=PENDING`, changes only
eligibility, and invalidates prior candidates. Mutations are transactional and
produce an audit record. Tools return typed domain errors, not success-shaped
fallback values.

## 2. Constraint proposal schema

```json
{
  "baseInputRevision": 12,
  "proposedChanges": [
    {
      "kind": "TIME_WINDOW",
      "date": "2026-11-08",
      "startMinute": 780,
      "endMinute": 1020,
      "strength": "PREFERENCE"
    }
  ],
  "ambiguities": [],
  "userSummary": "11월 8일 오후 시간대를 선호 조건으로 추가합니다."
}
```

**PROPOSED schema rules:**

- `strength` is `PREFERENCE` or `ABSOLUTE`; user-facing confirmation must
  clearly show which one is proposed. Unclear language remains an ambiguity.
- Qwen cannot propose participant additions/removals, per-person
  required-attendee flags (not supported in MVP), changes to the host-set
  minimum attendee count, approval, or finalization.
- A proposed absolute constraint that conflicts with an existing absolute
  constraint is rejected or clarified, never auto-relaxed.
- The server checks minute bounds, allowed meeting dates, duration, timezone,
  participant references, and `baseInputRevision`.
- Confirmation is a separate authenticated action. A stale base revision
  requires re-parse/review rather than rebasing silently.

## 3. Optimizer result handling

| OR-Tools status | Domain treatment |
|---|---|
| `OPTIMAL` | A solution exists and optimality is proved for the encoded objective. Validate candidate independently before publication. |
| `FEASIBLE` | A solution exists but optimality is not proved before the limit. Validate independently; present as feasible, not optimal. |
| `INFEASIBLE` | A solution is proved not to exist for this exact input/search space. Only all-attendee `INFEASIBLE` may route to partial search. Partial `INFEASIBLE` may produce `NO_FEASIBLE_SCHEDULE`. |
| `UNKNOWN` | No conclusion. Do not route to partial search or show “no schedule.” Return retryable `ERROR` or a separately approved unresolved state. |
| Timeout / cancellation | No conclusion. Do not route to partial search. Query/cancel the same run and expose retry guidance. |
| `MODEL_INVALID` / exception | Tool error; do not publish output. Preserve internal diagnostics server-side and return a sanitized stable error. |

The local adapter performs all-attendee search first. Its partial CP-SAT
objective maximizes the number of attendees subject to the configured minimum.
Only `OPTIMAL` proves the maximum; a `FEASIBLE` incumbent is not described as
the maximum. With no preference model, equal maximum-attendance candidates are
ordered by date, start minute, end minute, then participant IDs.

The current `server-api/optimizer.py` optimizes role assignments in 30-minute
steps; it is not the shared-time candidate solver specified here. Reusing its
status names does not make its plan compatible with this candidate contract.

## 4. Candidate validation checklist

Before a candidate can be persisted or returned:

1. The source revision and canonical input snapshot hash match the run.
2. Solver status is `OPTIMAL` or `FEASIBLE`.
3. Date is an allowed meeting date; timezone is exactly `Asia/Seoul`.
4. Start/end are integers, `0 <= start < end <= 1440`, and no rounding occurred.
5. Duration equals the meeting's required duration, unless an explicitly
   confirmed constraint changed duration.
6. Every attendee ID belongs to the authoritative eligible roster and submitted
   availability covering the complete half-open interval.
7. No absolute constraint is violated; MVP has no per-person required-attendee
   designation.
8. For `ALL_AVAILABLE`, every eligible participant is present and
   `unavailableIds` is empty.
9. For `PARTIAL_ALTERNATIVE`, all-attendee search evidence is `INFEASIBLE`,
   attendee count meets the host-configured `minimumAttendeeCount` (which must
   be at least two), and every unavailable ID is an eligible submitted
   participant absent from the attendee set.
10. Attendee and unavailable IDs are unique, disjoint, and their union equals
    the eligible roster; pending, excluded, or unresolved people are not
    represented as unavailable.
11. At most three candidates are persisted/displayed, with deterministic
    ordering and no duplicate interval/attendee result.
12. `candidateId` is generated by the server and bound immutably to meeting,
    run, payload, and input revision.

Any failed check rejects the candidate set, records a sanitized validation
failure, and prevents selection/consent/approval.

Before entering host approval, the consent service must verify that every ID
in the selected candidate's `attendeeIds` has consented to that exact
candidate, input revision, and consent round. No participant outside
`attendeeIds` is required to consent to a partial candidate.
