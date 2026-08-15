# Phase 3.0-R2C Test & Diagnostic Isolation Guardrails Review

Date: 2026-08-14

Repository HEAD inspected: `845fa51a649a3a2e4bec1200099618128a5b0b3d`

Scope: test and diagnostic database isolation only; no Phase 3.1 work

## 1. Precheck

The R2C task, the R2B1 trace review, the R2B2 instrumentation PoC review,
`backend/database.py`, the shared pytest configuration, the observability
contracts, every retained test import of `database`/`main`, and every file in
`scripts/` were read before implementation.

The opening worktree was already dirty with protected B0, B1, Round 1, R2A,
R2B1, and R2B2 work. `git status --short`, `git diff`, and `git diff --check`
were inspected. The initial diff check passed with only existing Git
LF-to-CRLF conversion warnings. No reset, checkout, clean, commit, push, merge,
rebase, deployment change, production acceptance run, or WeChat upload was
performed.

R2C did not modify `backend/database.py`, its local SQLite fallback, SQLAlchemy
construction, Render/Neon settings, API or WebSocket contracts, database
schema, Customer Session, game rules, UI, or R2B1 telemetry. Because no API
contract changed, OpenAPI/client regeneration was not applicable.

## 2. R2B2 isolation incident summary

The historical R2B2 PoC imported `database` before setting its isolated
`DATABASE_URL`. The import-time engine therefore retained the default local
SQLite URL and 552 rows carrying only `gf_r2b2_`/`*SENTINEL*` markers and their
declared foreign-key children were written there.

R2B2 performed a marker-only cleanup of exactly those 552 synthetic rows. A
second read found zero matching markers, no unrelated row or database file was
removed, and the final pytest-owned database was deleted normally. R2C does
not rewrite that history; it turns the lesson into an executable import-order
and cleanup contract.

## 3. Import-time database map

| Entry/module | Import path | Can initialize the engine? | Required URL timing/classification |
|---|---|---:|---|
| `tests/conftest.py` | test support bootstrap, then `core.settings`/telemetry | No engine itself | Creates and activates the UUID SQLite URL before all application imports |
| `tests/test_api.py` | `main` -> `database`, `models`, routes and services | Yes | Must rely on the already-active root conftest; its former fixed-file setup was removed |
| Direct persistence tests | `database.SessionLocal` or `Base`/`engine` | Yes | Protected by conftest before collection, independent of test-file order |
| Tests importing `test_api` | `test_api` -> `main` -> `database` | Yes | Protected by conftest before `test_api` collection |
| `test_settings_contracts.py` | `database` and `main` | Yes | Engine is already isolated; per-test environment changes exercise settings helpers, not engine rebinding |
| `test_customer_session_migration.py` | `database`, then Alembic with a `tmp_path` URL | Yes | Initial import is isolated; its temporary Alembic URL remains explicit |
| `alembic/env.py` | `database.Base`, `DATABASE_URL`, then `models` | Yes | Deployment/migration tool: URL must be selected before Alembic starts; R2C gate used an isolated URL |
| `main.py` and production modules | `database.engine`, `SessionLocal`, `Base` | Yes | Production/development process environment must be set before import; semantics unchanged |
| `seed.py` CLI branch | delayed import of `database` objects | Yes | Development/operational tool; explicit environment or unchanged local fallback applies |
| `scripts/backup_database.py` | constructs its own SQLAlchemy engine at call time | Yes, separate operational engine | Production/development backup source remains explicit or uses its existing fallback; never auto-switched |
| `scripts/verify_backup.py` | constructs an engine only for a restored target | Yes, separate verification engine | SQLite uses a temporary restore directory; PostgreSQL requires an explicit `restore_verify` URL |
| Remote acceptance/release scripts | HTTP/WebSocket/file checks only | No | No local application engine import |

All retained database-using test modules are now dominated by the root
conftest bootstrap. There is no retained R2B2 PoC script. The unified helper is
under `backend/test_support`; no production runtime module imports it.

## 4. Pytest bootstrap order

The previous safety property lived in `tests/test_api.py`: that module deleted
a fixed `tests/test_girlfriend_menu.db`, wrote `DATABASE_URL`, and only then
imported `main`. Other test modules could import `database` directly during
collection, so safety depended on `test_api` being collected first.

The final order is:

```text
pytest loads root tests/conftest.py
  -> fingerprint default backend/girlfriend_menu.db (read-only)
  -> create UUID SQLite ownership handle under backend/.test-tmp
  -> set DATABASE_URL and APP_ENV=test
  -> import settings/telemetry fixtures
pytest collects tests
  -> any database/main/models/service import sees the isolated URL
pytest_collection_finish
  -> assert an imported engine points to the owned UUID path
  -> assert the development DB fingerprint is still unchanged
session teardown
  -> dispose the existing production engine object
  -> delete only owned SQLite artifacts
  -> assert the development DB fingerprint is still unchanged
```

`test_api.py` retains its existing test credentials and application import but
no longer owns database setup or cleanup. No application `Settings`, database,
model, service, or `main` import precedes activation in conftest.

## 5. Isolation architecture

`backend/test_support/database_isolation.py` is a small test/diagnostic-only
boundary. It generates or safely claims an absent `.db` path, records an opaque
ownership token, sets the SQLite URL before application imports, optionally
sets `APP_ENV=test` (enabled here), fingerprints database files without opening
SQLite, and removes only the owned database plus its exact `-wal`/`-shm`
sidecars.

It deliberately does not import or wrap SQLAlchemy, create an engine, define a
second `Base`/`SessionLocal`, load models, replace pytest, or alter production
configuration. The application continues to have exactly one database
implementation: `backend/database.py`.

## 6. New contracts

`tests/test_database_isolation_contracts.py` adds 16 collected regression
cases:

- Contract A proves the pytest engine path equals the central UUID database and
  not `backend/girlfriend_menu.db`.
- Contract B compares the current development DB file/WAL/SHM fingerprint with
  the pre-collection snapshot.
- An explicit safe-import subprocess sets an isolated SQLite URL first and
  proves a fresh `database.engine` binds exactly there.
- A standalone bootstrap subprocess overwrites an ambient URL before import,
  connects through the existing engine, then deletes the owned database.
- A late-bootstrap subprocess imports `database` first and must fail loudly
  with `DatabaseIsolationOrderError`; it does not connect to or change the
  development DB.
- Cleanup rejects arbitrary path values, protected roots, production-style
  URLs, the development database, and pre-existing files.
- Cleanup removes an owned explicit database and only its exact SQLite
  sidecars.

The focused isolation/settings/observability gate passed with **55 tests**.
The full suite increased from 149 to **165 passed**, with the same 11 existing
Python 3.12 SQLite datetime-adapter warnings.

## 7. Subprocess regression

The safe subprocess received a unique `tmp_path/safe-import.db` URL before
`import database`. `engine.url.database` resolved to that exact path. Merely
constructing the engine did not create the file.

The shared-bootstrap subprocess started with a misleading ambient SQLite URL,
created a helper-owned UUID path, activated it before importing `database`,
opened one real SQLAlchemy connection, disposed the engine, and reported that
the file no longer existed after cleanup.

The unsafe subprocess deliberately bound `database` first. Calling the
bootstrap afterward returned `DatabaseIsolationOrderError` instead of silently
pretending isolation succeeded. Before/after read-only fingerprints proved the
default development DB did not change.

## 8. Diagnostic bootstrap

`backend/test_support/README.md` defines the future rule:

1. Prefer a pytest test for every DB-touching PoC so existing fixtures,
   cleanup, assertions, and CI apply automatically.
2. If a bounded standalone diagnostic is necessary, run from `backend/`, call
   `create_isolated_database(...).activate()` first, and only then import
   `database`, `main`, `models`, or services.
3. Dispose `database.engine` before calling the ownership handle's cleanup.
4. Do not scatter new `os.environ["DATABASE_URL"]` assignments among temporary
   scripts.
5. Production, backup, migration, and acceptance tools must not use the
   test-only bootstrap.

This location was selected instead of `tests/support` so a controlled
standalone diagnostic launched from `backend/` can import one stable helper
without importing pytest or treating the test directory as an application
package.

## 9. Safe cleanup rules

Cleanup accepts an `IsolatedDatabase` ownership handle, not a string or
arbitrary path. The handle is valid only while its token maps to the exact
absent path claimed by the helper. A pre-existing file cannot be relabelled as
test-owned.

Validation refuses `backend/`, the project root, `.`, `..`, the current working
directory, the user home, the system temp root itself, production-style URLs,
the default development database, files directly inside protected roots, and
non-`.db` paths. UUID files under a dedicated repository temp child or
pytest's `tmp_path` are accepted. Cleanup never removes a directory or scans a
glob; it checks and deletes only the exact database, `-wal`, and `-shm` files.

After focused tests, the full suite, Alembic, and route counting, the number of
remaining `backend/.test-tmp/loveos-test-*` artifacts was **0**. Pre-existing
ignored historical temp directories were not deleted or modified.

## 10. Scripts classification

| Script | Classification | Database behavior / R2C action |
|---|---|---|
| `backup_database.py` | PRODUCTION TOOL | Reads explicit/environment DB or the existing local fallback and creates a real backup; unchanged |
| `backup_production_api.py` | PRODUCTION TOOL | Reads deployed HTTP resources; no local DB import; unchanged |
| `production_ws_acceptance.py` | PRODUCTION TOOL | Explicit remote synthetic acceptance flow; no local DB import and not executed; unchanged |
| `verify_backup.py` | DIAGNOSTIC TOOL | SQLite restore uses `TemporaryDirectory`; PostgreSQL target must contain `restore_verify`; unchanged |
| `check_release_config.py` | DIAGNOSTIC TOOL | Static release-file check; no DB access; unchanged |
| `check_secrets.py` | DIAGNOSTIC TOOL | Static Git candidate scan; no DB access; unchanged |
| retained `scripts/` test tools | TEST TOOL | None |

Production tools were not automatically redirected to a test database, and
the backup system was not rewritten.

## 11. Default development DB before/after

The real development SQLite database was never deleted, restored, opened by a
test connection, or altered to test the guardrail. Read-only file metadata and
SHA-256 were recorded immediately before work and again after the complete
gate:

| Property | Before | After |
|---|---:|---:|
| Exists | true | true |
| Size | 1,224,704 bytes | 1,224,704 bytes |
| Last write UTC | `2026-08-14T03:31:45.1154363Z` | `2026-08-14T03:31:45.1154363Z` |
| Last write ticks | `639222751051154363` | `639222751051154363` |
| SHA-256 | `0A810C25967A89187DE595FEFB1B3843C4475E9AE4F258C0E3578C87195F4F8B` | same |

Because size, mtime, full content hash, and absent WAL/SHM sidecars were
identical, no additional SQLite query or marker-count read was necessary. The
pytest session independently enforces the same before/after snapshot.

## 12. Dependencies

R2C added **0 production dependencies** and **0 development dependencies**.
It uses the standard library, existing pytest fixtures/subprocess support, the
existing environment model, and the existing SQLAlchemy database boundary.

The R2B1 direct dependencies remain exactly
`opentelemetry-api==1.44.0` and `opentelemetry-sdk==1.44.0`. No FastAPI or
SQLAlchemy instrumentation, OTLP, Collector, Metrics, Docker, testcontainers,
or custom pytest plugin was introduced. Final `pip check` reported no broken
requirements.

## 13. Complete Gate

The gate was rerun from the beginning after the last implementation edit:

| Gate | Final result |
|---|---|
| `pip check` | PASS - no broken requirements |
| `python -m ruff check . ../scripts` | PASS |
| `lint-imports` | PASS - 2 kept, 0 broken; 101 files / 294 dependencies analyzed |
| `python -m pytest -q` | PASS - 165 passed, 11 warnings in 60.63s |
| `python -m compileall -q .` | PASS |
| isolated empty SQLite `alembic upgrade head` | PASS - `20260812_12 (head)`; helper-owned DB cleaned |
| `npm run build:weapp` | PASS - Taro 4.2.0 |
| `npm run test:ci` | PASS |
| `npm run test:games` | PASS |
| `npm run test:landlord` | PASS |
| `git diff --check` | PASS - existing line-ending conversion warnings only |

The rebuilt mini-program distribution remains **137 files / 803,033 bytes**.

## 14. HTTP/WS/Alembic

Route counts were collected in a helper-isolated process and its database
target was cleaned afterward:

- FastAPI `APIRoute` objects: **89**.
- Established public HTTP baseline excluding diagnostic health: **88**.
- OpenAPI schema operations: **87**.
- WebSocket routes: **3**:
  - `/ws/admin/orders`;
  - `/ws/game/{room_code}`;
  - `/ws/games/dice/{room_code}`.
- Alembic head: **`20260812_12`**.
- Migration files: **12**.
- Migration-count change in R2C: **0**.
- Schema change in R2C: **0**.

R2B1 retains only its bounded manual spans:
`game.websocket.join`, `game.lease.acquire`, `game.snapshot.load`,
`game.settlement` and its five stage spans, plus `notification.persist`.
R2C made no telemetry source or dependency change.

## 15. Rollback

Rollback must be selective because the worktree contains protected earlier
Phase 3.0 changes.

1. Remove only `backend/test_support`, the R2C database-isolation contract test,
   this review, and the R2C additions in `tests/conftest.py`.
2. Restore only the removed fixed `TEST_DB` setup/cleanup block in
   `tests/test_api.py`; otherwise tests would no longer have any database
   isolation after removing the new conftest bootstrap.
3. Rerun the complete gate and explicitly verify the development DB again.

Do not reset or checkout the whole worktree. No migration, database-content,
dependency, API, WebSocket, or telemetry rollback is required.

## 16. Phase 3.1-A readiness checklist

R2C does not create a staging deployment or collect hosted traces. A separately
approved **Phase 3.1-A - Hosted Latency Evidence Collection** should not start
until all of these are ready:

- an isolated Render-like service and isolated/staging Neon database, with no
  real couple data and no production database credentials;
- synthetic customer identities, rooms, orders, settlements, and an explicit
  data teardown owner;
- a separately reviewed trace export/collection method, because R2C adds no
  OTLP exporter or collector and production console tracing remains blocked;
- a bounded sampling/run-count plan for representative slow and normal joins
  and settlements;
- collection of the existing join, lease, snapshot, settlement-stage, and
  notification spans without adding automatic instrumentation;
- a privacy scan for identity, room, credential, URL, payload, SQL, and
  sentinel leakage before evidence is retained;
- timestamps for First State and Settlement Visibility plus Render/Neon
  environment metadata sufficient to interpret each trace;
- an evidence review before any performance optimization is proposed.

All R2C gates are green, pytest proves its own isolation, late diagnostic
activation fails loudly, the development fallback remains unchanged, and the
real development database stayed byte-for-byte unchanged.

**PASS — PHASE 3.0 INFRASTRUCTURE BASELINE COMPLETE**
