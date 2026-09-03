# Phase 3.1-A Hosted Latency Evidence Collection Plan

Date: 2026-08-15

Published Phase 3.0 revision: `ecfc91c0a63341116de52854c5073db55d539b2d`

Reviewed local revision: `f6d28c581cb707bddcd0c8f2e7e177bf4fea31c8`
(tree `27b794c2eb2e9f987a3fb558436a60431c3659b5`, identical to published `main`)

Status: the local gate and read-only provider inventory are complete. No
staging resource has been created, modified, or deleted. Creating the isolated
Render and Neon resources remains a separately confirmed cloud action.

## 1. Objective and boundary

This phase collects hosted evidence for two existing symptoms:

- First State latency: client WebSocket connect/join to the first legal state;
- Settlement Visibility latency: game completion to the first existing public
  read that exposes a complete record.

It does not optimize code. Database queries, indexes, pools, Redis, cache,
snapshot order, leases, retries, settlement order, background cadence,
`GameRoomManager`, WebSocket behavior, and preload behavior remain unchanged.
The current bounded manual tracing and `ConsoleSpanExporter` are kept exactly
as implemented. No automatic instrumentation, OTLP, Collector, Metrics, or
additional dependency is allowed.

## 2. Preconditions and stop conditions

The following order is mandatory:

1. Save this plan before connecting to or creating hosted resources.
2. Run the complete local baseline gate.
3. Read-only inspect candidate Render and Neon resources.
4. Prove the service and database are staging-only and cannot reach production
   data.
5. Prove the staging service runs the complete Phase 3.0 working-tree code.
6. Run the privacy sentinel flow before formal sampling.
7. Run smoke, bounded samples, evidence extraction, and cleanup.

Stop immediately when any of these occurs:

- a local baseline gate fails;
- staging would use the production `DATABASE_URL` or copied production rows;
- the selected staging revision differs from published `main` revision
  `ecfc91c0a63341116de52854c5073db55d539b2d` or its verified code tree;
- an existing production service or database must be modified;
- any secret, token, customer identity, room code, invite, database URL,
  password, S3 credential, game payload, card/dice state, or SQL appears in
  trace JSON or collected application logs;
- a critical stage is absent and the primary questions cannot be answered;
- cleanup targets cannot be proven to be staging-only synthetic resources.

The earlier `DEPLOYMENT REQUIRES PUBLISH STEP` blocker is resolved by merged PR
#11. It must not be reused as the reason for a later staging or privacy stop.

## 3. Planned staging architecture

```text
current reviewed Git revision
  -> independent Render staging web service
     APP_ENV=staging
     LOVEOS_TRACING_ENABLED=true
     LOVEOS_TRACING_CONSOLE=true
     REDIS_URL unset for experiment A
  -> independent Neon staging branch/database
     schema from Alembic only
     synthetic rows only
  -> Render staging logs
     bounded manual spans plus existing timing logs
  -> local redacted evidence table
```

The existing `render.yaml` describes only the production-named
`girlfriend-menu-api` service with `APP_ENV=production` and `autoDeploy=true`.
It will not be edited or applied to production in this phase. A candidate
staging service must be independently identifiable before any setting is read
or changed.

## 4. Source revision gate

PR #11 merged the reviewed Phase 3.0 branch into `main`. GitHub resolves
`main` to merge commit `ecfc91c0a63341116de52854c5073db55d539b2d`.
Its Git tree is `27b794c2eb2e9f987a3fb558436a60431c3659b5`, exactly matching local reviewed
commit `f6d28c581cb707bddcd0c8f2e7e177bf4fea31c8`. GitHub Actions passed for the
merge revision, and the existing production Render service successfully
deployed that exact revision. Production is source-revision evidence only and
must not be used for Phase 3.1-A sampling.

The independent staging service must deploy published `main` revision
`ecfc91c0...` with automatic deployment disabled for the bounded experiment.
No temporary commit, branch push, patch upload, Blueprint change, or production
configuration change is needed or authorized.

## 4.1 Read-only provider inventory

The authenticated inventory on 2026-08-15 found:

- Render: one production Python API service in Singapore and one production
  static web service; no independent staging service or staging project;
- Neon: one project in AWS US West 2 (Oregon), with only the default
  `production` branch; no preview, schema-only, or empty staging branch;
- no credential, connection string, password, environment value, production
  row, or query text was opened during inventory.

Therefore the exact-source gate is ready, but the isolation gate cannot pass
until new staging-only resources are explicitly authorized and created.

## 5. Neon isolation plan

Preferred target: an independent schema-only Neon branch. If schema-only
branching is unavailable, use an independent empty branch/database and build
it only with `alembic upgrade head`.

Before migration, record without credentials:

- project/branch label and a redacted identifier;
- region;
- branch type;
- compute state and whether it was suspended/cold;
- direct or pooled connection mode;
- empty/schema-only proof;
- explicit proof that the branch is not the production branch.

Never record or export the connection string, password, query text, or copied
production data. The migration must reach `20260812_12`. Production branch
cloning is prohibited even when the platform offers it as the fastest option.

## 6. Render isolation and settings plan

The independent staging service must use only:

- `APP_ENV=staging`;
- the isolated Neon staging URL;
- a synthetic `CUSTOMER_INVITE_CODE`;
- a synthetic `ADMIN_PASSWORD`;
- a newly generated strong synthetic `ADMIN_SECRET`;
- `UPLOAD_PROVIDER=database`;
- `LOVEOS_TRACING_ENABLED=true`;
- `LOVEOS_TRACING_CONSOLE=true`;
- a staging-only `OTEL_SERVICE_NAME`;
- `REDIS_URL` unset for experiment A.

Record service plan, region, deploy/start timestamps, service identifier in
redacted form, and cold/warm classification. Do not reveal environment values.
Production service configuration, instance size, tracing flags, or deployment
state must not change.

## 7. Synthetic dataset

All synthetic rows use one analysis owner label and time-bounded prefix, for
example `phase31a-20260815-<random>`. The dataset contains:

- synthetic customer A and B created through the public session flow;
- the application seed catalogue (expected 19 dishes, verified after startup)
  or the smaller existing minimum required by the tested flows;
- only the synthetic orders needed for HTTP smoke;
- fresh synthetic dice or Gomoku rooms for each bounded run;
- records, notifications, memories, replays, sessions, and snapshots produced
  only by those test flows.

Record seed source, table-level before counts, synthetic inserted counts, and
cleanup owner. Do not manually copy a row from production. Identifiers and
room codes are used transiently by the runner but are not placed in the final
evidence table.

## 8. Privacy gate

Before formal sampling, run one sequential sentinel flow carrying:

- `CUSTOMER_SENTINEL`;
- `ROOM_SENTINEL` or the exact known generated synthetic room code;
- `ADMIN_SENTINEL`;
- `INVITE_SENTINEL`;
- `DATABASE_SENTINEL` only inside a synthetic staging credential value.

Scan the bounded Render log window, every console span JSON object, and normal
application logs. Match both the literal sentinels and the actual generated
customer IDs, room code, tokens, invite, and database host/credential fragments.

The existing `game_ws_first_state` application log currently includes a
`room=%s` field. The hosted privacy gate must therefore explicitly test the
known generated room code, not merely search for the literal word
`ROOM_SENTINEL`. If that value is present, the result is a privacy failure and
formal sampling stops; no code amendment is made inside Phase 3.1-A.

## 9. Trace collection and correlation

Use only `ConsoleSpanExporter` output from the staging service. A local
collector copies a bounded time window into a redacted evidence artifact; it
does not add an exporter or send data to another service.

Runs execute sequentially so each client-side analysis ID maps to one trace
time window without adding a high-cardinality `run_id` span attribute. The
evidence table uses synthetic IDs such as `FS-W-01`, `RC-W-01`, and `ST-W-01`.
Trace/span IDs may be used transiently for parent-child matching but are not
customer identifiers.

Expected manual hierarchy:

```text
game.websocket.join
  game.lease.acquire
  game.snapshot.load

game.settlement
  game.settlement.persist
  game.settlement.reward
  game.settlement.replay
  game.settlement.notification
    notification.persist (only when a notification is created)
  game.settlement.finalize
```

An absent nonessential child is recorded as not applicable. A missing parent
or stage needed to answer the two primary questions is an `OBSERVABILITY GAP`
and stops sampling for a separate amendment review.

## 10. First State definition

Client timing:

- `T0_client`: monotonic timestamp immediately before initiating the WebSocket
  connection; the join frame is sent immediately after the handshake.
- `T1_client`: receipt of the first legal `type=state` or legacy
  `type=room_state` frame.
- First State latency: `T1_client - T0_client`.

Server timing:

- total `game.websocket.join` duration;
- `game.lease.acquire` duration;
- `game.snapshot.load` duration and `state.source`;
- existing `game_ws_first_state` fields for setup, client join wait, auth,
  membership, manager join, and total, but only if their privacy gate passes;
- `result` and `reconnect` when present in the current allow-list output.

The difference between client total and server span total is reported as an
unattributed boundary covering network/TLS/handshake, scheduling, and any
untraced interval. It is not assigned to one cause without independent proof.

## 11. Settlement Visibility definition

The public visibility path is the existing authenticated
`GET /api/games/records/my`. Its service intentionally hides records while
`settlement_status != complete`.

For each final legal game action:

- `T0_client`: monotonic timestamp immediately before sending the final action;
- `T0_server`: `game.settlement` span start, the closest existing observable
  point to server consumption of the completion event;
- `T1_public`: first bounded poll response containing the new complete record;
- client/public visibility latency: `T1_public - T0_client`;
- server settlement latency: `game.settlement` duration;
- post-settlement/public gap: `T1_public - game.settlement.end_time`.

Poll at a fixed low rate (planned 250 ms, bounded timeout 60 seconds) and do not
change the settlement order. Record persist, reward, replay, notification, and
finalize child durations and their percentage of the settlement parent.
Because the existing WebSocket sends finished state before settlement begins,
receipt of that frame is not accepted as settlement visibility.

## 12. Cold and warm definitions

`COLD` means the first successful target flow after a documented Render
deploy/start or platform suspension recovery, with start/resume evidence and no
earlier application flow in that instance window.

`WARM` means the service is already ready, the Neon compute is active, one
unrecorded warm-up flow has completed, and the sample follows without a deploy,
restart, suspension, or configuration change.

Cold and warm results remain separate. A run with ambiguous service or Neon
state is labelled `UNKNOWN` and excluded from grouped statistics, not folded
into warm data.

## 13. Sample schedule

After privacy and smoke pass:

- warm WebSocket joins: 10;
- warm reconnects: 10;
- warm settlements: 10;
- cold-start joins: target 3 to 5, recording the actual feasible number;
- no concurrent load and no hundreds-request stress run.

Each run gets a new synthetic room where required. Runs are sequential, with a
short quiet window around each trace. Redis remains unset for this first
PostgreSQL-only experiment. A Redis comparison is a separate experiment only
if production architecture actually uses Redis and receives separate approval.

## 14. Hosted smoke gate

Before samples, verify with synthetic identities only:

- `/api/health` returns its existing success payload;
- `/api/ready` reports ready;
- synthetic customer session creation/authentication;
- one synthetic HTTP order flow;
- WebSocket join and first state;
- reconnect token, HTTP recovery, and WebSocket reconnect;
- a completed synthetic game;
- the resulting complete record through `/api/games/records/my`.

Any response schema, status, WebSocket envelope, or business behavior mismatch
stops the experiment. No API is changed to make the smoke pass.

## 15. Evidence schema

The redacted row schema is:

| Field | Meaning |
|---|---|
| `run_id` | synthetic analysis ID only |
| `environment` | staging experiment label, never a URL |
| `temperature` | cold, warm, or unknown |
| `operation` | join, reconnect, or settlement |
| `client_latency_ms` | client T0 to T1 |
| `server_trace_ms` | matching parent span duration |
| `lease_ms` | lease child duration |
| `snapshot_ms` | snapshot child duration |
| `snapshot_source` | allow-listed source |
| `persist_ms` | settlement persist duration |
| `reward_ms` | reward duration |
| `replay_ms` | replay duration |
| `notification_ms` | notification stage duration |
| `finalize_ms` | finalize duration |
| `result` | allow-listed result only |
| `client_server_gap_ms` | defined boundary difference |

No customer ID, token, room code, invite, URL, database name, payload, card/dice
state, SQL, or password enters this table.

## 16. Statistics and attribution

For each operation/temperature group with sufficient samples, calculate count,
minimum, p50/median, nearest-rank p90, and maximum. Do not claim production
p95/p99 from these small diagnostic samples.

First State attribution reports client total, join parent, lease, snapshot,
the privacy-safe existing timing-log stages, and the unassigned client/server
gap. Settlement attribution reports parent total, each child duration and
percentage, public visibility total, and the post-settlement/public gap.

Evidence is ranked only as `P0`, `P1`, `P2`, `NO ISSUE`, or
`UNKNOWN / NEED MORE EVIDENCE`. A stage is not called a bottleneck merely
because it exists.

## 17. Success criteria

Phase 3.1-A evidence collection succeeds only when:

- every local baseline gate passes first;
- exact-source staging and database isolation are proven;
- the privacy gate passes;
- all hosted smoke flows pass with synthetic data;
- warm sample targets and as many valid cold samples as feasible are captured;
- client and server traces are correlated without identity attributes;
- First State and Settlement Visibility receive evidence-based attribution;
- Render and Neon observations are recorded without secrets;
- synthetic rows and temporary resources are cleaned and verified;
- `PHASE_3_1_A_HOSTED_LATENCY_REPORT.md` documents raw evidence, statistics,
  limitations, ranking, non-bottlenecks, and a Phase 3.1-B recommendation.

If any precondition blocks hosted execution, the report must say what was
proven locally, what hosted evidence is absent, and what single authorized next
step is required. It must not invent latency samples.

## 18. Cleanup ownership

The experiment owner is the Phase 3.1-A synthetic analysis ID. Before cleanup,
record staging-only table counts for the owned prefix and resource identifiers
in redacted form. Delete dependent synthetic rows through verified staging-only
paths, then prove owned counts are zero.

If a Neon branch or Render service was created solely for this experiment,
delete that exact resource after resolving and rechecking its staging identity.
If it is retained as a reusable staging resource, record the explicit reason,
owner, expiry/review date, and disabled tracing state. Never delete, restart,
resize, or reconfigure a production resource.
