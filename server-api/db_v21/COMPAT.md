# ok_* → db_v21 compatibility map (API port checklist)

Current FastAPI still imports legacy `models` / `admin.models`. Cutover requires porting
`workflow.py` and `admin/*` to `db_v21` before switching `DB_NAME`.

| Legacy | v2.1 | Notes |
|--------|------|-------|
| `ok_rooms` | `rooms` | `config` JSON → `title`/`starts_at`/`ends_at`/`lifecycle_status`; `host_id` → OWNER `room_members` |
| `ok_members` | `room_members` | needs `account_id`; keep `token_hash` + idempotency hashes |
| `ok_ai_drafts` | `ai_drafts` | JSON fields restored |
| `ok_condition_submissions` | `condition_submissions` + slots/prefs | write both JSON + normalized rows |
| `ok_proposals` | `proposals` + assignments/inputs | `round` UNIQUE; invalidate old |
| `ok_consents` | `proposal_consents` | composite PK |
| `ok_room_events` | `room_events` | add `event_type` / `actor_member_id` |
| `ok_admin_accounts` | `accounts` (ADMIN) | `admin_role`/`approved`/`failures`/`revision` |
| `ok_admin_sessions` | `account_sessions` | `token_hash`/`csrf`/`revoked_at` |
| `ok_admin_otps` | `admin_otps` | same semantics |
| `ok_admin_rate_limits` | `admin_rate_limits` | same |
| `ok_admin_audit` | `admin_audit_logs` | rename fields |
| `ok_room_lifecycle` | `rooms` + `room_controls` | no cycle table |
| `ok_room_cycles` | **removed** | use `idempotency_records` + `proposals.round` |

Unit tests with `DATABASE_URL=sqlite://` continue to exercise **legacy** schema until the port lands.
