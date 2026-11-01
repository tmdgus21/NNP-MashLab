# Potato Meet Agent Core experiment

This is a local-only LangGraph execution skeleton based on the five design
contracts in this directory. It does not modify or call `server-api`, the
database, or the mobile app. The optional Qwen adapter can call an explicitly
configured loopback llama.cpp server, but never starts or reconfigures it.

## Setup

From this directory, create and activate a local virtual environment, then
install the pinned dependencies:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run the LangGraph fixture regressions and actual CP-SAT tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Run the local graph demo:

```powershell
.\.venv\Scripts\python.exe -m potato_agent.demo
```

The demo writes a SQLite checkpoint file in the current directory and pauses
at candidate selection. Its meeting inputs are explicitly local fixtures; the
solver result is computed by OR-Tools CP-SAT. The graph exposes no HTTP API;
its SQLite `thread_id` is an internal local checkpoint key, not a public ID.

## Implemented flow and safeguards

- Pydantic models validate participant/RSVP states, submitted availability,
  Asia/Seoul minute intervals, host-configured minimum attendance, and the
  run's input revision and snapshot hash.
- The local validator supports date-scoped absolute time windows only; this
  narrow fixture schema does not define the eventual production constraint DSL.
- Missing RSVP and accepted-but-unsubmitted availability are reported
  separately; neither is treated as unavailable.
- `CpSatSolverAdapter` uses one Boolean per feasible date/minute interval and
  an exactly-one-slot constraint. The all-attendee solve searches first;
  partial search is only called after proven all-attendee `INFEASIBLE`.
- Partial solve maximizes attendee count subject to the host minimum. Only
  `OPTIMAL` proves the maximum; `FEASIBLE` candidates explicitly carry no
  maximum-attendance claim. Equal-count candidates sort by date, start minute,
  end minute, then participant IDs.
- CP-SAT uses one search worker, a fixed seed, and a configurable time limit.
  Timeout/unknown, cancellation, stale revision, invalid model, and exceptions
  remain distinct outcomes; none is treated as infeasibility.
- Availability intervals that touch are merged as half-open continuous time.
  Minute precision is preserved; no 30-minute rounding is applied.
- Candidate output is independently validated and bound to the fixture run
  and revision. Only verified candidates can reach the selection interrupt;
  results are deduplicated and capped at three.
- SQLite checkpoints allow a local process to close and reopen between
  candidate selection, attendee consent, and host approval.
- Approval is recorded separately from meeting finalization. This experiment
  never finalizes a meeting.

The `FixtureToolAdapter` remains available for deterministic LangGraph tests.
The CP-SAT adapter is local-only and accepts an injected snapshot and revision
  provider. Authentication, authoritative snapshot loading, consent storage,
  durable production persistence, and API retries remain unimplemented.

  ## Optional local Qwen proposal adapter

  `QwenProposalAgent` parses reschedule requests into validated proposals and
  exposes only the read-only meeting tools declared in `llama_cpp.py`. It does
  not optimize, persist candidates, approve changes, or finalize meetings.
  `LocalProposalApprovalAdapter` is a non-durable test adapter; a proposal must
  be explicitly confirmed before it changes the local input snapshot.
  Duration changes and exact time-window removal are distinct operations.
  Schema or domain validation failure triggers at most one constrained
  regeneration with the error code and allowed change types; another failure
  raises `PROPOSAL_RETRY_EXHAUSTED` without mutating the snapshot.

  The adapter defaults to the local SSH tunnel
  `http://127.0.0.1:18081` and model ID `potato-qwen-test`. It refuses
  non-loopback endpoints and explicitly rejects port `8080`. Optional settings
  are `POTATO_LLAMA_CPP_URL`, `POTATO_QWEN_MODEL`, and
  `POTATO_QWEN_THINKING_MODE` (`think` or `no_think`). The user must start and
  configure the tunnel and llama.cpp separately. This project does not install
  llama.cpp, download a model, or assume that tool calling and JSON Schema output
  are supported. The health probe checks `/health`, `/props`, and `/v1/models`;
  it reports the served model ID but does not claim that chat capabilities have
  been verified.

  `confirm_and_recompute` is the local-only confirmed-proposal path: after
  explicit confirmation it advances the input revision, snapshot hash, consent
  round, and Agent Run ID, then runs CP-SAT through the existing LangGraph. It
  returns only candidates that pass the graph's independent validator, uses a
  local SQLite checkpoint, and does not persist a meeting or expose an HTTP
  endpoint.

  Fixture tests never contact Qwen. The separate live test is opt-in and is
  restricted to the `127.0.0.1:18081` tunnel and `potato-qwen-test`:

  ```powershell
  $env:POTATO_RUN_LIVE_QWEN = "1"
  .\.venv\Scripts\python.exe -m pytest -q -s tests\test_qwen_live.py
  ```

  The live test reports proposal inference latency and verifies a read-only tool
  call before explicit local approval and Graph/CP-SAT recalculation. It fails if
  the local tunnel or expected model ID is unavailable; it never falls back to
  the production endpoint on port `8080`.
