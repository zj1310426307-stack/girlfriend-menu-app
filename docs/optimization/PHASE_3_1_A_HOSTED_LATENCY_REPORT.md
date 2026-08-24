# Phase 3.1-A Hosted Latency Evidence Report

Date: 2026-08-15

Current status: **BLOCKED — ISOLATED STAGING CREATION REQUIRES AUTHORIZATION**

Resolved blocker: ~~`DEPLOYMENT REQUIRES PUBLISH STEP`~~ — PR #11 is merged
and published as immutable `main` revision
`ecfc91c0a63341116de52854c5073db55d539b2d`.

This report records a stopped evidence-collection attempt. It does not contain
invented hosted samples, inferred latency statistics, or performance changes.

## 1. Executive Summary

The complete local baseline gate passed, PR #11 published Phase 3.0 to `main`,
and the hosted test plan was written before any staging resource was created.
GitHub resolves `main` to merge commit `ecfc91c0...`; its Git tree
`27b794c2...` exactly matches the reviewed local commit `f6d28c5...`. GitHub
Actions passed, and the existing production Render API deployed that exact
revision successfully. Production was used only to verify publication and
health, never for sampling.

Authenticated, read-only Render and Neon inventory then proved that no
independent staging environment currently exists. Render has only the
production API and production static site. Neon has only its default
`production` branch. Creating a new schema-only Neon branch and a new
independent Render staging service is a cloud-state and shared-free-quota
action that has not yet received action-time authorization.

No hosted resource was created, modified, restarted, deployed, or deleted. No
synthetic hosted data was created. The privacy gate, hosted smoke gate, and
latency sampling were not run.

## 2. Environment

### Local reviewed environment

- repository: `girlfriend-menu-app` / LoveOS;
- local branch: `agent/phase-3-0-infrastructure-baseline`;
- reviewed local `HEAD`: `f6d28c581cb707bddcd0c8f2e7e177bf4fea31c8`;
- published `main`: `ecfc91c0a63341116de52854c5073db55d539b2d`;
- source proof: both commits use Git tree
  `27b794c2eb2e9f987a3fb558436a60431c3659b5`;
- worktree: no tracked code change; only the Phase 3.1 plan/report and existing
  handoff document are untracked;
- established application baseline: 88 public HTTP routes, 3 WebSocket
  routes, Alembic head `20260812_12`;
- established mini-program build baseline: 137 files, 803,033 bytes.

### Intended hosted environment

The frozen plan requires an independent Render staging service, an independent
schema-only/empty Neon branch or database, `APP_ENV=staging`, synthetic
secrets, database uploads, console tracing, and Redis unset for the first
experiment. This environment was **not established**.

### Local gate result

| Gate | Result | Evidence |
|---|---:|---|
| `pip check` | PASS | no broken requirements |
| Ruff | PASS | all checks passed |
| import-linter | PASS | 2 kept, 0 broken; 101 files, 294 dependencies |
| pytest | PASS | 165 passed, 11 warnings in 19.27 s |
| compileall | PASS | completed without error |
| Alembic | PASS | helper-isolated upgrade reached `20260812_12 (head)`; helper cleanup succeeded |
| `build:weapp` | PASS | Taro 4.2.0; compilation completed |
| `test:ci` | PASS | completed without error |
| `test:games` | PASS | completed without error |
| `test:landlord` | PASS | completed without error |
| `git diff --check` | PASS | no whitespace error |

## 3. Isolation Proof

The local plan defines the required isolation boundaries. Authenticated
read-only inventory proved that an isolated hosted target does not yet exist:

- `render.yaml` describes only a production-named service,
  `girlfriend-menu-api`, with `APP_ENV=production`, free plan, Singapore
  region, and `autoDeploy=true`;
- Render contains the production Python API in Singapore and the production
  static web service, with no independent staging service or staging project;
- the production API is Live on the Free plan and deployed published revision
  `ecfc91c0...`; it remains excluded from all test traffic;
- Neon contains one Free project in AWS US West 2 (Oregon), one default branch
  named `production`, and no preview/schema-only/empty staging branch;
- no provider secret, environment value, connection string, production row,
  database name, password, or query text was opened.

Production separation and source identity are proven. Staging data isolation
remains unproven because the staging resources have not been created.

## 4. Synthetic Data

No hosted synthetic customer, dish, order, game room, session, snapshot,
notification, record, replay, or settlement row was created.

| Item | Before | Created | After |
|---|---:|---:|---:|
| Hosted synthetic rows owned by Phase 3.1-A | 0 known | 0 | 0 known |
| Temporary Neon resources | 0 created by this run | 0 | 0 created by this run |
| Temporary Render resources | 0 created by this run | 0 | 0 created by this run |

Because no isolated hosted database was established, table-level hosted counts
were not queried and no production data was accessed.

## 5. Privacy Gate

Status: **NOT RUN — BLOCKED BEFORE HOSTED FLOW**.

No sentinel identifiers were transmitted. No Render log window or hosted
console-span output was collected.

Static review identified a material pre-sampling risk: the existing
`game_ws_first_state` application log includes `room=%s`. A future privacy gate
must search for the actual generated synthetic room code as well as the
literal `ROOM_SENTINEL`. If the raw code is present, formal sampling must stop.
Phase 3.1-A did not change this log because this phase prohibits code changes
before evidence collection and requires instrumentation amendments to receive
their own review.

No token, customer identity, invite code, database URL, password, S3
credential, payload, card/dice state, or SQL was collected in this report.

## 6. Run Methodology

The methodology was frozen in
`docs/optimization/PHASE_3_1_A_HOSTED_TEST_PLAN.md` before hosted access:

1. pass the complete local gate;
2. prove exact-source Render staging and isolated Neon staging;
3. run one sequential privacy-sentinel flow;
4. run the hosted smoke gate with synthetic identities;
5. collect sequential bounded join, reconnect, settlement, and cold samples;
6. correlate client monotonic timings with the current manual spans;
7. calculate only min, p50, nearest-rank p90, and max;
8. clean exact synthetic rows and temporary resources.

Step 1 completed. The read-only portion of step 2 completed and found no
staging resources; exact source publication is proven, but staging isolation
cannot be proven until resource creation is authorized. Steps 3 through 8 were
not run.

## 7. Cold/Warm Definition

The planned definitions remain:

- **COLD**: first successful target flow after a documented Render
  deploy/start or suspension recovery, with no earlier application flow in the
  same instance window;
- **WARM**: service ready, Neon compute active, one unrecorded warm-up flow
  completed, and no deploy, restart, suspension, or configuration change;
- **UNKNOWN**: service or database temperature cannot be proven; exclude from
  grouped statistics.

No run was classified because no hosted flow occurred.

## 8. First State Raw Evidence

No First State sample was collected.

| Planned group | Target | Valid samples | Status |
|---|---:|---:|---|
| Warm WebSocket join | at least 10 | 0 | blocked before staging creation |
| Warm reconnect | at least 10 | 0 | blocked before staging creation |
| Cold WebSocket join | 3–5 | 0 | blocked before staging creation |

There are no client T0/T1 values, server span durations, snapshot sources,
results, or reconnect labels to report.

## 9. First State Statistics

Not computed. Sample count is zero. Min, p50, p90, and max would be fabricated
and are intentionally omitted.

## 10. Join Stage Breakdown

No timing attribution is possible. Static code review confirms only the
current observability shape:

```text
game.websocket.join
  game.lease.acquire
  game.snapshot.load
```

The existing first-state application timing log also exposes setup, client
join wait, auth, membership, manager join, and total fields, subject to the
privacy failure risk described above. Static presence does not establish
duration or bottleneck severity for room/auth, lease, snapshot, restore,
membership, manager join, first state, network, TLS, or client scheduling.

## 11. Settlement Raw Evidence

No settlement sample was collected.

| Planned group | Target | Valid samples | Status |
|---|---:|---:|---|
| Warm settlement visibility | at least 10 | 0 | blocked before staging creation |

There are no completion timestamps, public visibility timestamps, parent span
durations, or child-stage durations to report.

## 12. Settlement Statistics

Not computed. Sample count is zero. Min, p50, p90, and max are intentionally
omitted.

## 13. Settlement Stage Breakdown

No percentage attribution is possible. Static code review confirms only the
current span hierarchy:

```text
game.settlement
  game.settlement.persist
  game.settlement.reward
  game.settlement.replay
  game.settlement.notification
    notification.persist (only when created)
  game.settlement.finalize
```

No evidence supports assigning the reported approximately 34.5-second symptom
to persist, reward, replay, notification, finalize, database visibility,
polling, background work, or client refresh.

## 14. Client/Server Gap

Unknown. No paired client timing and server trace exists.

The plan defines the First State boundary as client T0 before WebSocket
connect/join through the first legal state, compared with the matching
`game.websocket.join` duration. It defines Settlement Visibility as the final
client action through the first complete record from the existing authenticated
`GET /api/games/records/my`, compared with `game.settlement` and its end time.

Without samples, no network/handshake/untraced gap and no post-settlement/public
visibility gap can be quantified.

## 15. Render Observations

Repository-visible facts:

- the only declared service is `girlfriend-menu-api`;
- plan: free;
- region: Singapore;
- declared application environment: production;
- automatic deployment: enabled;
- the deployment contract is Git-revision based.

Provider-console observation:

- authenticated inventory contains exactly one Python API and one static web
  service, both production resources; no staging service exists;
- production API: Free plan, Singapore, Live, Blueprint-managed, automatic
  deploy enabled;
- its successful deployment used exact commit `ecfc91c0...`, started at
  2026-08-15 22:09:14 GMT+8, and completed in 1 minute 15 seconds;
- Render displays the Free-plan cold-start warning; no production setting,
  deploy, restart, plan, or environment value was changed or opened.

## 16. Neon Observations

Provider-console observation:

- authenticated Free account contains one project in AWS US West 2 (Oregon),
  PostgreSQL 18, and one default branch named `production`;
- branch inventory is 1 of 10 available slots; there is no preview,
  schema-only, or empty staging branch;
- the primary compute is configured for 0.25 to 2 CU and the project reports
  six-hour history retention;
- no connection string, password, database name, query text, production row,
  or environment value was viewed;
- no branch/database was created, changed, resumed, queried, or deleted.

Neon staging isolation is therefore not yet available for evidence collection.

## 17. Bottleneck Ranking

| Area | Ranking | Reason |
|---|---|---|
| First State total | UNKNOWN / NEED MORE EVIDENCE | no hosted client/server sample |
| room/auth | UNKNOWN / NEED MORE EVIDENCE | no stage timing |
| lease | UNKNOWN / NEED MORE EVIDENCE | no span duration |
| snapshot/restore | UNKNOWN / NEED MORE EVIDENCE | no span duration or source |
| membership/manager join | UNKNOWN / NEED MORE EVIDENCE | no privacy-safe hosted timing |
| settlement total | UNKNOWN / NEED MORE EVIDENCE | no hosted trace |
| persist/reward/replay/notification/finalize | UNKNOWN / NEED MORE EVIDENCE | no child duration or percentage |
| post-settlement visibility gap | UNKNOWN / NEED MORE EVIDENCE | no public-read timing |

No item is labelled P0, P1, P2, or NO ISSUE because there is no hosted timing
evidence.

## 18. What Is NOT the Bottleneck

No runtime stage can be excluded as a bottleneck from this run. The only safe
negative conclusions are scope/design conclusions:

- automatic FastAPI instrumentation was not enabled;
- automatic SQLAlchemy instrumentation was not enabled;
- OTLP, Collector, Jaeger, Zipkin, Prometheus, and Grafana were not introduced;
- this attempt did not change queries, indexes, pools, Redis, cache, snapshot
  order, leases, retries, settlement transactions, background cadence,
  `manager.py`, WebSocket behavior, or preload behavior.

These facts prevent added instrumentation or optimization changes from
confounding the attempt; they do not prove any application stage is fast.

## 19. Evidence Limitations

- the exact reviewed code is published and source-matched, but no independent
  staging service or database exists yet;
- no privacy sentinel, hosted smoke, client timing, span JSON, application-log
  window, Neon compute observation, or cold-start observation exists;
- the raw-room-code log risk remains unresolved and could independently stop a
  future formal sample;
- zero samples means no latency distribution or production percentile claim is
  valid;
- the historical approximately 4.9–9.8-second First State and approximately
  34.5-second Settlement Visibility symptoms were not reproduced in this run.

## 20. Recommended Phase 3.1-B

Do **not** begin a performance optimization phase from this report. Publication
is complete. The single required authorization is to create one short-lived
schema-only Neon branch and one independent Render Free staging service using
exact revision `ecfc91c0...`, synthetic secrets/data, Redis unset, and
automatic deployment disabled. These resources should be deleted after the
bounded experiment unless separately retained.

After that action is authorized, resume Phase 3.1-A rather than optimizing.
Run the raw-room-code privacy sentinel first; if it leaks, stop without fixing
code in this phase. Only a passing privacy gate permits smoke and sampling.

Only those results may define a true Phase 3.1-B optimization proposal.

## 21. Cleanup Evidence

No cleanup mutation was necessary because this attempt created no hosted
resource and no hosted synthetic row.

| Target | Created by this run | Deleted by this run | Verification |
|---|---:|---:|---|
| Render staging service | 0 | 0 | stopped before creation |
| Render deploy/config change | 0 | 0 | no action taken |
| Neon branch/database | 0 | 0 | stopped before creation |
| Hosted synthetic rows | 0 | 0 | no isolated database connected |
| Hosted trace/log evidence copy | 0 | 0 | no sampling window collected |

Production resource metadata was inspected read-only to prove source publication
and the absence of staging. No production setting, credential, environment
value, row, log payload, deploy, restart, resize, query, or deletion occurred.

---

Current decision: **BLOCKED — HOSTED EVIDENCE NOT COLLECTED**

Required next authorization: **CREATE ISOLATED STAGING RESOURCES**
