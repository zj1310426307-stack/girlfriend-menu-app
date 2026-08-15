# Phase 3.0-R2B1 OpenTelemetry Trace Core Foundation Review

Date: 2026-08-14
Repository HEAD inspected: `845fa51a649a3a2e4bec1200099618128a5b0b3d`
Scope: Trace core foundation only; no R2B2 work

## 1. Precheck

The required audit, R2A review, settings/startup code, state and lease stores,
socket/settlement/notification services, `GameRoomManager`, and WebSocket route
were read before implementation.

The opening worktree was already dirty with protected B0, B1, Round 1, and R2A
work. `git status --short`, `git diff`, and `git diff --check` were inspected.
The opening diff check passed with only Git's existing LF-to-CRLF conversion
warnings. No reset, checkout, clean, commit, push, merge, rebase, or WeChat
upload was performed. Existing unrelated changes were preserved.

R2B1 remained inside the approved boundary:

- Trace only; no Metrics, Logs signal, profiling, or logging replacement.
- No performance optimization, query/cache/lease/retry change, or manager split.
- No HTTP contract, WebSocket protocol, database schema, Customer Session, game
  rule, AI, or mini-program UI change.
- `GameRoomManager` and `game_socket_session_service` remain structurally
  unchanged.

## 2. Official solution and version confirmation

The selected implementation is the CNCF OpenTelemetry Python API and SDK,
using their built-in no-op API behavior, `TracerProvider`, span processors,
`ConsoleSpanExporter`, and test-only `InMemorySpanExporter`.

Official references reviewed on 2026-08-14:

- [OpenTelemetry SDK environment-variable specification](https://opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/)
  defines `OTEL_SDK_DISABLED`, `OTEL_SERVICE_NAME`, and sampler configuration.
- [OpenTelemetry Python trace API](https://opentelemetry-python.readthedocs.io/en/stable/api/trace.html)
  documents the default `NoOpTracerProvider` behavior.
- [OpenTelemetry Python SDK trace export API](https://opentelemetry-python.readthedocs.io/en/stable/sdk/trace.export.html)
  provides `ConsoleSpanExporter` and the standard processor interfaces.
- [PyPI: opentelemetry-sdk 1.44.0](https://pypi.org/project/opentelemetry-sdk/)
  confirms the pinned release and Python `>=3.10` compatibility; the repository
  uses Python 3.12.13.
- The SDK's public in-memory exporter was used for contract tests instead of a
  custom tracing backend. A minimal failing exporter exists only inside the
  test file to exercise exporter-failure isolation.

Final pinned direct versions are `opentelemetry-api==1.44.0` and
`opentelemetry-sdk==1.44.0`; no floating `latest` dependency is used.

## 3. Dependency resolver

A resolver dry run was performed before modifying the lock-style requirements.
The first sandboxed attempt could not reach the package index; the approved
network retry resolved successfully.

Resolution added only:

- direct: `opentelemetry-api==1.44.0`;
- direct: `opentelemetry-sdk==1.44.0`;
- transitive SDK dependency: `opentelemetry-semantic-conventions==0.65b0`;
- existing `typing-extensions` was reused.

The resolver did not request changes to FastAPI, Pydantic, SQLAlchemy,
`pydantic-settings`, or `import-linter`. Final `pip check` reported
`No broken requirements found.`

## 4. Final dependencies

R2B1 adds exactly **2 direct production dependencies** and **0 development
dependencies**, meeting the approved budget.

| Package | Final version | Role |
|---|---:|---|
| `opentelemetry-api` | `1.44.0` | no-op API, context, tracer/span interfaces |
| `opentelemetry-sdk` | `1.44.0` | opt-in provider, processors, console/test exporters |

Existing core packages remain unchanged:

| Package | Version |
|---|---:|
| FastAPI | `0.115.12` |
| Pydantic | `2.11.4` |
| SQLAlchemy | `2.0.40` |
| `pydantic-settings` | `2.14.2` |
| `import-linter` | `2.13` |

No FastAPI/SQLAlchemy instrumentation package, OTLP exporter, distro,
instrumentation meta-package, Jaeger exporter, or Zipkin exporter is present.

## 5. Telemetry architecture

`backend/core/telemetry.py` is the single telemetry boundary. It owns:

- SDK provider construction and shutdown;
- exporter construction;
- tracer access and current-context span creation;
- span-name and attribute allow-lists;
- safe attribute normalization;
- telemetry failure degradation.

Business orchestration modules call only `trace_span()` and
`set_span_attribute()`. They do not construct providers/exporters or parse OTel
environment variables. Repositories and pure game rules/engines/AI do not
import OpenTelemetry.

The provider is initialized from the FastAPI lifespan after explicit opt-in and
shut down after the existing background-task cancellation path. No global
collector, network endpoint, or credential is required.

## 6. Default no-op design

The application-level switch `LOVEOS_TRACING_ENABLED` defaults to `false`.
Without explicit opt-in, `configure_tracing()` does not construct a
`TracerProvider`, span processor, or exporter. Manual hooks use the official
`NoOpTracerProvider` tracer, produce no console output, require no endpoint or
network, and do not alter startup.

The extra application switch is necessary because the standard
`OTEL_SDK_DISABLED` default is `false`: that standard variable is a kill switch,
but its absence does not express this repository's stricter requirement to
avoid initializing the SDK by default. When explicitly set to `true`,
`OTEL_SDK_DISABLED` overrides the LoveOS opt-in.

No `.env` or deployment configuration was added, so existing users and Render
startup remain unchanged.

## 7. Console development mode

Console export requires both:

- `LOVEOS_TRACING_ENABLED=true`;
- `LOVEOS_TRACING_CONSOLE=true`.

It uses the SDK's built-in `ConsoleSpanExporter`, adds no exporter dependency,
and is blocked when `APP_ENV=production`. Default startup prints no trace.
`OTEL_SERVICE_NAME` is supported with the bounded default `loveos-backend`.
`OTEL_TRACES_SAMPLER` and `OTEL_TRACES_SAMPLER_ARG` are left to the official SDK
instead of being reimplemented in Settings.

## 8. Span hierarchy

The manual spans follow the real orchestration context:

```text
game.websocket.join
├── game.lease.acquire
└── game.snapshot.load

game.settlement
├── game.settlement.persist
├── game.settlement.reward
├── game.settlement.replay
├── game.settlement.notification
│   └── notification.persist (only when a notification is actually created)
└── game.settlement.finalize
```

`game.websocket.join` begins before room load/lease and ends immediately after
runtime join emits the first state. It covers authentication, room load, lease,
runtime restore, membership/seat restoration, manager join, and first state,
but does not cover the long-lived receive loop, game actions, or heartbeat.

`game.lease.acquire` wraps only the join-time acquire CAS. Lease renewal
heartbeat and release produce no spans. `game.snapshot.load` reports the actual
durable/cache/memory fallback source. Settlement child spans preserve the
original persist, reward, replay, notification, and finalize order.

## 9. Attribute allow-list

Only these keys can reach a span:

- `game.type`;
- `state.source`;
- `result`;
- `retry.count`;
- `reconnect`;
- `settlement.stage`.

Values are also bounded: game types, state sources, results, and settlement
stages use enumerated low-cardinality sets; retry count is clamped to `0..10`;
reconnect accepts only booleans. Invalid keys or values are dropped rather than
stringified.

No room/user/session/order IDs, tokens, names, invite codes, URLs, credentials,
payloads, game state, SQL, SQL parameters, or exception messages are attached.

## 10. Privacy tests

Exporter-visible span names, resource attributes, span attributes, and events
were scanned for all required sentinels:

- `ADMIN_SECRET_SENTINEL`;
- `CUSTOMER_TOKEN_SENTINEL`;
- `ROOM_CODE_SENTINEL`;
- `DATABASE_PASSWORD_SENTINEL`;
- `S3_SECRET_SENTINEL`.

The real WebSocket join, settlement/notification workflow, direct allow-list
rejection test, and full console output contained none of them. Exception
recording and automatic exception status are disabled, avoiding accidental
payload disclosure through exception events.

## 11. Error isolation

Telemetry initialization, attribute update, span start/end, flush, and shutdown
failures are contained inside the telemetry boundary with fixed diagnostic
messages. Business exceptions are marked with the allow-listed `result=error`
and re-raised unchanged; HTTP status, WebSocket close code, transaction,
rollback, retry, settlement recovery, and notification idempotency paths remain
owned by existing code.

A contract test uses the SDK processor with a failing test exporter and performs
a real notification database write. The notification still commits and returns
an ID, proving exporter failure does not replace the business result.

## 12. Settings interaction

Telemetry imports the `get_settings` function but does not call it at module
import time. The cached startup snapshot is read only when FastAPI lifespan
calls `configure_tracing()`, preserving the R2A lifecycle and preventing an
early Settings freeze.

Trace settings are startup-stable. Existing runtime-observable
`load_settings()` boundaries, `ALLOW_LEGACY_CUSTOMER_HEADER`, `UPLOAD_PROVIDER`,
and required-on-use admin secret behavior are unchanged. All 30 Settings
contract tests remain part of the passing full suite.

## 13. Import boundary interaction

`lint-imports` analyzed 101 files and 294 dependencies:

- Repositories do not depend on API or service orchestration: **KEPT**.
- Pure game rules do not depend on web or persistence frameworks: **KEPT**.

Result: **2 kept, 0 broken**. Telemetry hooks exist only at application or
infrastructure orchestration boundaries. No rule, engine, AI, or repository
module gained an OpenTelemetry dependency.

## 14. Added and modified files

R2B1 added:

- `backend/core/telemetry.py`;
- `backend/tests/test_observability_contracts.py`;
- `docs/optimization/PHASE_3_0_R2B1_TRACE_FOUNDATION_REVIEW.md`.

R2B1 added focused hunks to:

- `backend/requirements.txt`;
- `backend/core/settings.py`;
- `backend/main.py`;
- `backend/core/game_room_lease.py`;
- `backend/core/game_state_store.py`;
- `backend/api/routes/websocket.py`;
- `backend/services/game_settlement_service.py`;
- `backend/notification_service.py`;
- `backend/tests/conftest.py`.

Some of these files were already dirty from protected R2A/B1 work; those
earlier changes were not reverted. No migration, mini-program product source,
database schema, or deployment file was modified by R2B1.

## 15. Test results

The final gate was rerun from the beginning after the last test edit.

| Gate | Final result |
|---|---|
| resolver dry run | PASS — no framework upgrade |
| `pip check` | PASS — no broken requirements |
| `python -m ruff check . ../scripts` | PASS |
| `lint-imports` | PASS — 2 kept, 0 broken |
| `python -m pytest -q` | PASS — 149 passed, 11 warnings |
| `python -m compileall -q .` | PASS |
| isolated empty SQLite `alembic upgrade head` | PASS |
| `npm run build:weapp` | PASS — Taro 4.2.0 |
| `npm run test:ci` | PASS |
| `npm run test:games` | PASS |
| `npm run test:landlord` | PASS |
| `git diff --check` | PASS — line-ending conversion warnings only |

The suite increased from 140 to 149 tests through 9 observability contract
tests. The 11 warnings are the existing Python 3.12 SQLite datetime-adapter
deprecation warnings.

Environment used: Python 3.12.13, Node v24.17.0, npm 11.13.0, Taro 4.2.0.

## 16. No-op Gate

The no-op tests remove all four trace-related environment variables and reset
the Settings cache before startup. With no OTel configuration:

- `configure_tracing()` returns disabled;
- spans are non-recording and console output is empty;
- FastAPI lifespan starts normally;
- `GET /api/health` returns the exact existing payload;
- `GET /api/ready` returns 200/ready;
- no endpoint, exporter, collector, network, or credential is required.

The dedicated no-op plus console gate command passed: **2 passed in 1.57s**.

## 17. Console Gate

With explicit test/development trace and console flags, local test data produced
both a real WebSocket join trace and a real settlement trace. Output included
the join children, settlement stage children, and notification span, with SDK
trace/span/parent identifiers showing their context hierarchy.

The complete console output was scanned and contained none of the five privacy
sentinels. It used only the isolated test database and TestClient; no production
database, collector, endpoint, or real user was contacted.

## 18. HTTP operation count

- Registered FastAPI `APIRoute` objects: **89**.
- Established public baseline excluding schema-hidden diagnostic
  `GET /api/health`: **88**.
- OpenAPI schema operations: **87**, because both health and readiness remain
  schema-hidden.

Required result: **88 public baseline operations — PASS**. No path, method,
request/response schema, status code, or HTTP payload contract changed. Because
the API contract did not change, client regeneration was not applicable.

## 19. WebSocket path count

The application still exposes exactly **3** WebSocket paths:

- `/ws/admin/orders`;
- `/ws/game/{room_code}`;
- `/ws/games/dice/{room_code}`.

The real join contract test verified the first state envelope remains exactly
`type`, `game`, `room_code`, and `data` with unchanged values. Payloads, close
codes, reconnect behavior, heartbeat, and game message handling remain
unchanged.

## 20. Alembic head

An isolated, initially empty SQLite database upgraded through every revision
and reported **`20260812_12 (head)`**. The temporary database was deleted after
verification.

## 21. Migration count

- Migration files: **12**.
- Migration-count change in R2B1: **0**.
- Schema change in R2B1: **0**.

## 22. Dist information

After the final clean Taro build measurement:

| Fact | Value |
|---|---:|
| files | `137` |
| bytes | `803,033` |
| approximate MiB | `0.766` |

The result exactly matches the approved R2A baseline.

## 23. Performance impact observation

R2B1 intentionally makes no claim that First State or Settlement Visibility is
faster and contains no performance optimization.

With default configuration, there is no SDK pipeline, processor, exporter,
serialization, network call, or console write. The only added work is the small
Python no-op context/allow-list hook at the selected boundaries. Explicit trace
mode records only the bounded manual spans; the synchronous console exporter is
development-only and blocked in production. Lease renewal heartbeat and game
action loops are not traced, preventing high-frequency span noise.

The foundation can now locate time among join setup, lease, snapshot, and the
five settlement stages. Actual latency conclusions require representative
traces in a separately reviewed R2B2/deployment setup.

## 24. Rollback

Rollback must be selective because the worktree contains user-owned B0/B1/R2A
changes.

1. Remove only the two OpenTelemetry requirement lines.
2. Remove R2B1 trace fields/properties from Settings and the lifespan
   configure/shutdown calls.
3. Remove only the `trace_span`/attribute hooks from lease, snapshot, WebSocket
   join, settlement, and selected notification boundaries, preserving their
   original business statements and order.
4. Remove the telemetry module, observability contract test, and telemetry
   reset lines in the shared test fixture.
5. Reinstall the remaining pinned requirements and rerun the full gate.

No database or migration rollback is necessary. Do not use a whole-worktree
checkout/reset for this rollback.

## 25. Recommendation for R2B2

R2B1 meets its dependency, privacy, compatibility, hierarchy, and complete-gate
requirements. The repository is ready for an **R2B2 review**, not automatic
R2B2 implementation. Any future auto-instrumentation or deployment exporter
must receive its own dependency resolution, payload/privacy review, sampling
plan, and failure-isolation gate.

**PASS — TRACE FOUNDATION COMPLETE — READY FOR R2B2 REVIEW**
