# Agent Run HTTP API

All routes require an active v2.1 USER account session in the
`Authorization: Bearer <token>` header and active membership in the room.

- `POST /v2/rooms/{room_id}/agent-runs`
  - Requires `Idempotency-Key` and `{"expectedInputRevision": <integer>}`.
  - Returns `202` with the Run ID, status/candidate URLs, and
    `workerDispatch: "NOT_CONFIGURED"`.
  - Replays with the same idempotency key return the existing Run.
- `GET /v2/rooms/{room_id}/agent-runs/{run_id}`
  - Returns Run status, source revision/hash, timestamps, and a typed error code.
- `GET /v2/rooms/{room_id}/agent-runs/{run_id}/candidates`
  - Returns persisted candidates and room-member participation/consent states.
- `POST /v2/rooms/{room_id}/agent-runs/{run_id}/cancel`
  - The Run creator or room host may cancel. Queued work is cancelled
    immediately; running work receives a cooperative cancellation request.

The HTTP layer does not invoke the Solver or Worker inline. A separate Worker
process/dispatcher is not yet connected, so accepted Runs remain `QUEUED` until
that integration is provided. Run DTOs omit account credentials, email,
checkpoint references, lease tokens, and lease ownership data.
