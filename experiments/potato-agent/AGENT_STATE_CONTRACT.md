# Agent State and API Contract

Status: design proposal for the local Agent Core experiment. **PROPOSED**
marks details that require API/product approval.

## 1. Public state machine

The API exposes domain states, not raw LangGraph node names or checkpoint
internals.

```text
WAITING_FOR_INPUT
  -> ANALYZING
  -> RUNNING_TOOLS
  -> ALL_AVAILABLE
  -> PARTIAL_ALTERNATIVE
  -> NO_FEASIBLE_SCHEDULE
  -> AWAITING_APPROVAL
  -> STALE | ERROR | CANCELLED
```

This is not a single linear sequence: successful candidates can transition
from either candidate state to `AWAITING_APPROVAL`; input changes can make any
non-final state `STALE`; retryable failures may return to `ANALYZING`.

| API state | Meaning and UI mapping | Allowed next action |
|---|---|---|
| `WAITING_FOR_INPUT` | RSVP response, accepted participant availability, or confirmed user input is missing. Identify RSVP-pending and availability-not-submitted separately. | Wait, collect input, or use explicit host exclusion after RSVP deadline; start only when server says ready |
| `ANALYZING` | Agent is validating request/constraints or preparing a deterministic solve. | Poll; request cancellation |
| `RUNNING_TOOLS` | Deterministic optimizer or validator is executing. | Poll; request cancellation |
| `ALL_AVAILABLE` | Verified candidates include every eligible participant. Maps to UI `ALL_AVAILABLE`. | Select a candidate; reschedule |
| `PARTIAL_ALTERNATIVE` | All-attendee infeasibility was proved and verified partial alternatives meet the host-configured minimum. Maps to UI `PARTIAL_ALTERNATIVE`. | Select a candidate; obtain consent from every listed attendee |
| `NO_FEASIBLE_SCHEDULE` | All-attendee search was proven infeasible and no alternative meets the host-configured minimum. Maps to UI equivalent. | Edit inputs or minimum; new run |
| `AWAITING_APPROVAL` | A verified candidate is held at a durable approval checkpoint. All actual attendees in that candidate have consented. Maps to UI equivalent. | Host decision through explicit API |
| `STALE` | `inputRevision` changed after the result was computed. Maps to UI equivalent; hide candidate actions. | Fetch current meeting and start a fresh run |
| `ERROR` | Execution failed. Includes stable code and retryability. Maps to UI equivalent. | Retry only when marked retryable |
| `CANCELLED` | Cancellation completed and the run will not produce further actions. **New UI state required.** | Start a new run |

`FEASIBLE` means a valid plan was found but optimality was not proved. It may
be displayed only after full deterministic validation and must not be labeled
“optimal.” `UNKNOWN`, deadline exhaustion, or timeout never map to
`NO_FEASIBLE_SCHEDULE`.

The current mobile UI has nine states and no `CANCELLED` state. It also needs
to show pending RSVP separately from accepted-but-unsubmitted availability.
Do not overload one generic “waiting” label with those different causes.

## 2. API envelope

**PROPOSED route family:** `/v2/coordination/meetings/{meetingId}/agent-runs`.
Keep `agent-runs` as the default path for new Agent Core operations. This is
separate from the existing `/v1/meetings` role-assignment API; do not reuse
that API's calculation or consent endpoints.

All routes require authenticated membership. The server verifies that the
actor belongs to the meeting, applies host-only authorization where specified,
and returns no checkpoint IDs, prompt content, or hidden reasoning.

### Start a run

```http
POST /v2/coordination/meetings/{meetingId}/agent-runs
Authorization: Bearer <member-token>
Idempotency-Key: <opaque unique key>
Content-Type: application/json
```

```json
{
  "expectedInputRevision": 12,
  "userRequest": null
}
```

The server loads authoritative meeting, participants, responses, and
availability. The client must not submit trusted participant identities or
invent other participants' availability in this request.

Response: `202 Accepted` with a snapshot containing `agentSessionId`, `runId`,
`inputRevision`, state, readiness/missing-input details, timestamps, and
status URL. A missing-input result is not a solver result. The MVP rejects
starting a run unless at least two eligible participants exist. The meeting
configuration supplies the host-set `minimumAttendeeCount`; there is no
half-of-N default.

### RSVP deadline and explicit exclusion

The host sets or extends the meeting's optional `rsvpDeadlineAt` through the
Agent Core meeting configuration contract. **PROPOSED run-scoped operation:**

```http
PUT .../{runId}/rsvp-deadline
{"expectedInputRevision": 12, "deadlineAt": "2026-11-02T09:00:00Z"}
```

After the deadline, expiry alone does not exclude anyone. The host may instead
wait, extend the deadline, or make an explicit audited exclusion:

```http
POST .../{runId}/participant-exclusions
Idempotency-Key: <unique exclusion key>
{"expectedInputRevision": 12, "participantId": "opaque-member-id", "reason": "RSVP deadline passed"}
```

The server accepts exclusion only for a sent invitee whose response is still
`PENDING`, only from the host, and only after the current RSVP deadline.
Exclusion changes eligibility to `EXCLUDED_BY_HOST` without rewriting the
pending response as declined. It increments `inputRevision` and invalidates
all existing candidates, selections, consents, and pending approvals. A host
change to `minimumAttendeeCount` is likewise explicit, host-authorized, and
revisioned; the value must be at least two.

```http
PUT .../{runId}/minimum-attendee-count
{"expectedInputRevision": 12, "minimumAttendeeCount": 3}
```

The configured minimum must be between two and the current eligible roster
size. Changing it increments `inputRevision` and invalidates prior candidates
and decisions. It is not derived from roster size and has no half-of-N default.

### Read status

```http
GET /v2/coordination/meetings/{meetingId}/agent-runs/{runId}
```

Returns the current snapshot and candidates only when the server has marked
them verified for the current input revision. **PROPOSED transport:** begin
with bounded polling and `Retry-After`; add SSE only if measured latency/UX
requires it.

### Propose and confirm a reschedule

```http
POST .../{runId}/reschedule-proposals
Idempotency-Key: <unique request key>
```

```json
{"expectedInputRevision": 12, "requestText": "일요일 오후로 다시 찾아줘"}
```

Response is a structured `ConstraintProposal` with proposed changes,
ambiguities, and the unchanged base revision. It does not mutate meeting
constraints or launch a solve.

```http
POST .../{runId}/reschedule-proposals/{proposalId}/confirm
Idempotency-Key: <unique confirmation key>
```

```json
{"expectedInputRevision": 12, "confirmed": true}
```

The server revalidates the proposal and authorization, applies only the
confirmed changes, increments `inputRevision`, supersedes old candidates and
approvals, then creates a new run in the same `agentSessionId`. A declined
proposal makes no change. **PROPOSED:** expose both endpoints rather than a
single implicitly mutating reschedule endpoint; this is required to meet the
user-confirmation policy.

### Select candidate

```http
PUT .../{runId}/selection
```

```json
{
  "expectedInputRevision": 12,
  "candidateId": "opaque-server-id"
}
```

The server re-reads the stored candidate and verifies run, meeting, revision,
eligibility, and validation status. This records selection only; it is not
consent, host approval, or finalization.

### Participant consent and host approval

```http
PUT .../{runId}/consents
```

```json
{
  "expectedInputRevision": 12,
  "consentRound": 3,
  "candidateId": "opaque-server-id",
  "decision": "AGREE"
}
```

The authenticated participant may decide only for themselves. Decisions are
bound to candidate, revision, and consent round. Only IDs in the selected
candidate's `attendeeIds` may consent to it. Every actual attendee must consent
before the host approval step; participants outside a partial candidate are
not treated as attendees or required to consent.

```http
POST .../{runId}/approval
```

```json
{
  "expectedInputRevision": 12,
  "consentRound": 3,
  "candidateId": "opaque-server-id",
  "decision": "APPROVE"
}
```

Only the host can approve/reject. Approval resumes the paused graph and
records approval, but **does not finalize the meeting**. The server requires
consent from every actual attendee listed in the candidate before accepting
host approval. This is enforced by the new time-coordination consent contract,
not the existing `/v1` role-assignment consent endpoint. Finalization remains
a separate domain command.

### Retry and cancel

```http
POST .../{runId}/retry
POST .../{runId}/cancel
```

Both require authorization and `expectedInputRevision`. Retry creates a new
execution under the same session only for retryable errors or an explicitly
stale run after refresh; it does not reuse an old result as current. Cancel is
idempotent and reports `CANCELLED`, `ALREADY_COMPLETED`, or `ALREADY_CANCELLED`.
Cancel does not undo a recorded consent or approval.

## 3. Snapshot and candidate envelope

```json
{
  "agentSessionId": "opaque-session-id",
  "runId": "opaque-run-id",
  "meetingId": "opaque-meeting-id",
  "inputRevision": 12,
  "consentRound": 3,
  "minimumAttendeeCount": 3,
  "rsvpDeadlineAt": "2026-11-02T09:00:00Z",
  "status": "ALL_AVAILABLE",
  "updatedAt": "2026-11-01T09:00:00Z",
  "participants": [
    {
      "participantId": "opaque-member-id",
      "invitationStatus": "SENT",
      "responseStatus": "ACCEPTED",
      "eligibilityStatus": "ACTIVE",
      "availabilityStatus": "SUBMITTED"
    }
  ],
  "missingInput": [],
  "searchEvidence": {
    "allAvailable": "FEASIBLE",
    "partialAllowed": false
  },
  "candidates": [],
  "error": null
}
```

Candidate `verified: true` is server-generated only after independent
validation. It must bind `candidateId`, `runId`, `meetingId`, and
`inputRevision`. Candidate payloads are immutable after publication. If input
or participant configuration changes, the candidate becomes stale and cannot
be selected, consented to, or approved. `minimumAttendeeCount` is a host-set
meeting input and participates in the input revision.

## 4. Error contract

**PROPOSED** stable error envelope:

```json
{
  "error": {
    "code": "STALE_INPUT_REVISION",
    "message": "모임 정보가 변경됐어요. 최신 정보를 확인해 주세요.",
    "retryable": false,
    "currentInputRevision": 13
  }
}
```

| HTTP | Example codes | Client behavior |
|---|---|---|
| 400/422 | `INVALID_REQUEST`, `INVALID_CONSTRAINT` | Show field guidance; do not retry unchanged |
| 401/403 | `AUTH_REQUIRED`, `NOT_MEETING_MEMBER`, `HOST_REQUIRED` | Stop action and restore/authenticate correct actor |
| 404 | `RUN_NOT_FOUND`, `CANDIDATE_NOT_FOUND` | Refresh; never infer success |
| 409 | `STALE_INPUT_REVISION`, `INVALID_STATE_TRANSITION`, `IDEMPOTENCY_CONFLICT` | Fetch authoritative snapshot; require explicit new action |
| 429/503 | `AGENT_BUSY`, `TOOL_UNAVAILABLE` | Honor `Retry-After`; do not create an unbounded retry loop |
| 504 | `AGENT_TIMEOUT` | Treat outcome as unknown; query the same `runId` before retry |

Logs and error responses must not expose secrets, bearer tokens, prompts,
private chain-of-thought, or raw checkpoint payloads.
