# LangGraph StateGraph Design

Status: production node names and routing remain **PROPOSED**. A local
LangGraph execution skeleton exists under `potato_agent/`; it is not connected
to the production API, persistence layer, Qwen, or OR-Tools service.

## 1. Trust boundaries

- The authenticated API loads and authorizes the meeting snapshot.
- LangGraph coordinates deterministic domain services; it is not the source of
  truth for participants, availability, revision, candidate validity,
  approval, or finalization.
- Qwen may interpret user language into a proposed structured delta and
  provide a bounded explanation. It cannot call the solver, mutate constraints,
  set approval/consent/finalization, or declare a candidate verified.
- OR-Tools searches a normalized, versioned input. A separate deterministic
  validator checks its output before persistence or publication.
- Client-provided `verified`, participant availability, `sourceRevision`, and
  attendee membership are never trusted as authoritative.

## 2. State schema

```text
AgentState {
  meetingId
  agentSessionId
  runId
  actorParticipantId
  inputRevision
  inputSnapshotHash
  consentRound
  rsvpDeadlineAt?
  minimumAttendeeCount
  meetingConstraint
  participants[]
  availabilityByParticipantId
  missingInput[]
  userRequest?
  proposedConstraintDelta?
  proposalConfirmed: boolean
  searchPhase: ALL_ATTENDEES | PARTIAL_ATTENDEES | NONE
  allAttendeeSolverStatus: OPTIMAL | FEASIBLE | INFEASIBLE | UNKNOWN | TIMEOUT | ERROR | NOT_RUN
  partialSolverStatus: same
  searchEvidence
  rawSolverCandidates[]
  verifiedCandidates[]
  selectedCandidateId?
  consentByAttendeeId
  approvalDecision?
  publicStatus
  retryCount
  cancelRequested: boolean
  error?
  auditEventIds[]
}
```

Checkpoint state contains only what is needed to continue safely. The
checkpoint is keyed by a server-private thread ID bound to one meeting and
agent session. Each run has an independent `runId`; checkpoint resume must
validate the persisted revision and state transition before proceeding.

## 3. Nodes

| Node | Responsibility | Must not do |
|---|---|---|
| `load_authoritative_snapshot` | Load current meeting, authenticated participants, invitation/response statuses, availability, hard constraints and revisions. | Trust app-supplied member data |
| `validate_input_and_authorize` | Check actor/host permissions, membership, MVP minimum of two eligible participants, host-configured minimum attendance, supported timezone/date/minute bounds, versions, and duplicate IDs. | Fill missing fields or invent per-person required-attendee flags |
| `classify_readiness` | Separate pending RSVP, accepted-but-unsubmitted availability, declined, invalid, and ready participants. | Treat pending or not submitted as unavailable |
| `wait_for_user_input` | Persist `WAITING_FOR_INPUT` and reasons if data are missing. | Start OR-Tools with fabricated slots |
| `set_or_extend_rsvp_deadline` | Let the host set or extend the meeting RSVP deadline, with revision checks and audit. | Auto-exclude invitees when the deadline passes |
| `exclude_pending_invitee` | After the deadline, let the host explicitly exclude a sent invitee still pending; preserve the pending RSVP, record reason/actor/time, increment input revision, and invalidate results. | Treat expiry as exclusion or rewrite pending as declined |
| `parse_reschedule_with_qwen` | Produce a schema-constrained proposal for user text: candidate dates/times, duration, preference vs hard constraint, ambiguity/questions. | Choose candidate times, mark a proposal confirmed, mutate meeting state |
| `validate_constraint_proposal` | Resolve participant references to authoritative IDs, verify allowed dates/ranges and semantic consistency; surface ambiguity. | Guess a name-to-ID mapping or weaken hard constraints |
| `await_proposal_confirmation` | Persist proposal and wait at a review checkpoint. | Apply changes before authenticated user confirmation |
| `apply_confirmed_delta` | Recheck actor and revision; apply only confirmed fields; increment input revision; supersede prior candidates/approvals. | Reuse a result from the prior revision |
| `build_normalized_search_input` | Build deterministic solver input from eligible accepted participants with submitted slots and the host-configured minimum attendance. | Include unresolved participants as unavailable or synthesize required-attendee flags |
| `solve_all_attendees` | Search for all eligible participants and satisfy every absolute constraint. | Optimize away absolute constraints |
| `validate_all_attendee_result` | Independently validate date, minute interval, duration, slot coverage, attendee set, hard constraints and solver status. | Trust an LLM explanation or solver output without validation |
| `solve_partial_attendees` | Run only after all-attendee `INFEASIBLE`; enforce all absolute constraints, host-configured minimum count, and attendee-count-first objective. | Run after `UNKNOWN`, timeout, tool error, or merely no returned candidates |
| `validate_partial_result` | Verify each attendee has submitted availability covering the slot; each unavailable ID is eligible and submitted; attendee count meets the configured minimum. | Mark a pending, excluded, or non-submitting participant unavailable |
| `persist_candidates_and_status` | Persist immutable candidate payloads bound to run and input revision; issue opaque IDs; return at most three. | Publish unverified candidates |
| `await_candidate_selection` | Save selected candidate only after server-side revalidation. | Treat selection as consent |
| `collect_consents` | Record authenticated decisions from every participant in the selected candidate's `attendeeIds`, bound to candidate, input revision and consent round. | Require non-attendees of a partial candidate to consent or carry consent across a changed candidate/revision |
| `await_host_approval` | Verify every ID in the selected candidate's `attendeeIds` has consented to that candidate/revision/round; then interrupt durably for host decision. | Require consent from non-attendees of a partial candidate or finalize the meeting |
| `resume_after_host_decision` | Resume checkpoint using server-recorded approval/rejection after fresh authorization/version checks. | Accept an arbitrary client `thread_id` or checkpoint |
| `mark_stale` | Mark run/candidates/approval stale when authoritative input revision changes. | Permit action against stale candidate |
| `handle_cancel_or_error` | Persist terminal/cancel state or classified retryable error and audit event. | Convert timeout/unknown into infeasibility |

## 4. Edges and conditional routes

```text
START
  -> load_authoritative_snapshot
  -> validate_input_and_authorize
  -> classify_readiness
       missing/pending/invalid -> wait_for_user_input -> END
            deadline passed + host action -> exclude_pending_invitee
            extend deadline -> set_or_extend_rsvp_deadline
            exclusion/extension -> reload snapshot and reclassify
       ready                 -> build_normalized_search_input

build_normalized_search_input
  -> userRequest absent -> solve_all_attendees
  -> userRequest present -> parse_reschedule_with_qwen
       -> validate_constraint_proposal
       -> ambiguity/invalid -> wait_for_user_input -> END
       -> valid proposal -> await_proposal_confirmation -> interrupt
            reject -> END without mutation
            confirm -> apply_confirmed_delta -> build_normalized_search_input

solve_all_attendees
  -> OPTIMAL or FEASIBLE -> validate_all_attendee_result
       -> valid -> persist ALL_AVAILABLE -> await_candidate_selection
       -> invalid -> handle_cancel_or_error
  -> INFEASIBLE -> solve_partial_attendees
  -> UNKNOWN/TIMEOUT/ERROR -> handle_cancel_or_error (never partial fallback)

solve_partial_attendees
  -> OPTIMAL or FEASIBLE -> validate_partial_result
       -> valid -> persist PARTIAL_ALTERNATIVE -> await_candidate_selection
       -> invalid -> handle_cancel_or_error
  -> INFEASIBLE -> persist NO_FEASIBLE_SCHEDULE -> END
  -> UNKNOWN/TIMEOUT/ERROR -> handle_cancel_or_error

await_candidate_selection
  -> select -> revalidate candidate/revision -> collect_consents
  -> reschedule -> parse/confirm proposal path
  -> cancel -> handle_cancel_or_error

collect_consents
  -> every candidate attendeeId consented -> await_host_approval -> interrupt
  -> attendee review/reject -> await user action or new run
  -> revision changed -> mark_stale

await_host_approval
  -> approved -> resume_after_host_decision -> record APPROVED -> END
  -> rejected -> resume_after_host_decision -> record REJECTED -> END
  -> revision changed -> mark_stale
  -> cancel -> handle_cancel_or_error
```

Every node that can call a tool or persist a mutation checks cancellation and
revision before proceeding. A revision mismatch routes to `mark_stale` without
publishing or approving a result.

## 5. Checkpoint and resume rules

**PROPOSED:** persist LangGraph checkpoints in a durable store suitable for the
deployment, not process memory. The public API accepts `agentSessionId` and
`runId`; it never accepts arbitrary raw `thread_id`/checkpoint identifiers.

- A reschedule continues the session but creates a new run and new input
  revision after confirmation.
- Approval/rejection resumes the exact paused run only after checking actor,
  host privilege, candidate, consent round, and source revision.
- Duplicate approval with the same idempotency key returns the recorded
  decision; conflicting decisions return `409`.
- Process restart restores the checkpoint, then revalidates authoritative
  revision before any side effect.
- Checkpoint expiry or corruption yields a typed recoverable error and a new
  run; never fabricate the previous state.

## 6. Qwen and deterministic policy

Qwen output is untrusted structured data. It may propose a `ConstraintDelta`,
ask a clarification question, and summarize the server-provided result. Its
output is validated against a strict schema and the original request, then
shown for user confirmation before mutation. It cannot:

- call OR-Tools or mark its result feasible/infeasible;
- create or select a `Candidate`;
- mark `verified`;
- decide all-attendee infeasibility or partial eligibility;
- add/remove participants, map names to IDs, or create unsupported per-person
  mandatory-attendance flags;
- weaken absolute constraints, minimum attendance, or required attendance;
- grant consent, approve, or finalize.

OR-Tools and deterministic validators enforce all search policy. Persist raw
solver status and evidence to distinguish proof from timeout/unknown.

## 7. Cancellation, timeout, retry

- Cancellation is cooperative and idempotent. Persist `cancelRequested`, stop
  future side effects, and expose `CANCELLED` only when execution has stopped.
- A client timeout is an unknown outcome. Query the same `runId` before
  requesting a retry.
- Retryable infrastructure failure may resume/re-run an idempotent node with
  the same input snapshot. A changed input requires a new run and revision.
- Tool calls with external side effects require their own idempotency key.
- Maximum attempts, execution deadline, checkpoint retention, and rate limits
  are **PROPOSED** deployment settings to be fixed before production.
