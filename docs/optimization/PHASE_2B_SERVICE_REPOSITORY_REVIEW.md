# Phase 2B Service / Repository Review — Round 1

This review covers only the task-authorized first round: Precheck, CRUD Map,
Dish and Favorite. Review, Order and Stats were not migrated.

## 1. Precheck

- Commit: `5fe1cf888de18e9cf5dfc5a1154c22e4338490b2`
- Initial worktree: clean and synchronized with `origin/main`
- Baseline backend: 81 passed, 11 warnings
- Router contract: 2 passed
- Baseline API shape: 87 HTTP operations, 3 WebSocket paths
- Controlled production smoke: all requested checks passed; full evidence is in
  `PHASE_2B_PRECHECK.md`
- Known pre-change readiness state: PostgreSQL ready while S3/R2 was missing.
  The follow-up release replaces that external blocker with the database image
  provider and requires a post-deploy readiness/upload smoke.

## 2. crud.py Before

- Lines: 1,032
- Bytes: 34,357
- Top-level functions: 37
- Domain map: `PHASE_2B_CRUD_MAP.md`

## 3. New architecture

```text
api/routes/dishes.py
  -> services/dish_service.py
     -> repositories/dishes.py
        -> SQLAlchemy Session / models

api/routes/dishes.py
  -> services/favorite_service.py
     -> repositories/favorites.py
        -> SQLAlchemy Session / models
```

The ranking endpoint intentionally remains on `crud.get_favorite_ranking`
because it is a cross-domain Stats aggregate, not Favorite persistence.

## 4. Migration matrix

| Old Function | New Location | Wrapper Kept | Callers Migrated |
|---|---|---:|---:|
| `list_dishes` | `dish_service.list_dishes` / `dishes.list_active` | yes | yes |
| `get_dish` | `dish_service.get_dish` / `dishes.find_active` | yes | yes |
| `create_dish` | `dish_service.create_dish` / `dishes.create` | yes | yes |
| `update_dish` | `dish_service.update_dish` / `dishes.update` | yes | yes |
| `delete_dish` | `dish_service.delete_dish` / `dishes.disable` | yes | yes |
| `list_favorite_dishes` | `favorite_service.list_favorite_dishes` / `favorites.list_active_dishes` | yes | yes |
| `add_favorite_dish` | `favorite_service.add_favorite_dish` / `favorites.add` | yes | yes |
| `remove_favorite_dish` | `favorite_service.remove_favorite_dish` / `favorites.remove` | yes | yes |

## 5. Transaction compatibility

Dish and Favorite preserve the previous operation order:

- Dish create: construct -> `add` -> `commit` -> `refresh`.
- Dish update: mutate fields -> `commit` -> `refresh`.
- Dish delete: set `is_active=False` -> `commit`; historical `order_items`
  remain snapshots.
- Favorite add: active-dish check -> owned-row check -> `add` -> `commit`;
  unique-race `IntegrityError` still rolls back and returns the dish.
- Favorite remove: owned-row lookup -> optional `delete` -> `commit`; absent rows
  remain a no-op.

Order creation, status transitions, Review rewards, notifications, memories,
tasks and WebSocket broadcasts are unchanged in this round.

## 6. API compatibility

- HTTP operations: 87
- WebSocket paths: 3
- Request changes: 0
- Response changes: 0
- Status-code changes: 0
- Deprecated-marker changes: 0

## 7. Database

- Schema change: 0
- Migration: 0
- Model change: 0

## 8. Tests

| Command | Result |
|---|---|
| `pytest tests/test_repository_contracts.py tests/test_service_contracts.py -q` | 4 passed |
| `pytest -q` | 85 passed, 11 warnings |
| `pytest tests/test_router_contract.py -q` | 2 passed |
| `python -m compileall -q .` | passed |
| API operation count | 87 HTTP / 3 WebSocket |
| `git diff --check` | passed; Windows line-ending warnings only |

The first isolated contract-test attempt failed because the shared SQLite schema
was only created by FastAPI lifespan. Module-scoped schema fixtures were added,
then the isolated and full test runs both passed. This was a test isolation issue,
not a production implementation failure.

## 9. crud.py After round 1

- Lines: 983
- Bytes: 33,346
- Top-level functions: 37, including eight documented compatibility wrappers
- Removed inline non-game persistence: 49 lines / 1,011 bytes net
- Remaining non-game domains: Order, Review, Stats and Favorite ranking
- Deferred domains: all game room/player/state/action/record/session/settlement
  functions and game statistics

## 10. Existing issues found

| Issue | Severity | Evidence | Affected code | Recommended phase |
|---|---|---|---|---|
| Production WebSocket first state latency about 33–36 seconds | P1 | controlled smoke room `82MJZX` | Render/game gateway path | performance/stability follow-up |
| Production image readiness changed from missing R2 to PostgreSQL provider | deploy verification | `/api/ready` and real upload/read smoke | deployment configuration | deployment operations |
| Pytest default Windows temp root can be unreadable | resolved locally | `backend/pytest.ini` now pins repository-owned `.pytest-tmp`; 87 passed | developer test command | developer tooling |

No bug was broadened into this refactor.

## 11. Rollback

Round 1 can be rolled back without database work:

1. restore `backend/api/routes/dishes.py` and the eight facade bodies in
   `backend/crud.py`;
2. delete `backend/repositories/dishes.py`, `favorites.py` and their package;
3. delete `backend/services/dish_service.py`, `favorite_service.py` and their package;
4. delete the two new contract-test files;
5. rerun 85 tests and the 87/3 Router contract gate.

## 12. Whether to enter Phase 2C

**NO.** Phase 2B is intentionally incomplete. The next authorized work is
Step 3 Review, Step 4 Order and Step 5 Stats. Phase 2C must remain a separate,
explicitly reviewed change after Phase 2B completes.

---

# Round 2 and Final Assessment

## 13. Round 2 precheck

- Commit: `62e8ba71eef6a02a911a85c532d5fe4ab82c20ff`
- Initial worktree: clean and synchronized with `origin/main`
- Baseline backend: 87 passed, 11 warnings
- Router contract: 2 passed
- Baseline API shape: 87 HTTP operations, 3 WebSocket paths
- `python -m compileall -q .`: passed through the project virtual environment
- Round 1 `crud.py`: 1,035 lines / 34,771 bytes on this deployed baseline

The first command using bare `python` could not run because no global Python is
on this Windows PATH. All gates then used `backend/.venv/Scripts/python.exe`.
One intentionally parallel test attempt produced a Windows SQLite file lock;
the affected Router contract was rerun sequentially and passed 2/2.

## 14. Review migration

```text
api/routes/orders.py
  -> services/review_service.py
     -> repositories/reviews.py
```

- Repository owns review lookup, insert, commit/refresh and
  `IntegrityError` rollback.
- Service preserves completed-order validation, duplicate 409 semantics and
  five-star reward/task ordering after the review commit.
- Customer authentication and ownership remain in the Router.
- Administrator notification and `order_reviewed` WebSocket broadcast remain in
  the Router and execute once after a successful review.
- `crud.get_review` and `crud.create_review` remain documented compatibility
  wrappers.

## 15. Order migration

```text
api/routes/orders.py
  -> services/order_service.py
     -> repositories/orders.py
```

Repository responsibilities now cover order/dish lookup, customer/admin lists,
cursor filtering, order and item-snapshot persistence, status-event persistence
and latest-event lookup. Service responsibilities retain:

- idempotency replay and cross-customer 409;
- active-dish validation and non-disclosing source-order ownership;
- the existing `desired_at` UTC conversion;
- immutable `OrderItem` name/price snapshots;
- repeat-order +2 after the order transaction;
- `ORDER_STATUS_TRANSITIONS`, same-status no-op and illegal-transition 409;
- completion +10 and MEAL task after the status transaction;
- completed rollback prohibition and append-only `ADMIN_ROLLBACK` audit.

Notification, first-meal/first-cook memories and order WebSocket broadcasts
remain Router-owned. All eight order functions remain compatibility wrappers in
`crud.py`.

## 16. Non-game Stats migration

```text
api/routes/admin.py
  -> services/stats_service.py
     -> repositories/stats.py
```

The summary, dish aggregate and ten-recent-order queries preserve their former
fields, grouping and ordering. `get_favorite_ranking` stays in `crud.py` because
it aggregates Dish, Order, Review and Favorite domains. `game_stats` and all
game/realtime persistence remain deferred.

## 17. crud.py final size and remaining domains

- Round 1/deployed baseline: 1,035 lines / 34,771 bytes
- Final Round 2: 799 lines / 26,658 bytes before final formatting checks
- Net reduction: 236 lines / 8,113 bytes
- Compatibility wrappers: Dish, Favorite, Review, Order and non-game Stats
- Remaining direct domains: Favorite Ranking and all game/realtime persistence

## 18. Transaction and API compatibility

Transaction order remains intentionally unchanged:

- order: `add -> flush -> snapshot items -> commit -> refresh -> repeat reward`;
- review: `add -> commit -> refresh -> five-star reward -> REVIEW task`;
- status: mutate -> append event -> commit -> refresh -> completion reward/task;
- rollback: restore prior status -> append audit event -> commit -> refresh.

API compatibility target and final gate:

- HTTP operations: 87
- WebSocket paths: 3
- Request/path/response/status/deprecation changes: 0
- Database schema/model/Alembic changes: 0

## 19. Round 2 tests

Seven dedicated `test_phase2b_round2_contracts.py` tests cover review validation/race and
rewards, order idempotency/snapshots/ownership/repeat/pagination/transitions/
rollback, Router notification/memory/broadcast and exact non-game Stats semantics.

| Command | Result |
|---|---|
| `python run_tests.py -q` | 94 passed, 11 warnings |
| `python run_tests.py tests/test_router_contract.py -q` | 2 passed |
| `python -m compileall -q .` | passed |
| API operation count | 87 HTTP / 3 WebSocket |
| `npm.cmd run test:session` | passed |
| `npm.cmd run test:games` | passed |
| `npm.cmd run test:landlord` | passed |
| `npm.cmd run build:weapp` | passed; Taro production build |
| `git diff --check` | passed; Windows line-ending warnings only |

PowerShell blocked the `npm.ps1` shim under the machine execution policy; the
same package scripts were executed successfully through the standard Windows
`npm.cmd` entry point.

## 20. Document drift and existing issues

- README's former “Round 1 only” architecture text was updated to current facts.
- Historical Phase 1/2A and release records were not rewritten.
- The production image provider is PostgreSQL (`UPLOAD_PROVIDER=database`); R2
  credentials are optional for a future scale-up, not the current readiness path.
- The historical 33–36 second first-state WebSocket observation remains a
  deployment/performance item outside this refactor. No storage, deployment,
  WebSocket or game code changed in Round 2.

## 21. Rollback

Round 2 has no database rollback. Restore `api/routes/orders.py`,
`api/routes/admin.py` and `crud.py`, then remove the Review/Order/Stats repository,
service and dedicated contract-test files. Re-run the 87/3 Router surface gate,
backend suite and mini-program regressions.

## 22. Phase 2B final status

**PASS WITH FOLLOW-UP.** The authorized non-game modularization is complete and
contract-covered. The follow-up is intentionally separate: Favorite Ranking and
game/realtime persistence still live in `crud.py`, while the production
WebSocket performance observation requires deployment-level measurement.

## 23. Whether to design Phase 2C

**YES, but do not enter it automatically.** Phase 2C needs a new audit for game
state, settlement, room ownership, multi-instance realtime and WebSocket
protocol boundaries. Those concerns are higher risk than the behavior-preserving
non-game extraction completed here.
