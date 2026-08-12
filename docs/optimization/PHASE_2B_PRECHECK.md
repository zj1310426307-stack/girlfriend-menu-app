# Phase 2B Precheck

## Baseline

- Commit: `5fe1cf888de18e9cf5dfc5a1154c22e4338490b2`
- Working tree before Phase 2B: clean (`main...origin/main`)
- `backend/crud.py`: 1,032 lines, 34,357 bytes, 37 top-level functions
- Database schema change planned: 0
- Alembic change planned: 0
- Mini-program change planned: 0

## Current callers

Non-game callers are concentrated in:

- `backend/api/routes/dishes.py`
- `backend/api/routes/orders.py`
- `backend/api/routes/admin.py`

Game and real-time callers remain in `backend/api/routes/games.py`,
`backend/api/routes/websocket.py`, the V2.4/V2.5 game services and
`backend/games/core/`. They are explicitly deferred to Phase 2C.

## Verification gate

| Check | Result |
|---|---|
| First unrestricted local run | 79 passed, 2 setup errors because Windows denied pytest access to its default system temp directory |
| Controlled backend baseline | 81 passed, 11 warnings (`--basetemp backend/.pytest_phase2b_baseline`) |
| Router contract | 2 passed |
| HTTP operations | 87 |
| WebSocket paths | 3 |
| Compile/import baseline | Covered by the existing release gate; rerun after this phase |

The two initial setup errors were environment errors, not application failures.
Pointing pytest at a repository-owned writable temporary directory produced the
required clean baseline.

## Controlled production smoke

Completed against `https://girlfriend-menu-api.onrender.com` after deploying
Phase 1 and Phase 2A commit `5fe1cf8`:

- `/api/health`: HTTP 200
- `/api/ready`: HTTP 200; PostgreSQL ready; release remains blocked only by the
  known missing S3/R2 credentials
- legacy device recovery: stable customer ID, token rotation, old token rejected
- order submission: passed with controlled order `#2`
- admin status update: order `#2` changed to `已接单`
- game HTTP action: flight room state version advanced from 1 to 2
- WebSocket disconnect/reconnect: room `82MJZX` returned
  `state -> session -> pong` on both connections and reconnect-token recovery
  returned HTTP 200

Observed performance signal: the two WebSocket state handshakes took 33.39 and
35.94 seconds. Correctness passed; latency is a P1 follow-up and is not changed
by this repository modularization.

## Risk and rollback

Highest risks are transaction ordering and accidentally moving game persistence.
The first execution round therefore moves only Dish and Favorite. Existing CRUD
entry points remain compatibility wrappers, so rollback is file-scoped:

1. restore `backend/api/routes/dishes.py`;
2. restore the Dish/Favorite wrapper bodies in `backend/crud.py`;
3. remove the new `backend/repositories/` and `backend/services/` files;
4. rerun the 81-test and 87/3 route gates.

