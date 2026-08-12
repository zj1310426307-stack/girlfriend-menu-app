# Phase 2C Game Runtime Map

This map records the game persistence and real-time surface after Round 2.
Snapshot storage, room leases, runtime rules, socket transport and settlement
side effects remain separate concerns.

| Function | Domain | Callers | Tables | Commit? | Runtime Critical? | Round |
|---|---|---|---|---|---:|---|
| `touch_game_room` | ROOM | flight/core state, CRUD helpers | in-memory `game_rooms` row | no | yes | R1_WRAP |
| `list_games` | CATALOG | HTTP games Router | `games` | no | no | R1_MOVE |
| `get_game` | CATALOG | room create | `games` | no | no | R1_MOVE |
| `create_game_room` | ROOM | HTTP, flight/core room | `games`, `game_rooms` | yes | yes | R1_MOVE |
| `get_game_room` | ROOM | HTTP, WS, game services, recovery | `game_rooms` + selectin relationships | no | yes | R1_MOVE |
| `get_game_room_runtime` | ROOM | WebSocket setup | `game_rooms`, relationships disabled | no | yes | R1_MOVE |
| `update_game_room_status` | ROOM | WebSocket settlement/rematch | `game_rooms` | yes | yes | R1_MOVE |
| `list_game_players` | PLAYER | HTTP recovery/create, WS | `game_rooms`, `game_players` | no | yes | R1_MOVE |
| `join_game_room` | PLAYER | HTTP, WS, game services/core | `game_rooms`, `game_players`, notifications | configurable | yes | R1_MOVE |
| `issue_room_session_token` | ROOM_SESSION | WebSocket | `game_players`, `game_rooms` | configurable | yes | R1_MOVE |
| `mark_game_player_disconnected` | PLAYER | WebSocket finally | `game_rooms`, `game_players` | yes when found | yes | R1_MOVE |
| `expire_stale_game_rooms` | MAINTENANCE | app maintenance loop/tests | rooms, players, reconnect tokens | conditional | yes | DEFER |
| `_game_record_query` | RECORD | finish/list helpers | records, rooms, players | no | yes | R1_MOVE |
| `finish_game_room` | RECORD | WS, flight, core settlement, maintenance | rooms, records, players | yes | yes | R1_MOVE |
| `list_game_records` | RECORD | HTTP/tests | records, rooms, players | no | no | R1_MOVE |
| `game_stats` | STATS | admin/tests | game, score, task, achievement tables | no | no | KEEP |

## Existing helper boundaries

| Helper | Owner | Round 1 policy |
|---|---|---|
| `DatabaseGameStateStore` / `state_cache` | durable snapshot plus optional hot cache | READ ONLY |
| `GameRoomLeaseRepository` | PostgreSQL CAS ownership and epoch | READ ONLY |
| `GameRoomManager` | process-local sockets, dice/gomoku live rules and filtered state | READ ONLY |
| `reconcile_game_settlements` | crash-window repair | READ ONLY |
| `resolve_turn_timeouts` | authoritative timeout repair | READ ONLY |
| `_persist_completed_game*` | WebSocket settlement order | Round 2 |

## Target Round 1 boundary

```text
HTTP games Router
  -> services/game_persistence_service.py
     -> repositories/game_runtime.py
        -> SQLAlchemy Session / PostgreSQL

WebSocket, maintenance and existing game services
  -> crud.py compatibility facade
     -> services/game_persistence_service.py
```

`expire_stale_game_rooms` and `game_stats` remain implemented in `crud.py`.
Snapshot, lease, settlement rewards and WebSocket protocol objects never enter
the new Repository.

Transaction note: the player Repository respects `commit=False`, but the legacy
post-join notification orchestration can independently commit for a real guest.
This is retained for behavioral compatibility and explicitly deferred to the
Round 2 socket-session orchestration review.

## Round 2 active boundary

```text
WebSocket Router
  -> services/game_socket_session_service.py
     -> game_persistence_service / PostgreSQL lease / GameRoomManager

Completion Event
  -> services/game_settlement_service.py
     -> finish record / rewards / replay / memory / notification
```

The Router retains `accept`, receive/send, join-first validation, payload
shaping and close codes. The Session Service owns room loading, lease acquire,
snapshot/seat restore, customer authentication, membership plus room-session
token composition, manager attach, durable status sync, disconnect persistence
and final-socket lease release. The Settlement Service owns the existing
pending-to-complete side-effect sequence. `realtime.py`, snapshot storage and
the PostgreSQL CAS lease implementation are unchanged until Round 3.
