"""Run repeatable local V3 API and rule-AI latency budgets in an isolated database."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


def percentile(values: list[float], fraction: float) -> float:
    """Return a nearest-rank percentile for a small deterministic sample."""
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return round(ordered[index], 3)


def measure(callable_, samples: int) -> list[float]:
    """Measure one synchronous callable in milliseconds."""
    results = []
    for _ in range(samples):
        started = time.perf_counter()
        callable_()
        results.append((time.perf_counter() - started) * 1000)
    return results


def main() -> int:
    """Measure V3 API, AI, room recovery and replay serialization budgets."""
    with tempfile.TemporaryDirectory(prefix="loveos-v3-benchmark-") as directory:
        database_path = (Path(directory) / "benchmark.db").as_posix()
        os.environ.update(
            {
                "APP_ENV": "test",
                "DATABASE_URL": f"sqlite:///{database_path}",
                "CUSTOMER_INVITE_CODE": "benchmark-invite",
                "ALLOW_LEGACY_CUSTOMER_HEADER": "false",
                "LOVEOS_TRACING_ENABLED": "false",
            }
        )

        from fastapi.testclient import TestClient

        from ai.registry import AI_PROVIDERS
        from database import engine
        from main import app

        with TestClient(app) as client:
            session = client.post(
                "/api/customers/session",
                json={"invite_code": "benchmark-invite", "display_name": "benchmark"},
            )
            if session.status_code != 200:
                raise RuntimeError(f"benchmark session failed: {session.status_code}")
            headers = {
                "Authorization": f"Bearer {session.json()['customer_token']}"
            }

            def bootstrap() -> None:
                response = client.get("/api/bootstrap", headers=headers)
                if response.status_code != 200:
                    raise RuntimeError(f"bootstrap failed: {response.status_code}")

            def legacy_home() -> None:
                for path in (
                    "/api/dishes",
                    "/api/stats/favorite-ranking",
                    "/api/couple/score",
                ):
                    response = client.get(path, headers=headers)
                    if response.status_code != 200:
                        raise RuntimeError(f"legacy home failed: {path} {response.status_code}")

            bootstrap()
            legacy_home()
            bootstrap_ms = measure(bootstrap, 30)
            legacy_ms = measure(legacy_home, 30)

        board = [[0 for _ in range(15)] for _ in range(15)]
        for index in range(20):
            board[5 + index // 10][2 + index % 10] = 1 if index % 2 == 0 else 2
        state = {
            "board": board,
            "players": [
                {"id": "human", "color": "black"},
                {"id": "ai_gomoku", "color": "white"},
            ],
        }
        ai_ms = measure(
            lambda: AI_PROVIDERS.choose_action(
                "gomoku", state, "ai_gomoku", "strategy"
            ),
            100,
        )
        from game_runtime.manager import GameRoomManager

        manager = GameRoomManager()

        def create_room_state() -> dict:
            return manager._new_room("BENCH1", "gomoku", 2)

        room = create_room_state()
        snapshot = manager._snapshot(room)

        def recover_room_state() -> None:
            restored = create_room_state()
            manager._restore_snapshot(restored, snapshot)

        room_creation_ms = measure(create_room_state, 100)
        reconnect_ms = measure(recover_room_state, 100)
        replay_ms = measure(lambda: json.dumps(snapshot), 100)
        engine.dispose()

        result = {
            "environment": "local TestClient + isolated SQLite; not hosted or real-device",
            "samples": {
                "api": 30,
                "ai": 100,
                "room_lifecycle": 100,
            },
            "bootstrap_ms": {
                "mean": round(statistics.mean(bootstrap_ms), 3),
                "p95": percentile(bootstrap_ms, 0.95),
            },
            "legacy_three_requests_ms": {
                "mean": round(statistics.mean(legacy_ms), 3),
                "p95": percentile(legacy_ms, 0.95),
            },
            "gomoku_strategy_ai_ms": {
                "mean": round(statistics.mean(ai_ms), 3),
                "p95": percentile(ai_ms, 0.95),
            },
            "room_creation_ms": {
                "mean": round(statistics.mean(room_creation_ms), 3),
                "p95": percentile(room_creation_ms, 0.95),
            },
            "reconnect_snapshot_ms": {
                "mean": round(statistics.mean(reconnect_ms), 3),
                "p95": percentile(reconnect_ms, 0.95),
            },
            "replay_serialization_ms": {
                "mean": round(statistics.mean(replay_ms), 3),
                "p95": percentile(replay_ms, 0.95),
            },
            "budgets_ms": {
                "ordinary_api_p95": 300,
                "local_ai_p95": 100,
                "room_creation_p95": 300,
                "reconnect_p95": 3000,
                "replay_p95": 1000,
            },
        }
        print(json.dumps(result, ensure_ascii=True, indent=2))
        if result["bootstrap_ms"]["p95"] >= 300:
            return 1
        if result["gomoku_strategy_ai_ms"]["p95"] >= 100:
            return 1
        if result["room_creation_ms"]["p95"] >= 300:
            return 1
        if result["reconnect_snapshot_ms"]["p95"] >= 3000:
            return 1
        if result["replay_serialization_ms"]["p95"] >= 1000:
            return 1
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
