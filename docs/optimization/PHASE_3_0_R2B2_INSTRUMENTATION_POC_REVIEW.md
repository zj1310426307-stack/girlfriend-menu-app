# Phase 3.0-R2B2 Framework & Database Instrumentation Compatibility PoC Review

Date: 2026-08-14
Repository HEAD inspected: `845fa51a649a3a2e4bec1200099618128a5b0b3d`
Scope: compatibility PoC and adoption decision only; no production deployment

## 1. Precheck

The R2B2 task, R2B1 review, telemetry boundary, Settings lifecycle, application
lifespan, database engine construction, and existing observability tests were
read before the PoC. Opening `git status --short`, `git diff`, and
`git diff --check` confirmed the protected B0/B1/R2A/R2B1 dirty worktree. The
opening diff check passed with only existing LF-to-CRLF conversion warnings.

No reset, checkout, clean, commit, push, merge, rebase, Render configuration,
external telemetry delivery, or WeChat upload was performed. No API, WebSocket,
schema, game, Customer Session, or mini-program product behavior was changed.
Because there was no API change, OpenAPI/client regeneration was not applicable.

PoC isolation note: the first temporary SQLAlchemy run imported `database`
before the test harness established its isolated URL and therefore wrote only
synthetic `gf_r2b2_`/`*SENTINEL*` rows to the repository's default local SQLite
database. The import order was corrected immediately. A validated, marker-only
cleanup removed the 552 synthetic rows and their declared foreign-key children;
a second inspection found zero marker rows. No database file or unrelated row
was removed. All decision evidence below was recollected against
`backend/tests/test_girlfriend_menu.db`, and the normal pytest fixture later
removed that test database.

## 2. Official package status

Official metadata and documentation were rechecked on 2026-08-14:

- [FastAPI instrumentation documentation](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html)
  documents `excluded_urls`, header-capture options, `exclude_spans`, and the
  optional tracer/meter providers.
- [SQLAlchemy instrumentation documentation](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/sqlalchemy/sqlalchemy.html)
  documents existing-engine instrumentation and SQLCommenter flags.
- [OpenTelemetry Python Contrib 0.65b0 release](https://github.com/open-telemetry/opentelemetry-python-contrib/releases/tag/v0.65b0)
  is the `1.44.0/0.65b0` release family, published 2026-07-16.
- [FastAPI package metadata](https://pypi.org/project/opentelemetry-instrumentation-fastapi/0.65b0/)
  identifies `0.65b0` as a pre-release, Development Status Beta, Apache-2.0,
  and Python `>=3.10` compatible.
- [OpenTelemetry Python Contrib repository](https://github.com/open-telemetry/opentelemetry-python-contrib)
  states that its instrumentation libraries are currently Beta and generally
  should not be treated as production-stable.

The resolver and installed package metadata confirmed both exact candidates:

- `opentelemetry-instrumentation-fastapi==0.65b0`;
- `opentelemetry-instrumentation-sqlalchemy==0.65b0`.

They match the installed API/SDK `1.44.0` and semantic conventions `0.65b0`.

## 3. Beta stability note

The core OpenTelemetry API and SDK are stable `1.44.0`; the two Contrib
instrumentation packages are **not equivalently stable**. Their `0.65b0`
versions are Beta/pre-release packages with evolving semantic-convention and
middleware behavior.

This PoC therefore treats successful installation as only compatibility
evidence. It is not production approval and does not override LoveOS privacy,
noise, dependency, or performance gates.

## 4. Dependency resolver

The first sandboxed resolver attempt could not access PyPI. The approved
network retry performed a successful joint dry run with both candidates pinned
to `0.65b0`.

The resolver kept these versions unchanged:

| Package | Version |
|---|---:|
| `opentelemetry-api` | `1.44.0` |
| `opentelemetry-sdk` | `1.44.0` |
| `opentelemetry-semantic-conventions` | `0.65b0` |
| FastAPI | `0.115.12` |
| Pydantic | `2.11.4` |
| SQLAlchemy | `2.0.40` |
| `pydantic-settings` | `2.14.2` |
| `import-linter` | `2.13` |

The candidates installed successfully in the local virtual environment for the
PoC, and `pip check` passed. After the decisions were made, both candidates and
their newly introduced transitives were uninstalled. A second `pip check`
passed in the restored R2B1 environment.

## 5. Transitive dependency graph

The exact resolver result was:

```text
opentelemetry-instrumentation-fastapi==0.65b0
├── opentelemetry-api~=1.12                 (already 1.44.0)
├── opentelemetry-semantic-conventions==0.65b0 (already present)
├── opentelemetry-instrumentation==0.65b0
├── opentelemetry-instrumentation-asgi==0.65b0
│   ├── asgiref~=3.0                       (resolved 3.12.1)
│   └── opentelemetry-util-http==0.65b0
└── opentelemetry-util-http==0.65b0

opentelemetry-instrumentation-sqlalchemy==0.65b0
├── opentelemetry-api~=1.12                 (already 1.44.0)
├── opentelemetry-semantic-conventions==0.65b0 (already present)
├── opentelemetry-instrumentation==0.65b0
├── packaging>=21.0                         (already 26.3)
└── wrapt>=1.11.2                           (resolved 2.3.0)
```

`opentelemetry-instrumentation-dbapi` was not required by this resolver. No
release-family mixing or core framework change occurred.

## 6. FastAPI PoC

The official `FastAPIInstrumentor.instrument_app()` was tested against the real
LoveOS `FastAPI` app with the R2B1 tracer provider and in-memory exporter. The
PoC configuration used:

- official `excluded_urls` for `/api/health`, `/api/ready`, and all three
  WebSocket path families;
- `exclude_spans=["receive", "send"]`;
- no request/response header capture configuration;
- no Metrics SDK, Metrics exporter, OTLP exporter, or collector.

A plain `GET /api/dishes` produced exactly one `GET /api/dishes` SERVER span
and zero ASGI internal spans. Its standard attributes included method, route,
status, scheme/host, network basics, and URL. The response payload and status
remained unchanged.

The instrumentation always asks the Metrics API for HTTP instruments, but the
runtime meter provider remained `_ProxyMeterProvider`; without a configured
Metrics SDK/exporter, no effective metric pipeline or metric export existed.
This is still a future scope risk if an SDK meter provider is introduced.

## 7. WebSocket exclusion proof

The official exclusions were exercised with a real `/ws/game/{room_code}` join.

| Category | Manual only | FastAPI candidate |
|---|---:|---:|
| manual business spans | 3 | 3 |
| HTTP/WS automatic server spans | 0 | 0 |
| ASGI receive spans | 0 | 0 |
| ASGI send spans | 0 | 0 |

The remaining three spans were exactly:

- `game.websocket.join`;
- `game.lease.acquire`;
- `game.snapshot.load`.

The first WebSocket state envelope retained the exact existing keys `type`,
`game`, `room_code`, and `data`. No long-lived `/ws/...` server span and no
per-message receive/send span was exported. The positive exclusion result is
real, but it does not cure the HTTP query privacy failure in section 9.

## 8. Health/ready exclusion

With FastAPI instrumentation alone, `GET /api/health` and `GET /api/ready`
produced zero automatic HTTP or ASGI spans and returned their existing 200
payloads. The exclusion regexes did not change readiness behavior.

With SQLAlchemy instrumentation enabled, readiness still produced two DB spans
(`connect` and `SELECT 1`) even though its HTTP span was excluded. That is an
additional source of probe noise for the database candidate.

## 9. HTTP privacy scan

Request headers included synthetic `Authorization` and `Cookie` values. No
captured-header attributes were present; request/response bodies were also not
recorded.

The critical query test failed:

```text
GET /api/dishes?invite_code=INVITE_SENTINEL
```

The exported server span contained:

```text
http.url = http://testserver/api/dishes?invite_code=INVITE_SENTINEL
```

The sentinel was therefore present in exporter-visible attributes. The
instrumentor's public options do not provide a supported switch to omit the raw
query component while retaining the server span. `excluded_urls` receives a URL
constructed from scheme/host/path before the ASGI query string is appended, so
it cannot reliably exclude arbitrary query-bearing requests based on the query
content. Excluding every potentially affected route would also eliminate the
required HTTP value and cannot cover ignored query parameters accepted by any
FastAPI route.

No private-API mutation or custom SpanProcessor scrubber was introduced.

## 10. SQLAlchemy PoC

The official instrumentor was attached to the existing engine exactly as
required:

```python
SQLAlchemyInstrumentor().instrument(
    engine=engine,
    tracer_provider=provider,
    enable_commenter=False,
    enable_attribute_commenter=False,
)
```

The engine, `SessionLocal`, repositories, transaction order, commit/rollback
behavior, and schema were not rebuilt or modified. No SQL comment or
`traceparent` was injected into executed queries.

The candidate produced usable parent/child DB timing, but it failed the
mandatory SQL-text privacy rule and the span-noise budget.

## 11. SQL text attribute inspection

`enable_commenter=False` disables SQLCommenter only; it does **not** disable SQL
text attributes. Every recorded statement span called the package's standard
DB attribute path and exported `db.statement`, for example:

```text
SELECT game_rooms... FROM game_rooms WHERE game_rooms.room_code = ?
UPDATE game_rooms SET owner_instance_id=?, lease_expires_at=? ...
INSERT INTO game_records (...) VALUES (?, ?, ...)
SELECT customer_sessions... FROM customer_sessions WHERE ...
```

The span names also contained the SQLite database filename/path, for example:

```text
SELECT D:/my-project/girlfriend-menu-app/backend/tests/test_girlfriend_menu.db
```

The public `SQLAlchemyInstrumentor.instrument()` configuration has no stable,
documented option to suppress `db.statement`/`db.query.text` while retaining DB
spans. `enable_attribute_commenter=False` only controls whether SQL comments are
copied into the already-present query attribute. LoveOS explicitly prohibits
SQL statement text in telemetry, so this is a hard privacy failure.

## 12. SQL parameter inspection

The positive result is that parameter values were not exported by this
configuration:

- no `db.statement.parameters` attribute was present;
- bind parameters appeared only as `?` placeholders;
- `DATABASE_PASSWORD_SENTINEL`, `CUSTOMER_TOKEN_SENTINEL`,
  `ROOM_CODE_SENTINEL`, `USER_SENTINEL`, and `INVITE_SENTINEL` had zero matches
  across DB span names, attributes, and events.

This does not override the stricter `NO SQL STATEMENT IN TELEMETRY` rule. Query
structure, table/column names, and the database path were still exported.

## 13. DB span hierarchy

The instrumentor did demonstrate technical context value. DB spans appeared
under the existing manual spans, including:

| Manual ancestor | Observed DB descendants |
|---|---:|
| `game.lease.acquire` | 9 |
| `game.snapshot.load` | 2 |
| `game.websocket.join` orchestration remainder | 35–36 |
| `game.settlement.persist` | 20 |
| `game.settlement.reward` | 46 |
| `game.settlement.replay` | 4 |
| `game.settlement.notification` | 16 |
| `notification.persist` | 8 |
| `game.settlement.finalize` | 4 |

This proves standard OTel context propagation works with the R2B1 provider. It
also demonstrates why unrestricted engine-wide instrumentation is too broad for
the current runtime.

## 14. Sentinel privacy scan

Synthetic order, customer-session, game snapshot/join, and settlement flows
carried all required sentinels. Exporter-visible span names, resources,
attributes, and events were scanned.

| Candidate | Parameter/body/header sentinel result | Structural privacy result |
|---|---|---|
| FastAPI | headers/bodies: 0 leaks | **FAIL** — `INVITE_SENTINEL` in `http.url` query |
| SQLAlchemy | parameter sentinels: 0 leaks | **FAIL** — SQL text and DB path exported |

The FastAPI finding is a literal sentinel leak. The SQLAlchemy finding fails an
explicit policy even without literal parameter leakage.

## 15. Span-count comparison

Counts varied by one DB span depending on pool state; the material conclusion
did not change.

| Flow | Manual | HTTP auto | DB auto | ASGI internal | Total |
|---|---:|---:|---:|---:|---:|
| WebSocket join, manual only | 3 | 0 | 0 | 0 | 3 |
| WebSocket join + FastAPI candidate | 3 | 0 | 0 | 0 | 3 |
| WebSocket join + SQLAlchemy candidate | 3 | 0 | 53–54 | 0 | 56–57 |
| Settlement, manual only | 8 | 0 | 0 | 0 | 8 |
| Settlement + FastAPI candidate | 8 | 0 | 0 | 0 | 8 |
| Settlement + SQLAlchemy candidate | 8 | 0 | 98 | 0 | 106 |
| Combined representative flow, manual only | 11 | 0 | 0 | 0 | 11 |
| Combined flow + FastAPI | 11 | 1 | 0 | 0 | 12 |
| Combined flow + SQLAlchemy | 11 | 0 | 167 | 0 | 178 |
| Combined flow + both candidates | 11 | 1 | 167 | 0 | 179 |

FastAPI's restricted span volume was acceptable. SQLAlchemy generated dozens
to hundreds of low-level spans for normal flows and failed the noise gate even
before sampling.

## 16. Local overhead observation

These are local Windows/TestClient/SQLite observations only, not production
benchmarks. A stable 20-request `GET /api/dishes` comparison produced:

| Mode | Median | Minimum | Maximum | Spans/request |
|---|---:|---:|---:|---:|
| tracing disabled | 2.458 ms | 2.045 ms | 5.186 ms | 0 |
| manual only | 2.126 ms | 1.815 ms | 3.350 ms | 0 |
| manual + FastAPI | 3.989 ms | 3.284 ms | 55.306 ms | 1 HTTP |
| manual + SQLAlchemy | 3.283 ms | 2.008 ms | 4.290 ms | 2 DB |

A single same-flow HTTP + join + settlement sample measured 211.636 ms
(disabled), 203.303 ms (manual), 216.471 ms (FastAPI), and 188.694 ms
(SQLAlchemy). Repeated composite samples showed substantial SQLite/background
task variance, so no production latency claim is made.

The deterministic evidence is span volume: SQLAlchemy added 167 DB spans to an
11-span representative workflow. The timing samples do not justify accepting
either privacy failure.

## 17. Settings interaction

No Settings fields or lifecycle functions were changed. The PoC instrumented
only after the existing `LOVEOS_TRACING_ENABLED` path had created the R2B1
provider. In the disabled mode, neither candidate was invoked and all flows
exported zero spans.

The final runtime contains no candidate bootstrap, so `get_settings()`,
`load_settings()`, required-on-use secrets, storage selection, legacy customer
headers, and startup timing remain exactly at R2B1 behavior.

## 18. Import-linter

After full PoC cleanup, import-linter analyzed 101 files and 294 dependencies:

- Repositories do not depend on API or service orchestration: **KEPT**.
- Pure game rules do not depend on web or persistence frameworks: **KEPT**.

Result: **2 kept, 0 broken**. No repository, rule, engine, or AI module imports
telemetry or an instrumentation package.

## 19. Final retained dependencies

R2B2 retains **0 candidate direct dependencies** and **0 new transitive
dependencies**. Final runtime requirements remain the R2B1 state:

- `opentelemetry-api==1.44.0`;
- `opentelemetry-sdk==1.44.0`;
- SDK transitive `opentelemetry-semantic-conventions==0.65b0`.

The following PoC packages are absent from requirements and the local virtual
environment:

- `opentelemetry-instrumentation-fastapi`;
- `opentelemetry-instrumentation-sqlalchemy`;
- `opentelemetry-instrumentation-asgi`;
- `opentelemetry-instrumentation`;
- `opentelemetry-util-http`;
- `asgiref`;
- `wrapt`.

`packaging` was pre-existing and remains untouched. Final `pip check`: PASS.

## 20. Full Gate

The complete baseline was rerun after candidate and PoC cleanup.

| Gate | Final result |
|---|---|
| `pip check` | PASS — no broken requirements |
| `python -m ruff check . ../scripts` | PASS |
| `lint-imports` | PASS — 2 kept, 0 broken |
| `python -m pytest -q` | PASS — 149 passed, 11 warnings |
| `python -m compileall -q .` | PASS |
| isolated empty SQLite `alembic upgrade head` | PASS — `20260812_12` |
| `npm run build:weapp` | PASS — Taro 4.2.0 |
| `npm run test:ci` | PASS |
| `npm run test:games` | PASS |
| `npm run test:landlord` | PASS |
| `git diff --check` | PASS — line-ending conversion warnings only |

The 11 warnings remain the existing Python 3.12 SQLite datetime-adapter
deprecation warnings. The normal pytest fixture confirmed the isolated PoC test
database no longer exists after the suite.

## 21. HTTP/WS/Alembic counts

- Registered FastAPI `APIRoute` objects: **89**.
- Established public HTTP baseline excluding diagnostic health: **88**.
- OpenAPI schema operations: **87** (health and readiness remain hidden).
- WebSocket paths: **3**:
  - `/ws/admin/orders`;
  - `/ws/game/{room_code}`;
  - `/ws/games/dice/{room_code}`.
- Alembic head: **`20260812_12`**.
- Migration files: **12**.
- Migration-count change: **0**.
- Schema change: **0**.
- Mini-program dist: **137 files / 803,033 bytes**.

All required public counts match R2B1. No API or WebSocket contract changed.

## 22. Rollback

There is no retained R2B2 runtime implementation to roll back. Candidate
packages, instrumentation bootstrap, and temporary PoC scripts were already
removed. The only retained R2B2 artifact is this decision report.

To roll back the review itself, remove only
`docs/optimization/PHASE_3_0_R2B2_INSTRUMENTATION_POC_REVIEW.md`. Do not reset
or checkout the whole dirty worktree. No database or migration rollback is
needed.

## 23. FastAPI decision

**DEFER**

The official exclusions reliably removed WebSocket, health/readiness, and
receive/send span noise, and plain HTTP span volume was small. Adoption is
nevertheless blocked because arbitrary raw query content is exported in
`http.url`, producing a literal `INVITE_SENTINEL` leak. There is no simple
documented option that removes query text while preserving the server span.

Reconsider only when an official supported query-omission/redaction control can
be demonstrated without private API mutation or a custom scrubbing processor.

## 24. SQLAlchemy decision

**DEFER**

The candidate preserved engine/session/transaction behavior, did not capture
parameter values, and produced useful manual-span descendants. It cannot meet
the current privacy rule because SQL text is always exported and no supported
query-text disable switch exists. It also adds 53–54 DB spans to join and 98 to
settlement, far beyond the accepted noise budget.

Keep the existing manual snapshot, lease, settlement, and notification spans.
Do not build a custom DB tracing framework or private SpanProcessor workaround.

## 25. Recommended next step

Retain the R2B1 manual trace foundation exactly as-is. Do not add either
candidate to production requirements and do not configure OTLP, Collector,
Jaeger, Zipkin, Metrics, or deployment tracing.

Future work should be another explicit review after official Contrib packages
offer supported controls for omitting HTTP query content and SQL statement
text. Until then, use current request logs and bounded business spans to answer
performance questions. Do not start Phase 3.1 automatically.

**BLOCKED — DO NOT ADOPT INSTRUMENTATION**
