"""Run a controlled production Gomoku WebSocket/reconnect/settlement smoke.

The script reads ``CUSTOMER_INVITE_CODE`` from the environment and never logs
it or the issued customer/session credentials. It creates two clearly labelled
test identities and one auditable completed game record.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid

import httpx
from websockets.exceptions import ConnectionClosed
from websockets.legacy.client import connect as legacy_connect


API = os.getenv("PRODUCTION_API_ORIGIN", "https://girlfriend-menu-api.onrender.com")
WS = API.replace("https://", "wss://").replace("http://", "ws://")
INVITE = os.environ["CUSTOMER_INVITE_CODE"]


def millis(started_at: float) -> int:
    """Return elapsed wall time in whole milliseconds."""
    return round((time.perf_counter() - started_at) * 1000)


def progress(stage: str, **metrics) -> None:
    """Emit credential-free progress so a failed run still identifies its stage."""
    print(json.dumps({"stage": stage, **metrics}, ensure_ascii=False), flush=True)


async def receive_json(socket, timeout: float = 90) -> dict:
    """Receive one JSON frame with a bounded production timeout."""
    return json.loads(await asyncio.wait_for(socket.recv(), timeout))


async def drain_latest_state(socket, idle_timeout: float = 0.35) -> dict | None:
    """Discard reconnect presence broadcasts and retain their newest state."""
    latest = None
    while True:
        try:
            payload = await receive_json(socket, timeout=idle_timeout)
        except asyncio.TimeoutError:
            return latest
        if payload.get("type") == "state":
            latest = payload


async def run() -> dict:
    """Execute the full two-client production acceptance flow."""
    result: dict = {"run": uuid.uuid4().hex[:8]}
    async with httpx.AsyncClient(timeout=90) as client:
        sessions = []
        for label in ("A", "B"):
            started = time.perf_counter()
            response = await client.post(
                API + "/api/customers/session",
                json={
                    "invite_code": INVITE,
                    "display_name": f"Phase2C生产验收{label}-{result['run']}",
                    "device_label": "Codex controlled smoke",
                },
            )
            result[f"session_{label}_status"] = response.status_code
            result[f"session_{label}_ms"] = millis(started)
            response.raise_for_status()
            sessions.append(response.json())
        first_session, second_session = sessions
        auth = {"Authorization": f"Bearer {first_session['customer_token']}"}

        started = time.perf_counter()
        created = await client.post(
            API + "/api/games/rooms",
            headers=auth,
            json={
                "game_type": "gomoku",
                "creator": first_session["customer_id"],
                "invite_code": "",
            },
        )
        result.update(create_status=created.status_code, create_ms=millis(started))
        created.raise_for_status()
        room_code = created.json()["room_code"]
        result["room_code"] = room_code
        progress("room_created", create_ms=result["create_ms"])

        async def connect(session: dict, name: str):
            last_error = None
            room_busy_retries = 0
            for attempt in range(1, 11):
                socket = None
                started_connect = time.perf_counter()
                try:
                    socket = await legacy_connect(
                        f"{WS}/ws/game/{room_code}",
                        open_timeout=90,
                        close_timeout=10,
                        ping_interval=10,
                        ping_timeout=20,
                        max_size=2**20,
                    )
                    connect_ms = millis(started_connect)
                    started_first = time.perf_counter()
                    await socket.send(
                        json.dumps(
                            {
                                "type": "join",
                                "game": "gomoku",
                                "data": {
                                    "customer_token": session["customer_token"],
                                    "name": name,
                                },
                            },
                            ensure_ascii=False,
                        )
                    )
                    first_state = await receive_json(socket)
                    first_ms = millis(started_first)
                    if first_state.get("type") == "room_busy":
                        room_busy_retries += 1
                        retry_after = max(
                            0.5,
                            min(float(first_state.get("retry_after_ms") or 1000) / 1000, 5),
                        )
                        await socket.close()
                        await asyncio.sleep(retry_after)
                        continue
                    if first_state.get("type") != "state":
                        raise RuntimeError(
                            f"unexpected first frame: {first_state.get('type') or 'missing'}"
                        )
                    session_frame = await receive_json(socket)
                    return (
                        socket,
                        connect_ms,
                        first_ms,
                        first_state,
                        session_frame,
                        attempt,
                        room_busy_retries,
                    )
                except (
                    ConnectionClosed,
                    ConnectionError,
                    OSError,
                    TimeoutError,
                    asyncio.TimeoutError,
                ) as error:
                    last_error = error
                    if socket is not None:
                        await socket.close()
                    if attempt < 10:
                        await asyncio.sleep(min(attempt * 1.5, 5))
            raise RuntimeError(
                f"WebSocket TLS/connect failed after retries: {type(last_error).__name__}"
            ) from last_error

        first, connect_a, first_a, state_a, session_a, attempts_a, busy_a = await connect(
            first_session,
            "验收A",
        )
        result.update(
            ws_a_connect_ms=connect_a,
            ws_a_first_state_ms=first_a,
            ws_a_connect_attempts=attempts_a,
            ws_a_room_busy_retries=busy_a,
            ws_a_phase=state_a.get("data", {}).get("phase"),
            session_frame_fields=sorted(session_a),
        )
        progress(
            "player_a_connected",
            connect_ms=connect_a,
            first_state_ms=first_a,
            attempts=attempts_a,
        )
        second, connect_b, first_b, state_b, _, attempts_b, busy_b = await connect(
            second_session,
            "验收B",
        )
        first_ready = await receive_json(first)
        result.update(
            ws_b_connect_ms=connect_b,
            ws_b_first_state_ms=first_b,
            ws_b_connect_attempts=attempts_b,
            ws_b_room_busy_retries=busy_b,
            ws_b_phase=state_b.get("data", {}).get("phase"),
            ws_a_after_b_phase=first_ready.get("data", {}).get("phase"),
        )
        progress(
            "player_b_connected",
            connect_ms=connect_b,
            first_state_ms=first_b,
            attempts=attempts_b,
        )

        started = time.perf_counter()
        await first.send(json.dumps({"type": "ping", "game": "gomoku", "data": {}}))
        result["pong"] = (await receive_json(first)).get("type")
        result["ping_ms"] = millis(started)

        started = time.perf_counter()
        token_response = await client.post(
            API + "/api/games/reconnect/token",
            headers=auth,
            json={"room_code": room_code},
        )
        result.update(
            reconnect_token_status=token_response.status_code,
            reconnect_token_ms=millis(started),
        )
        token_response.raise_for_status()
        reconnect_token = token_response.json()["reconnect_token"]
        await first.close()

        started = time.perf_counter()
        recovered = await client.post(
            API + "/api/games/reconnect",
            json={"reconnect_token": reconnect_token},
        )
        result.update(
            http_reconnect_status=recovered.status_code,
            http_reconnect_ms=millis(started),
        )
        recovered.raise_for_status()
        result["http_reconnect_phase"] = recovered.json()["state"].get("phase")
        first, reconnect_connect, reconnect_first, state_a, _, attempts_reconnect, busy_reconnect = (
            await connect(
            first_session,
            "验收A重连",
            )
        )
        result.update(
            ws_reconnect_connect_ms=reconnect_connect,
            ws_reconnect_first_state_ms=reconnect_first,
            ws_reconnect_connect_attempts=attempts_reconnect,
            ws_reconnect_room_busy_retries=busy_reconnect,
            ws_reconnect_phase=state_a.get("data", {}).get("phase"),
        )
        progress(
            "player_a_reconnected",
            connect_ms=reconnect_connect,
            first_state_ms=reconnect_first,
            attempts=attempts_reconnect,
            room_busy_retries=busy_reconnect,
        )
        opponent_reconnect_state = await drain_latest_state(second)
        if opponent_reconnect_state:
            result["opponent_reconnect_phase"] = opponent_reconnect_state.get(
                "data", {}
            ).get("phase")

        async def move(socket, x: int, y: int, minimum_version: int):
            started_move = time.perf_counter()
            await socket.send(
                json.dumps(
                    {"type": "MOVE", "game": "gomoku", "data": {"x": x, "y": y}}
                )
            )
            states = []
            for viewer in (first, second):
                while True:
                    payload = await receive_json(viewer)
                    version = int(payload.get("data", {}).get("state_version") or 0)
                    if payload.get("type") == "state" and version >= minimum_version:
                        states.append(payload)
                        break
            assert states[0]["data"]["state_version"] == states[1]["data"][
                "state_version"
            ]
            return millis(started_move), states[0]

        action_times = []
        final_state = None
        state_version = int(state_a.get("data", {}).get("state_version") or 0)
        black = [(3, 7), (4, 7), (5, 7), (6, 7), (7, 7)]
        white = [(0, 0), (0, 1), (0, 2), (0, 3)]
        for index, black_move in enumerate(black):
            elapsed, final_state = await move(first, *black_move, state_version + 1)
            state_version = int(final_state["data"]["state_version"])
            action_times.append(elapsed)
            progress("move", number=len(action_times), latency_ms=elapsed)
            if index < len(white):
                elapsed, final_state = await move(
                    second,
                    *white[index],
                    state_version + 1,
                )
                state_version = int(final_state["data"]["state_version"])
                action_times.append(elapsed)
                progress("move", number=len(action_times), latency_ms=elapsed)
        result.update(
            actions_ms=action_times,
            action_p50_ms=sorted(action_times)[len(action_times) // 2],
            final_phase=final_state.get("data", {}).get("phase"),
            winner_id_matches=(
                final_state.get("data", {}).get("winner_id")
                == first_session["customer_id"]
            ),
        )
        started = time.perf_counter()
        records = []
        for _ in range(20):
            response = await client.get(API + "/api/games/records/my", headers=auth)
            response.raise_for_status()
            records = [
                item for item in response.json() if item.get("room_code") == room_code
            ]
            if records:
                break
            await asyncio.sleep(0.25)
        result.update(
            settlement_visible_ms=millis(started),
            record_found=bool(records),
            record_settlement=(
                records[0].get("result", {}).get("_settlement") if records else None
            ),
        )
        progress(
            "settled",
            final_phase=result["final_phase"],
            record_found=result["record_found"],
            settlement_visible_ms=result["settlement_visible_ms"],
        )
        await first.close()
        await second.close()
    return result


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))
