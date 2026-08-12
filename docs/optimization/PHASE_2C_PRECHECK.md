# Phase 2C Round 1 Precheck

## Baseline

- Commit: `62e8ba71eef6a02a911a85c532d5fe4ab82c20ff`
- Worktree: Phase 2B Round 2 is complete and verified but intentionally
  uncommitted; its modified and new files are retained as the working baseline.
- Backend: 94 passed, 11 Python 3.12 SQLite adapter warnings
- Router contract: 2 passed
- Public surface: 87 HTTP operations / 3 WebSocket paths
- `python -m compileall -q .`: passed through `backend/.venv`

## File size baseline

| File | Lines | Bytes |
|---|---:|---:|
| `backend/crud.py` | 799 | 26,658 |
| `backend/realtime.py` | 804 | 33,385 |
| `backend/api/routes/websocket.py` | 425 | 17,076 |
| `backend/game_maintenance.py` | 243 | 8,323 |
| `backend/core/game_state_store.py` | 174 | 6,136 |

## Production facts

- `/api/health`: **NOT VERIFIED IN THIS ENVIRONMENT**. The browser safety layer
  rejected the direct endpoint and the restricted shell could not connect.
- `/api/ready`: **NOT VERIFIED IN THIS ENVIRONMENT** for the same reason.
- Room create, HTTP action, WebSocket join, reconnect and completion:
  **NOT VERIFIED IN THIS ENVIRONMENT**. They require a controlled production
  identity and game state and are not simulated as production evidence.
- The last documented controlled environment reports PostgreSQL plus the
  database image provider; this Round does not change deployment or storage.

## Round gate

The 94-test, 2-test Router and 87/3 surface thresholds pass. Round 1 may proceed.
Round 2 WebSocket/session extraction is explicitly not authorized in this run.
