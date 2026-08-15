# Phase 3.0-R2A — Configuration & Architecture Guardrails Review

> Final status: **PASS — R2A COMPLETE — READY FOR OBSERVABILITY REVIEW**
>
> Scope completed: `pydantic-settings` compatibility layer, A1 runtime compatibility repair, and dev-only `import-linter` guardrails. OpenTelemetry was not implemented.

## 1. Precheck

All existing B0, B1, Precheck, and Round 1 workspace changes were identified and preserved. No broad reset, checkout, clean, commit, push, merge, rebase, or WeChat upload was performed.

| Check | Result |
|---|---|
| `git status --short` / `git diff` | Existing work identified and preserved |
| Initial `git diff --check` | PASS; line-ending conversion warnings only |
| Initial backend Ruff | PASS |
| Initial backend pytest | PASS — 110 passed, 11 warnings |
| Initial mini-program `test:ci` | PASS |

The shell did not expose a bare `python` command, so all backend commands used the repository's existing `.venv` Python 3.12.13. This was an invocation adaptation, not a source or dependency change.

## 2. Round 1 document correction

`docs/optimization/PHASE_3_0_OPEN_SOURCE_AUDIT.md` was corrected narrowly before implementation:

- removed the inaccurate statement that no dependency update bot exists;
- changed Dependabot from `ADOPT_LATER` to `KEEP_CURRENT`, with configuration tuning as possible later work;
- removed the proposal to introduce Dependabot as a new tool;
- did not rewrite unrelated Round 1 conclusions.

## 3. Dependabot actual state

`.github/dependabot.yml` exists, is tracked, and covers:

- npm in `/miniprogram`, weekly, with Taro and routine npm groups;
- pip in `/backend`, weekly, with a routine Python group;
- GitHub Actions, monthly, grouped.

No Dependabot schedule, grouping, or update policy was changed in R2A.

## 4. pydantic-settings final version

Production dependency added:

```text
pydantic-settings==2.14.2
```

The current release was selected after resolver verification against the existing environment. It adds one direct production dependency and did not upgrade the current frameworks. Project and release metadata were checked against the official [pydantic-settings PyPI page](https://pypi.org/project/pydantic-settings/).

## 5. Why it is compatible with current Pydantic

| Package | Final version | Changed by R2A |
|---|---:|---|
| Pydantic | 2.11.4 | No |
| pydantic-settings | 2.14.2 | Added |
| FastAPI | 0.115.12 | No |
| SQLAlchemy | 2.0.40 | No |

`pydantic-settings` accepts Pydantic `>=2.7.0`; the existing 2.11.4 satisfies that range. The resolver installed no Pydantic, FastAPI, or SQLAlchemy upgrade, and `pip check` returned `No broken requirements found`.

## 6. Settings architecture

`backend/core/settings.py` is the only application environment-source boundary:

- one `Settings(BaseSettings)` schema with `SettingsConfigDict`;
- unchanged environment aliases, defaults, normalization, clamps, and required-on-use checks;
- absolute `backend/.env`, independent of current working directory;
- `SecretStr` for credentials, invite codes, database URLs, S3 keys, and Redis URLs;
- `get_settings()` for cached startup-stable configuration;
- `load_settings()` for fresh runtime/required-on-use compatibility snapshots;
- `reset_settings_cache()` for test isolation and explicit startup configuration reloads.

No business or infrastructure module creates `Settings()` or reads `os.getenv` directly. There is no module-level collection of competing Settings singletons.

## 7. Settings Compatibility Repair

### Original blocker

The first Package A implementation sent every consumer through cached `get_settings()`. Two unchanged legacy tests then failed:

1. `ALLOW_LEGACY_CUSTOMER_HEADER` changed from true to false in one process, but the next request retained true (expected 401, received 200).
2. `UPLOAD_PROVIDER` changed from local to S3 in one process, but the next upload retained local (expected 503, received 200).

### Root cause

Centralizing names and parsing was correct, but freezing every variable into one process-wide snapshot changed old call-time `getenv` semantics. A singleton objective had been applied more broadly than the compatibility contract allowed.

### Repair

The schema remained centralized, but its lifecycle access was split:

```text
startup infrastructure -> get_settings() -> cached Settings snapshot
request/on-use boundary -> load_settings() -> fresh Settings snapshot
```

The two old tests were not changed, skipped, weakened, or taught to call `reset_settings_cache()`. They now pass because normal runtime access again observes values that were historically visible on the next call.

### Performance impact

Fresh Settings construction is limited to authentication/session creation, legacy-header checks, storage selection/readiness/client construction, and the frontend-origin helper. Database queries, WebSocket messages, game actions, lease heartbeats, Redis-backed state access, and initialized engine/client objects do not construct Settings repeatedly.

Focused result: **32 passed** — the two unchanged blocker tests plus 30 Settings compatibility cases.

## 8. Environment-variable migration and lifecycle matrix

| ENV | Legacy read timing | Final boundary | Lifecycle | Runtime observable | Cache allowed |
|---|---|---|---|---|---|
| `DATABASE_URL` | database module/engine initialization | `database.configured_database_url()` | startup | No after engine creation | Yes |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE` | non-SQLite engine initialization | `database_engine_options()` | startup | No after pool creation | Yes |
| `REDIS_URL` | cache/rate-limiter construction | `StateCache` / limiter factory | startup | No after adapter construction | Yes |
| `GAME_ROOM_LEASE_SECONDS` | lease module initialization | lease accessor backed by cached Settings | startup/high-frequency | No implicit reload | Yes |
| `GAME_INSTANCE_ID`, `RENDER_INSTANCE_ID` | lease module initialization | resolved instance accessor | startup | No | Yes |
| `APP_ENV` | lifespan and storage calls | cached in lifespan; fresh in storage boundary | mixed by boundary | Yes for storage readiness | Mixed |
| `ALLOW_LEGACY_CUSTOMER_HEADER` | each request dependency call | `load_settings()` | request | Yes | No |
| `ADMIN_PASSWORD`, `ADMIN_INVITE_CODE` | each admin login check | fresh dependency accessor | required-on-use | Yes | No |
| `ADMIN_SECRET`, `ADMIN_TOKEN_VERSION` | token issue/verification | one fresh auth snapshot per operation | required-on-use | Yes | No |
| `CUSTOMER_INVITE_CODE` | session/claim/recovery validation | fresh customer accessor | required-on-use | Yes | No |
| `CUSTOMER_SESSION_TTL_DAYS` | session expiry creation | fresh TTL accessor | required-on-use | Yes | No |
| `UPLOAD_PROVIDER` | provider/readiness/upload call | fresh storage snapshot | request/on-use | Yes | No |
| `S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET`, keys, public URL | S3 construction/readiness | one fresh storage snapshot per boundary call | required-on-use | Yes | No |
| `FRONTEND_URL` | helper invocation; middleware uses it at app assembly | fresh helper accessor | call-time compatibility | Yes when helper is called | No |

## 9. Failure-timing compatibility matrix

| Configuration | Required/fails when | Preserved behavior |
|---|---|---|
| `ADMIN_SECRET` | token issue or verification | Application startup remains valid without it; short/missing value fails only on use |
| Admin password/invite | matching login credential is requested | Missing value produces the same 503 boundary response |
| Customer invite | session/claim/recovery verifies it | Missing value remains 503; mismatch remains 401 |
| S3 credentials | readiness or S3 provider construction | Readiness reports missing fields; construction raises only when selected |
| Database pool strings | non-SQLite engine options are built | Same integer conversion timing and lower bounds |
| Customer TTL | a session expiry is created | Invalid value falls back to 90; result remains clamped to 1..365 |
| Game lease | lease duration is initialized/used | Same integer failure semantics and minimum 15 seconds |
| Legacy header/provider runtime mutation | next relevant call/request | New process environment state is visible without a cache reset |

## 10. Secret redaction verification

Both cached and fresh loader tests verified that Settings `repr` and `str`, plus required-on-use failures, do not reveal sentinels representing:

- admin passwords, signing secrets, and invite codes;
- customer invite codes;
- database URL credentials;
- S3 access/secret keys;
- Redis URL credentials.

The customer token is not a Settings field. No secret value was added to logging or exception text.

## 11. Settings cache and test isolation

`get_settings()` has one `@lru_cache(maxsize=1)`. `reset_settings_cache()` clears only this startup snapshot and is used by an autouse fixture before and after tests.

Contracts prove both paths:

- a startup database setting remains stable after an environment change until explicit reset;
- `load_settings()` sees the updated environment immediately;
- cached and fresh paths use the same absolute `.env` location;
- no runtime module directly constructs `Settings`;
- normal runtime behavior does not depend on reset calls.

## 12. import-linter version

Development dependency added:

```text
import-linter==2.13
```

The official [Import Linter PyPI page](https://pypi.org/project/import-linter/) identifies 2.13 as the current stable release and supports Python 3.12. Its installed transitive graph engine is `grimp==3.15`. Neither package is present in `backend/requirements.txt`.

## 13. Contracts

`backend/.importlinter` contains exactly two effective forbidden contracts, with no ignores:

1. `repositories` must not depend on `api`, `services`, or `notification_service`.
2. `games.*.rule`, `games.*.engine`, and `games.*.ai` must not depend on `fastapi`, `sqlalchemy`, `database`, or `models`.

Result:

```text
Analyzed 101 files, 292 dependencies.
Contracts: 2 kept, 0 broken.
```

## 14. Why these contracts are current green boundaries

Repository modules currently perform persistence access without importing request routing or service orchestration. Pure game rule, engine, and AI modules currently operate on game-domain structures without web or persistence frameworks.

The second contract intentionally excludes `games/core/room.py`, `player.py`, `state.py`, and `service.py`; they are application/persistence modules, not pure rule modules. No models, schemas, manager, CRUD, directories, or business imports were moved to satisfy the linter.

## 15. CI changes

Backend CI retains all migration, Ruff, compileall, and pytest steps. One command was inserted after Ruff and before compileall:

```yaml
- run: python -m ruff check . ../scripts
- run: lint-imports
- run: python -m compileall -q .
- run: python -m pytest -q
```

No other CI behavior or Dependabot policy changed.

## 16. New production dependency count

**1 direct dependency**: `pydantic-settings==2.14.2`.

This matches the R2A production dependency budget. No OpenTelemetry package was added.

## 17. New development dependency count

**1 direct dependency**: `import-linter==2.13`.

Its transitive implementation dependency is `grimp==3.15`. This matches the R2A development dependency budget.

## 18. HTTP operations

**88 public baseline operations**, unchanged.

FastAPI currently registers 89 `APIRoute` objects. The established B1 contract count excludes the diagnostic `GET /api/health` route (`include_in_schema=False`), yielding 88. OpenAPI itself contains 87 schema operations because both health and readiness are schema-hidden. No path, method, request, response, or status code changed in R2A.

No API was changed, so an OpenAPI client regeneration step was not applicable.

## 19. WebSocket paths

**3 paths**, unchanged:

- `/ws/admin/orders`
- `/ws/game/{room_code}`
- `/ws/games/dice/{room_code}`

No payload, close code, reconnect behavior, or message handling changed.

## 20. Alembic head

- Head: **`20260812_12`**
- Migration files: **12**
- Migration-count change: **0**

An isolated empty SQLite database upgraded through all 12 revisions and reported `20260812_12 (head)`.

## 21. Complete Gate

| Gate | Final result |
|---|---|
| `python -m ruff check . ../scripts` | PASS |
| `lint-imports` | PASS — 2 kept, 0 broken |
| `python -m pytest -q` | PASS — 140 passed, 11 warnings |
| `python -m compileall -q .` | PASS |
| isolated `alembic upgrade head` | PASS — `20260812_12` |
| `npm run build:weapp` | PASS — Taro 4.2.0 |
| `npm run test:ci` | PASS |
| `npm run test:games` | PASS |
| `npm run test:landlord` | PASS |
| `git diff --check` | PASS; line-ending conversion warnings only |

Build facts:

| Fact | Value |
|---|---:|
| Git SHA | `845fa51a649a3a2e4bec1200099618128a5b0b3d` |
| Node / npm used locally | `v24.17.0` / `11.13.0` |
| Taro | `4.2.0` |
| dist files | 137 |
| dist bytes | 803,033 bytes (about 0.766 MiB) |

The 11 pytest warnings remain the existing Python 3.12 SQLite datetime-adapter deprecation warnings.

## 22. Rollback plan

Rollback must be selective because the worktree also contains user-owned B0/B1/Precheck/Round 1 changes:

1. remove only `backend/.importlinter`, `backend/core/settings.py`, `backend/tests/conftest.py`, and `backend/tests/test_settings_contracts.py`;
2. selectively revert the R2A configuration-consumer edits in `database.py`, `storage.py`, `main.py`, `auth.py`, `customer_service.py`, `api/dependencies.py`, and the three `core` adapters;
3. remove only `pydantic-settings==2.14.2` from production requirements;
4. remove only `import-linter==2.13` from development requirements and the `lint-imports` CI line;
5. optionally uninstall the two direct packages and their now-unused transitive dependencies from the repository `.venv`;
6. retain the Round 1 Dependabot fact correction and pre-existing B0/B1 files unless separately requested;
7. rerun the original minimal baseline.

Do not use broad reset, checkout, or clean commands for rollback.

## 23. Remaining getenv count

| Scope | Direct environment reads remaining |
|---|---:|
| Business/infrastructure runtime modules | 0 direct `os.getenv` / `os.environ` reads |
| Central settings boundary | pydantic-settings owns environment loading; `core/settings.py` contains no scattered business reads |
| Operational scripts | 6 reads across database backup, production API backup, and production WebSocket acceptance scripts |
| Tests | 7 explicit environment assignments in `test_api.py` |

The runtime result means application modules no longer read the environment themselves; it does not mean the process is restricted to one startup snapshot.

## 24. Next-step recommendation

R2A is complete. The repository may proceed to a separately reviewed Observability phase, but that phase should re-evaluate the production dependency budget before choosing OpenTelemetry packages. Do not infer observability implementation from this review.

R2A added no OpenTelemetry dependency, instrumentation, span, exporter, or runtime tracing code.

## Final status

**PASS — R2A COMPLETE — READY FOR OBSERVABILITY REVIEW**
