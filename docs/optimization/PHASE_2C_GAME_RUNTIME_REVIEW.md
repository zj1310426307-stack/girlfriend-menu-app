# Phase 2C Game Runtime Review — Round 2

## 1. Precheck

- Commit: `62e8ba71eef6a02a911a85c532d5fe4ab82c20ff`
- Worktree: Phase 2B Round 2 was verified but uncommitted and remains part of
  this working baseline; no existing change was discarded.
- Backend baseline: 94 passed, 11 warnings
- Router contract: 2 passed
- Public surface: 87 HTTP / 3 WebSocket
- Baseline measurements and environment facts:
  `PHASE_2C_PRECHECK.md`

## 2. Original architecture and runtime map

Before extraction, `crud.py` directly mixed game catalogue, room, seat, room
session, record, maintenance and statistics persistence. The complete caller,
table, commit and Round classification is in `PHASE_2C_GAME_RUNTIME_MAP.md`.

`GameRoomManager`, `DatabaseGameStateStore`, PostgreSQL CAS room leases,
settlement repair and turn-timeout repair were already separate and remain
unchanged. Round 1 did not create a second snapshot store or lock provider.

## 3. Persistence migration matrix

| Responsibility | Repository | Service | HTTP caller migrated | `crud.py` wrapper |
|---|---|---|---:|---:|
| Game catalogue | `game_runtime` | `game_persistence_service` | yes | yes |
| Room create/get/runtime/status | `game_runtime` | `game_persistence_service` | low-risk calls only | yes |
| Player list/join/disconnect | `game_runtime` | `game_persistence_service` | low-risk calls only | yes |
| Room session token | `game_runtime` | `game_persistence_service` | no; WebSocket deferred | yes |
| Finish/list records | `game_runtime` | `game_persistence_service` | list only | yes |
| Stale-room maintenance | unchanged | unchanged | no | direct implementation |
| Game stats | unchanged | unchanged | no | direct implementation |

New files:

- `backend/repositories/game_runtime.py`
- `backend/services/game_persistence_service.py`

Only `backend/api/routes/games.py` moved its low-risk persistence calls to the
Service. `backend/api/routes/websocket.py`, `game_maintenance.py`, flight and
V2.5 game services continue through compatibility wrappers.

## 4. Transaction compatibility

### Room

- Catalogue availability and creator validation still precede creation.
- Room code retains six characters and the same alphabet.
- A pre-query collision or unique-constraint race retries up to 20 times.
- New room is touched, added, committed and refreshed in the original order.

### Player

- Repeated join is idempotent and refreshes activity/disconnect state.
- First free seat, room-full 409 and finished/abandoned 409 are unchanged.
- The Repository honors `commit=False` by flushing without committing, allowing
  the WebSocket gateway to compose join plus room-session token. However, the
  pre-existing cross-domain join notification path may issue its own commit for
  a non-creator human join. Round 1 preserves that behavior; Round 2 must make
  the notification transaction boundary explicit rather than silently claiming
  the whole Service is commit-free.
- Join notifications remain Service orchestration after persistence; the
  Repository never imports notification code.

### Room session

- Token format remains `gfr_` plus the same URL-safe random length.
- Only SHA-256 hash is stored; raw token is returned exactly once.
- Expiry remains 15 minutes.
- `commit=False` still flushes without taking over the gateway transaction.

### Record

- Room plus round remains the idempotency key.
- Retry returns the existing record without replacing result or duration.
- Human winner must be a member; `ai_*` winner remains allowed.
- Human winner score increases once.
- Room finishes and clears expiry plus persisted lease ownership.
- New record starts with `settlement_status=pending` and zero attempts.
- Unique-constraint race rolls back, then reloads the existing round.
- Member history still hides records whose result `_settlement` is `pending`.

Settlement rewards, replay, memories, notifications and maintenance repair were
not moved into Repository or changed in Round 1.

## 5. `crud.py`

- Before Round 1: 799 lines / 26,658 bytes
- After Round 1: 525 lines / 17,578 bytes
- Net reduction: 274 lines / 9,080 bytes
- Remaining direct game domains: stale-room maintenance and aggregate game stats
- Compatibility wrappers remain for every migrated function used by WebSocket,
  maintenance, legacy services and tests.

## 6. API and database

- HTTP operations: 87
- WebSocket paths: 3
- HTTP path/request/response/status changes: 0
- WebSocket path/payload/close/reconnect changes: 0
- Schema changes: 0
- Model changes: 0
- Alembic changes: 0
- Mini-program changes: 0

No OpenAPI regeneration command exists in this Taro/FastAPI repository, and no
public interface changed. Jellyfish separation was applied as
Router → Service → Repository while preserving the existing transport contract.

## 7. Tests

Five new `test_game_persistence_contracts.py` tests cover:

- catalogue and unavailable-game errors;
- deterministic room-code collision retry;
- seat idempotency, full room, disconnect and `commit=False` visibility;
- room-session hashing, expiry and reissue;
- invalid/AI winner, record idempotency, winner score, lease clear and pending
  settlement visibility;
- single-owner PostgreSQL CAS lease, expired takeover and owner-only release.

| Command | Result |
|---|---|
| `python run_tests.py -q` | 99 passed, 11 warnings |
| `python run_tests.py tests/test_router_contract.py -q` | 2 passed |
| `python -m compileall -q .` | passed |
| API operation count | 87 HTTP / 3 WebSocket |
| `git diff --check` | passed; Windows line-ending warnings only |

A selected persistence subset exposed an existing order dependency in
`test_game_persistence.py`: run alone, it assumes an earlier dice integration
test has already created a record. The official full suite runs in repository
order and passed 99/99. This Round does not change game stats or rewrite that
historical assertion.

## 8. Snapshot, lease, privacy and recovery guarantees

- `core/game_state_store.py`: unchanged; PostgreSQL remains durable source,
  Redis optional hot cache and memory process-local fallback/cache.
- `core/game_room_lease.py`: unchanged; PostgreSQL CAS remains the authority.
- `realtime.py`: unchanged; dice viewer filtering and Gomoku public board remain
  exactly as before.
- WebSocket reconnect, cold manager restore, completed-event recovery and seat
  restore remain on their existing paths and passed the full regression suite.

## 9. Controlled production smoke and performance

- `/api/health` and `/api/ready`: **NOT VERIFIED IN THIS ENVIRONMENT** because
  both the browser safe-open layer and restricted shell connection were blocked.
- Create/action/WebSocket/reconnect/completion: **NOT VERIFIED IN THIS
  ENVIRONMENT**; no production identity or game state was fabricated.
- No first-state, reconnect or settlement latency claim is made in Round 1.
- The historic 33–36 second observation remains an operations/profiling issue.
  No performance optimization was attempted without current stage timings.

## 10. Socket session boundary

Round 2 adds `backend/services/game_socket_session_service.py` and moves the
following orchestration out of the Router:

- durable room load and lifecycle validation;
- PostgreSQL CAS lease acquisition and idle release;
- runtime snapshot/container plus durable-seat restoration;
- customer-token or explicitly enabled legacy identity authentication;
- `join_game_room(commit=False)` plus room-session token composition and the
  caller-owned commit;
- manager join, durable status sync and disconnect persistence.

The Router still owns socket acceptance, receive/send calls, join-first parsing,
game-type validation, protocol-specific JSON, public error text and close codes.
Its size fell from 425 lines / 17,076 bytes to 273 lines / 10,939 bytes.

The pre-existing guest notification commit inside `join_game_room` remains
observable and unchanged. Moving it would alter transaction ordering and needs
an explicit cross-domain notification/outbox decision; Round 2 does not claim a
single transaction across notification creation.

## 11. Settlement boundary

Round 2 adds `backend/services/game_settlement_service.py`. It preserves this
exact order:

```text
finish_game_room
-> settlement pending
-> attempts +1
-> commit
-> rewards
-> replay
-> memory
-> notification
-> _settlement complete
-> settlement_status complete
-> settled_at
-> commit
```

The Router keeps a temporary compatibility alias for the sync helper used by a
historical direct test, but production completion calls the new Service.
Notifications use the existing idempotent `create_notification_once` path so a
re-delivered completion event repairs missing replay/effects without duplicating
notifications. `game_maintenance.reconcile_game_settlements` remains unchanged
and repairs a committed pending record after a simulated replay-stage crash.

## 12. Protocol compatibility

Golden-field tests now lock:

- admin `ready`, ping/pong, invalid auth and close `4401`;
- unified join-first error and close `4400`;
- missing room close `4404`;
- non-owner `room_busy`, `retry_after_ms=1200` and close `4429`;
- legacy dice error envelope without a `game` field;
- unified error and pong envelopes;
- first-state followed by the room `session` payload and `gfr_` token.

Existing dice privacy, viewer-filtered recovery, process-restart snapshots,
completed-event persistence and online Gomoku tests remain green.

## 13. Round 2 verification

| Command | Result |
|---|---|
| `python run_tests.py -q --basetemp=...` | 107 passed, 11 warnings |
| Round 2 golden/crash tests | 8 passed |
| Router contract | 2 passed; 87 HTTP / 3 WebSocket |
| `python -m compileall -q .` | passed |
| `npm.cmd run test:session` | passed |
| `npm.cmd run test:games` | passed |
| `npm.cmd run test:landlord` | passed |
| `npm.cmd run build:weapp` | passed; Taro compiled successfully |
| `git diff --check` | passed; Windows line-ending warnings only |

Database schema/model/Alembic changes remain zero. HTTP and WebSocket paths,
HTTP schemas, mini-program source, game rules, reward values, replay schema,
snapshot JSON and lease schema remain unchanged.

Production controlled smoke and the historic 33–36 second first-frame latency
remain **NOT VERIFIED IN THIS ENVIRONMENT**. No performance change was made.

## 14. Remaining realtime risks

- `GameRoomManager` still combines socket registry, dice/Gomoku live state,
  filtering, snapshot/recovery, rule dispatch, AI, completion and broadcast;
  structural separation belongs only to Round 3.
- Socket protocol parsing and action loop intentionally remain in the Router.
- Join notifications can commit inside the membership flow as documented above.
- Controlled production create/join/reconnect/complete latency is still a
  deployment follow-up.

## 15. Rollback

No database rollback is required. Restore `backend/api/routes/websocket.py`,
remove the two Round 2 Services and their two tests, then rerun the 99-test
Round 1 baseline and the 87/3 Router contract gate.

## 16. Round 2 status and readiness

**PASS WITH DEPLOYMENT FOLLOW-UP.** Local settlement, crash recovery, transport
compatibility, API and mini-program gates pass. Controlled production flows and
latency were not verified in this environment.

**Round 3 readiness: YES, after explicit approval.** Round 3 may structurally
split `realtime.py` only; it must not rewrite dice/Gomoku rules, privacy,
snapshot, recovery, lease or protocol behavior. This execution stops at Round 2.

## 17. Round 3 execution

Round 3 separates the combined module without changing its public contract:

- `backend/realtime_events.py` owns `OrderEventHub` and its singleton;
- `backend/game_runtime/manager.py` owns `GameRoomManager`, dice/Gomoku state,
  filtering, recovery, AI and broadcasts;
- `backend/realtime.py` is a small compatibility facade exporting the same
  classes and exact singleton objects;
- production modules import the new owner directly, while historical tests and
  external scripts remain valid through the facade.

The production gate before Round 3 found and fixed three real defects: an
existing seat lacked its room relationship during reconnect token rotation,
durable snapshot writes blocked every broadcast, and state versions were
incremented after payload creation. The controlled Render run then completed a
two-client Gomoku round with one disconnect/reconnect, winner match and complete
settlement. Nine action samples measured p50 97 ms (max 694 ms). First state
remains about 4.9-9.8 seconds and settlement visibility about 34.5 seconds, both
tracked as P1 hosted database/platform latency rather than correctness failures.

## 18. Round 3 rollback

Recombine `realtime_events.py` and `game_runtime/manager.py` into `realtime.py`,
restore direct imports, and remove the facade identity test. No schema or data
rollback is required.
