# Agent Core Test Scenarios

Status: required test plan before any production API integration. A subset of
local domain, graph, checkpoint, and CP-SAT scenarios is implemented under
`tests/`; server/API integration tests remain outstanding.

## 1. Domain and readiness unit tests

| ID | Scenario | Expected result |
|---|---|---|
| D-01 | Organizer and at least one other accepted invitee have valid availability. | Input is ready; MVP minimum of two eligible participants is met; roster and slots preserve server participant IDs. |
| D-02 | Invite is sent but RSVP is pending, before or after its deadline. | `WAITING_FOR_INPUT`; deadline expiry alone does not decline or exclude the invitee, and no partial candidate is allowed. |
| D-03 | Invitee accepted but has not submitted time. | `WAITING_FOR_INPUT`; no availability is fabricated. |
| D-04 | Invitee explicitly declined. | Excluded from active roster; not represented as time-unavailable. |
| D-05 | Organizer availability missing or malformed. | Input rejected/waiting; solver is not called. |
| D-06 | Duplicate participant IDs, unknown IDs, invalid interval, bad date or timezone. | Validation fails closed; no solver call. |
| D-07 | Fewer than two eligible participants attempt to start a run. | Reject as unsupported MVP input; no solver call. |
| D-08 | Host sets minimum attendee count below two or above the current eligible roster. | Reject; do not clamp or substitute a default. |
| D-09 | Host changes the per-meeting minimum attendee count. | Persist explicit host value, increment `inputRevision`, and invalidate existing candidates/selections/consents/approvals. |
| D-10 | RSVP deadline passes while an invitee remains pending. | Preserve `PENDING` and `ACTIVE`; only an explicit host exclusion may change eligibility. |
| D-11 | Host explicitly excludes a pending invitee after the deadline. | Record actor/time/reason; set `EXCLUDED_BY_HOST` while preserving `PENDING`; increment revision and invalidate existing results. |
| D-12 | Host attempts exclusion before the deadline, on an accepted/declined invitee, or with stale revision. | Reject; no participant or candidate state changes. |
| D-13 | Qwen proposes participant roster or host-minimum changes, or relaxing an absolute condition. | Reject or clarify; no state mutation. There is no per-person required-attendee feature in MVP. |
| D-14 | Qwen proposes a name matching two participants. | Ask user to resolve; no guessed ID. |
| D-15 | Qwen proposal is valid but not confirmed. | Constraints and input revision remain unchanged; no solve begins. |
| D-16 | User confirms a proposal against a stale base revision. | `409`/stale result; require refresh and new confirmation. |

## 2. Search-policy and optimizer tests

| ID | Scenario | Expected result |
|---|---|---|
| S-01 | At least one all-attendee interval exists. | Return validated `ALL_AVAILABLE` candidates; partial solver is never called. |
| S-02 | All-attendee search returns `INFEASIBLE`; partial has feasible solutions. | Partial solver runs; absolute constraints and host-set minimum hold; attendee count is maximized first. |
| S-03 | All-attendee search returns `UNKNOWN`. | No partial fallback and no “no schedule” result. |
| S-04 | All-attendee search times out. | No partial fallback; run remains queryable and retry policy applies. |
| S-05 | Partial search returns `UNKNOWN`/timeout. | No `NO_FEASIBLE_SCHEDULE`; report unresolved/error. |
| S-06 | Partial candidate count is below the host-configured minimum. | Candidate rejected; no `max(2, ceil(N/2))` fallback is applied. |
| S-07 | Partial candidate violates an absolute constraint. | Candidate rejected. MVP has no individually required attendees. |
| S-08 | Partial candidate lists a pending, excluded, or non-submitting invitee as unavailable. | Candidate rejected. |
| S-09 | `FEASIBLE` solution found before deadline. | Candidate may be returned as feasible after deterministic validation; never label optimal. |
| S-10 | `INFEASIBLE` result from invalid model or different input revision. | Must not trigger partial fallback; treat as tool error/stale. |
| S-11 | Two candidates have identical slot and attendee set. | Deduplicate; deterministic tie-break ordering is stable. |
| S-12 | More than three candidates are found. | Return at most three according to documented deterministic ranking. |
| S-13 | Time is 09:30–10:00 or ends at 24:00. | Preserve exact minute bounds and half-open interval; no rounding. |

## 3. Candidate validation and authorization

| ID | Scenario | Expected result |
|---|---|---|
| C-01 | Candidate contains a participant not in the server roster. | Reject candidate set. |
| C-02 | Candidate omits a submitted participant from an `ALL_AVAILABLE` result. | Reject candidate. |
| C-03 | `attendeeIds` and `unavailableIds` overlap or contain duplicates. | Reject candidate. |
| C-04 | Candidate interval exceeds submitted availability or violates duration. | Reject candidate. |
| C-05 | Client changes `verified`, `sourceRevision`, interval, or attendee list. | Server ignores client fields and resolves stored candidate by opaque ID. |
| C-06 | Candidate belongs to another meeting/run or is stale. | Reject selection/consent/approval with authorization or conflict response. |
| C-07 | Non-host attempts host approval. | Deny; no checkpoint resume. |
| C-08 | Participant submits consent for another participant. | Deny; actor ID comes from authentication. |
| C-09 | Partial candidate count is below the meeting's host-configured minimum or below two. | Reject result. |
| C-10 | Candidate generation returns unknown validation status. | Fail closed; do not publish as verified. |

## 4. State graph and durable execution

| ID | Scenario | Expected result |
|---|---|---|
| G-01 | Ready input follows normal path. | Snapshot → validation → all-attendee solver → validator → candidates. |
| G-02 | Missing input found. | Persist `WAITING_FOR_INPUT`; no solver or Qwen fabrication. |
| G-03 | Reschedule text has ambiguity. | Return proposal/questions; do not mutate or solve. |
| G-04 | Confirmed reschedule delta. | Compare-and-swap revision, new input revision/run, old candidates superseded. |
| G-05 | Process restarts while run is executing. | Restore durable checkpoint and recheck input revision before side effects. |
| G-06 | Process restarts at approval interrupt. | Restore same run; only authorized recorded decision can resume it. |
| G-07 | Supplied arbitrary `thread_id`/checkpoint ID. | Public API does not accept or trust it. |
| G-08 | Input revision changes during tool execution. | Mark stale; do not publish candidate or continue to approval. |
| G-09 | Cancel during solve. | Cooperative stop; terminal `CANCELLED` only after execution stops. |
| G-10 | Cancel after approval recorded. | Do not undo approval; return already-completed/terminal outcome. |
| G-11 | Retry after tool failure. | Retry only permitted idempotent work for same snapshot; no duplicate mutation. |
| G-12 | Retry after `UNKNOWN`. | New bounded attempt is allowed by policy, but previous unknown is not called infeasible. |

## 5. Consent and approval sequence

| ID | Scenario | Expected result |
|---|---|---|
| A-01 | Candidate selected. | Selection recorded only; no consent/approval/finalization. |
| A-02 | A participant listed in a partial candidate has not consented. | Host approval remains unavailable until every actual attendee consents. |
| A-03 | A participant is not listed in a partial candidate. | That non-attendee is not required to consent to this candidate; do not treat them as unavailable without submitted availability. |
| A-04 | An actual attendee declines/reviews candidate. | No automatic acceptance or finalization; require explicit next action. |
| A-05 | Every actual attendee consents and host approves. | Resume approval checkpoint and record approval; meeting is still not finalized. |
| A-06 | Host rejects candidate. | Record rejection, resume/terminate run per policy; no finalization. |
| A-07 | Input or participant configuration changes after consent. | Candidate and consents become superseded; increment `inputRevision`; require a new candidate/consent round. |
| A-08 | Same approval request is replayed with same idempotency key/payload. | Return original outcome; do not duplicate resume or audit action. |
| A-09 | Same idempotency key is reused with a different candidate/decision. | `409 IDEMPOTENCY_CONFLICT`; no state mutation. |
| A-10 | Agent approval is followed by existing `/v1` finalization attempt. | Domains remain separate; no implicit bridge or fabricated `/v1` proposal. |

## 6. API resilience and security tests

| ID | Scenario | Expected result |
|---|---|---|
| R-01 | Client times out after server accepted start. | Client queries same `runId`; does not blindly create a second run. |
| R-02 | Duplicate start request, same key and payload. | Same run/result returned. |
| R-03 | Duplicate key with changed payload. | Conflict. |
| R-04 | Concurrent reschedule/availability update. | One compare-and-swap wins; stale action receives current revision. |
| R-05 | `429/503` with `Retry-After`. | Client honors delay and avoids uncontrolled retry storm. |
| R-06 | Model unavailable or malformed output. | Typed sanitized error; no candidate or constraint mutation. |
| R-07 | OR-Tools exception/invalid model. | Typed tool error; never `INFEASIBLE`. |
| R-08 | Prompt-injection text requests approval or participant disclosure. | Parser treats it as untrusted user text; no privileged tool/action occurs. |
| R-09 | Error/logging response inspected. | No bearer token, private reasoning, raw checkpoint, or unnecessary personal data. |
| R-10 | Cross-meeting run/candidate ID supplied. | Authorization failure; no existence leakage beyond approved API policy. |

## 7. End-to-end local experiment sequence

1. Create a test meeting and server-authenticated organizer/member identities.
2. Exercise sent/pending, accepted/no-availability, declined, and fully
   submitted participant states.
3. Verify readiness classification before invoking the optimizer.
4. Run all-attendee feasible, infeasible, unknown, timeout, and tool-error
   fixtures.
5. Verify partial search occurs only after proven all-attendee infeasibility;
   assert attendee maximum, host-configured minimum (>=2), absence of a
   per-person required-attendee feature, and exact intervals.
6. Pass an RSVP deadline without action, then explicitly exclude a pending
   invitee as host; verify response remains pending, the action is audited, and
   candidates are invalidated. Verify non-host and pre-deadline exclusions fail.
7. Tamper with candidate payload/revision and verify stored candidate
   revalidation blocks every action.
8. Propose a natural-language change, confirm that no mutation occurs before
   user confirmation, then test confirmation and stale confirmation.
9. Stop/restart the local process at a running checkpoint and an approval
   checkpoint; verify durable recovery.
10. Test duplicate start, reschedule, consent, approval, cancellation, timeout,
   and retry requests using idempotency keys.
11. Complete candidate selection → consent from every actual attendee
    (including partial-candidate semantics) → host approval; assert the
    meeting is not final until a separate, explicitly authorized
    finalization action exists.

## 8. Required gates before connecting the mobile UI

- Approve remaining **PROPOSED** decisions that affect API persistence,
  consent/approval integration, input revisions, idempotency, and route shape.
- Pass domain, optimizer, candidate, authorization, checkpoint-resume, and
  API-contract tests above.
- Provide OpenAPI or equivalent authoritative request/response schemas and
  stable error codes.
- Implement server persistence and a staging API with actual authenticated
  participant identities.
- Only then implement a mobile HTTP adapter. Keep the existing preview
  fixtures separate from production API responses.
