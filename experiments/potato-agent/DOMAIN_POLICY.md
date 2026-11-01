# Potato Meet Time Coordination — Domain Policy

Status: policy baseline requested for the Agent Core experiment. Items marked
**PROPOSED** are design choices, not approved production behavior.

## 1. Domain boundary

The new time-coordination domain finds a shared meeting time. The existing
`server-api` `/v1/meetings` domain collects role conditions, computes role
assignments, obtains participant consent for an assignment round, and lets the
host finalize that round. Its `Room`, `Submission`, `Proposal`, `ConsentRow`,
`revision`, and `round` must not be silently reused as Agent Core state.

**PROPOSED:** Keep Agent Core behind a separately versioned API and persistence
boundary (for example, `/v2/coordination/...` and `coord_*` tables). Do not
change existing `/v1` routes, models, migrations, or role-assignment behavior
as part of the experiment.

The current app request (`AppointmentAiRecommendationRequest`) is a useful
starting shape, not a server contract. Its local friend IDs are not necessarily
the server's authenticated member IDs. Only server-resolved participant IDs
may be used in authoritative availability, candidate, or approval records.

## 2. Core entities

All identifiers below are opaque server-issued IDs unless explicitly marked
otherwise. Times are local wall-clock minutes on an ISO date in
`Asia/Seoul`; intervals are half-open `[startMinute, endMinute)`. Never round
user input or solver output silently.

### Participant

```text
Participant {
  participantId: string
  displayName: string
  role: ORGANIZER | INVITEE
  invitationStatus: NOT_APPLICABLE | NOT_SENT | SENT
  responseStatus: PENDING | ACCEPTED | DECLINED
  eligibilityStatus: ACTIVE | EXCLUDED_BY_HOST
  excludedAt: timestamp | null
  exclusionReason: string | null
}
```

- The organizer is an accepted participant and cannot be omitted from the
  participant roster.
- MVP does not support designating individual participants as required
  attendees.
- An invitation being selected in the app is not proof that it was sent.
- An invitee is not an authoritative participant until the server has linked
  the invitee to an authenticated account/member.
- Exclusion is a separate, explicit host action. It does not rewrite a pending
  RSVP as declined and must record actor, time, reason, and audit event.
- A meeting may have an optional host-configured `rsvpDeadlineAt`. Passing the
  deadline does not change `responseStatus` or `eligibilityStatus`.

### Availability

```text
AvailabilitySubmission {
  participantId: string
  status: NOT_SUBMITTED | SUBMITTED
  slots: [{ date: YYYY-MM-DD, startMinute: integer, endMinute: integer }]
  timeZone: Asia/Seoul
  submittedAt: timestamp | null
  updatedAt: timestamp | null
  submissionVersion: integer
}
```

- `NOT_SUBMITTED` has no slots. It does not mean unavailable.
- A submitted empty slot list is invalid; express explicit unavailability as a
  separate constraint, not as missing availability.
- Only a participant's own authenticated action may submit or update their
  availability. A host cannot invent it on their behalf.
- Slots must be within `[0, 1440]`, have `startMinute < endMinute`, refer to an
  allowed meeting date, and use the domain timezone. Keep minute precision.
- **PROPOSED:** impose API limits on slot count and meeting horizon after
  product/API capacity requirements are agreed.

### MeetingConstraint

```text
MeetingConstraint {
  meetingId: string
  title: string
  activity: string
  location: string
  durationMinutes: integer
  dates: YYYY-MM-DD[]
  timeZone: "Asia/Seoul"
  rsvpDeadlineAt: timestamp | null
  minimumAttendeeCount: integer
  absoluteConstraints: Constraint[]
  preferences: Constraint[]
  sourceRevision: integer
}
```

Absolute constraints and the host-configured minimum attendance are hard
constraints. MVP has no per-person required-attendee feature. Preferences are
optimization objectives only after hard constraints are satisfied. Neither
Qwen nor the optimizer may weaken, remove, or reinterpret a hard constraint.
User changes to a Qwen-parsed proposal require explicit review and confirmation
before they affect this entity or start a new run.

### Candidate

```text
Candidate {
  candidateId: string
  meetingId: string
  agentRunId: string
  sourceRevision: integer
  date: YYYY-MM-DD
  startMinute: integer
  endMinute: integer
  timeZone: "Asia/Seoul"
  type: ALL_AVAILABLE | PARTIAL_ALTERNATIVE
  attendeeIds: string[]
  unavailableIds: string[]
  solverStatus: OPTIMAL | FEASIBLE
  verified: true
  explanation: { agentSummary: string, optimizerSummary?: string }
}
```

`candidateId` is opaque and bound to the exact run, candidate payload, and
input revision. It is not a client-generated ID. `unavailableIds` may contain
only confirmed, eligible participants whose submitted availability does not
cover the candidate; it must never include pending, not-submitted, or otherwise
unknown participants.

### AgentRun

```text
AgentRun {
  agentSessionId: string
  runId: string
  meetingId: string
  status: AgentStatus
  sourceRevision: integer
  createdByParticipantId: string
  idempotencyKey: string
  checkpointRef: string | null
  createdAt: timestamp
  updatedAt: timestamp
  error: StructuredError | null
}
```

The public `agentSessionId` groups reschedules. Each execution has a distinct
`runId`. LangGraph `thread_id`, checkpoint IDs, prompts, and tool traces remain
server-private. Persist only the minimum checkpoint data needed to resume and
apply the product's retention policy.

### Approval

```text
Approval {
  approvalId: string
  meetingId: string
  candidateId: string
  sourceRevision: integer
  consentRound: integer
  status: PENDING | APPROVED | REJECTED | SUPERSEDED
  requestedByParticipantId: string
  decidedByParticipantId: string | null
  createdAt: timestamp
  decidedAt: timestamp | null
}
```

Candidate selection, consent from every participant named in that candidate's
`attendeeIds`, host approval, and final meeting confirmation are distinct
actions. For a partial candidate, every actual attendee must consent; people
not listed as attendees are not asked to consent to that candidate. An
all-attendee candidate consequently requires consent from all eligible
participants. Agent approval alone does not finalize a meeting. This consent
must use the new time-coordination domain, not the existing role-assignment
`/v1` consent API.

## 3. Participant eligibility and missing input

1. MVP supports only runs with at least two eligible participants. An eligible
   participant is active, accepted, and has valid submitted availability.
2. A declined invitee is excluded from the active attendee set. Decline is not
   an availability submission.
3. A pending invitee is unresolved. A missing response is not a decline or an
   unavailable interval. Passing `rsvpDeadlineAt` does not automatically
   change this.
4. An accepted invitee without submitted availability is separately
   unresolved. Do not infer any available or unavailable interval.
5. The organizer must have valid submitted availability before solving.
6. Block both all-attendee and partial calculation while a sent invitee is
   pending or an accepted participant has not submitted availability. Return
   `WAITING_FOR_INPUT` with separate RSVP and availability reasons.
7. After the deadline, the host may explicitly exclude a still-pending invitee
   using an authenticated, reasoned, audited action. Exclusion changes
   participant configuration and `inputRevision`, invalidating old candidates.
   The pending response remains recorded as pending; timeout alone never
   excludes anyone. The host can instead extend the deadline or continue to
   wait.
8. The host configures `minimumAttendeeCount` per meeting. There is no
   `max(2, ceil(N / 2))` default. The configured value must be at least 2 and
   no greater than the eligible participant count at solve time. If membership
   or eligibility changes make it impossible to meet, do not silently lower
   the configured minimum; require an explicit host update or report no
   policy-compliant partial result.

## 4. Search and optimization policy

1. Search for candidates satisfying every eligible participant's availability
   and every absolute constraint.
2. Only a proven no-solution result permits partial search.
3. For partial search, retain every absolute constraint, enforce the host's
   configured `minimumAttendeeCount`, and maximize attendee count before
   optimizing preferences.
4. Apply soft preferences only after hard-constraint feasibility and attendee
   count priority are respected.
5. Return at most three deterministically ordered, deduplicated candidates.
   The production tie-break ordering is **PROPOSED**: attendee count,
   preference score, earliest date, earliest start, then stable candidate
   fingerprint. The local CP-SAT prototype has no preference model; after
   maximizing attendance it orders equal-count results by date, start minute,
   end minute, then participant IDs.
6. Never show an unverified, stale, malformed, or solver-unknown candidate.

An optimizer `INFEASIBLE` result is evidence only for the precise search space
and constraint snapshot it evaluated. It does not establish that a participant
who did not respond is unavailable.

## 5. Versioning and rounds

Use independent monotonically increasing versions:

- `inputRevision`: meeting constraints (including the host-set minimum and
  RSVP deadline), participant membership/eligibility/response, and availability
  submissions used by a run.
- `consentRound`: a candidate/approval round. Any new candidate set or
  material input change starts a new round; old consent cannot be carried
  forward.

Candidate `sourceRevision` must equal the run's `inputRevision`. Any input or
participant-configuration mutation (including explicit exclusion) marks active
candidates and pending approvals `STALE` or
`SUPERSEDED`, and invalidates their ability to be selected, consented to, or
approved. A consent-only mutation increments consent state/round as applicable
without pretending that input data changed. Existing `/v1` `Room.revision`
currently also changes for consent, so it is not a drop-in `inputRevision`.

**PROPOSED:** an input revision is a canonical snapshot hash or monotonic
meeting counter paired with a snapshot hash. The counter supports conflict
responses; the hash makes exact input identity auditable.

## 6. Existing backend compatibility findings

- `/v1/meetings/{room_id}/calculations` uses OR-Tools for role assignments,
  requires every member to submit role conditions, and persists a `Proposal`.
- `/consent` records per-member agreement for an assignment round;
  `/finalize` requires all participants' current-round agreement and a host.
- `workflow_models.py` constrains intervals and durations to 30-minute
  multiples; the optimizer searches 30-minute slots.
- The server reports OR-Tools `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, and
  `UNKNOWN`; only the first two produce a feasible plan.
- `/ai/parse-condition` calls Qwen to parse participant-entered natural
  language into a draft. It does not schedule, persist availability as a
  submission, or finalize a meeting.
- Existing member IDs are server-issued; mobile friend IDs are not proven to
  be those IDs.

Therefore the existing `/v1` calculation and consent/finalize APIs must remain
untouched and must not be presented as the new time-coordination Agent Core.
