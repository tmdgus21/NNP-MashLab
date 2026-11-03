# ok_* → db_v21 compatibility map

FastAPI `workflow.py` / `admin/*` now use `db_v21` via `models.py` aliases.
Physical tables are v2.1 names. Live `.env` / deploy still point at `ok_*` until cutover approval.

| Legacy | v2.1 | Port notes |
|--------|------|------------|
| `ok_rooms` | `rooms` | `config`→`meeting_settings`; `status`→`progress_status`; `round`→`current_round`; `host_id`→`host_member_id`; title/starts_at/ends_at/lifecycle_status columns |
| `ok_members` | `room_members` | anonymous → `account_type=GUEST`; email USER via `/v1/auth` + optional `X-Account-Authorization` |
| `ok_ai_drafts` | `ai_drafts` | `member_id` synonym → `room_member_id`; `parse_status` |
| `ok_condition_submissions` | `condition_submissions` | `member_id`/`created_at` synonyms; slots/prefs optional on write |
| `ok_proposals` | `proposals` | solver statuses include OPTIMAL/FEASIBLE; `proposal_status` |
| `ok_consents` | `proposal_consents` | composite PK; API lowercase `agreed`/`pending`/`review` |
| `ok_room_events` | `room_events` | requires `event_type` |
| `ok_admin_accounts` | `accounts` (ADMIN) | `email`/`role`/`frozen` synonyms |
| `ok_admin_sessions` | `account_sessions` | lookup by `token_hash`; `revoked`→`revoked_at` |
| `ok_admin_otps` | `admin_otps` | same |
| `ok_admin_rate_limits` | `admin_rate_limits` | same |
| `ok_admin_audit` | `admin_audit_logs` | `action_type`/`target_id`/`occurred_at` |
| `ok_room_lifecycle` | `meeting_settings._lifecycle` + `room_controls` | `admin.models.Lifecycle` view |
| `ok_room_cycles` | `idempotency_records` | scope `extend:{room_id}` + `payload` |

Unit tests: `DATABASE_URL=sqlite://` → `Base.metadata.create_all` (v21 metadata).
