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
- Known readiness state: PostgreSQL ready; S3/R2 credentials remain an external
  release blocker

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
| Production readiness blocked by missing S3/R2 credentials | release blocker for uploads | `/api/ready` | deployment configuration | deployment operations |
| Pytest default Windows temp root can be unreadable | local environment | initial 79 passed + 2 setup errors; repository-owned `--basetemp` yields 81/85 passed | developer test command | developer tooling |

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

