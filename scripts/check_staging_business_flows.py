"""Run credential-safe, write-path acceptance against isolated hosted staging.

The gate refuses the production API origin, reads credentials from environment
variables or one bounded JSON object on stdin, and never prints credentials,
tokens, customer identities, order IDs, room codes, or uploaded image URLs.
Synthetic staging records are deliberately retained as auditable evidence.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
from dataclasses import dataclass
from getpass import getpass
import json
import os
from pathlib import Path
import sys
import time
import uuid

import httpx
from websockets.asyncio.client import connect as websocket_connect
from websockets.exceptions import ConnectionClosed

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_staging_readiness import (
    StagingReadinessError,
    _dotenv_value,
    _safe_target_ref,
    validate_staging_origin,
)


ROOT = SCRIPT_DIR.parent
DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_CREDENTIAL_BYTES = 4096
PNG_FIXTURE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFElEQVR4nGPs3zmNARtgwio6"
    "aCUAeMQB7lt4eBwAAAAASUVORK5CYII="
)


class StagingAcceptanceError(RuntimeError):
    """Describe one safe acceptance failure without secret-bearing context."""


@dataclass(frozen=True, repr=False)
class Credentials:
    admin_password: str
    admin_invite_code: str
    customer_invite_code: str


def _credentials_from_payload(payload: object) -> Credentials:
    if not isinstance(payload, dict):
        raise StagingAcceptanceError("credential input must be a JSON object")
    credentials = Credentials(
        admin_password=str(payload.get("admin_password") or ""),
        admin_invite_code=str(payload.get("admin_invite_code") or ""),
        customer_invite_code=str(payload.get("customer_invite_code") or ""),
    )
    values = (
        credentials.admin_password,
        credentials.admin_invite_code,
        credentials.customer_invite_code,
    )
    if any(not value or len(value) > 200 for value in values):
        raise StagingAcceptanceError("all staging credentials must be present and bounded")
    if credentials.admin_invite_code == credentials.customer_invite_code:
        raise StagingAcceptanceError("admin and customer invites must be distinct")
    return credentials


def _read_credentials(*, from_stdin: bool) -> Credentials:
    if from_stdin:
        if sys.stdin.isatty():
            raw = getpass("").encode("utf-8")
        else:
            raw = sys.stdin.buffer.readline(MAX_CREDENTIAL_BYTES + 1)
        if len(raw) > MAX_CREDENTIAL_BYTES:
            raise StagingAcceptanceError("credential input exceeded the size limit")
        try:
            return _credentials_from_payload(json.loads(raw))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise StagingAcceptanceError("credential input is not valid JSON") from error
    return _credentials_from_payload(
        {
            "admin_password": os.getenv("ADMIN_PASSWORD", ""),
            "admin_invite_code": os.getenv("ADMIN_INVITE_CODE", ""),
            "customer_invite_code": os.getenv("CUSTOMER_INVITE_CODE", ""),
        }
    )


def _progress(stage: str, **safe_fields: object) -> None:
    print(json.dumps({"stage": stage, **safe_fields}, ensure_ascii=False), flush=True)


def _expect_status(response: httpx.Response, expected: int | set[int], label: str) -> None:
    allowed = {expected} if isinstance(expected, int) else expected
    if response.status_code not in allowed:
        raise StagingAcceptanceError(
            f"{label} returned unexpected HTTP {response.status_code}"
        )


def _json(response: httpx.Response, label: str) -> object:
    try:
        return response.json()
    except json.JSONDecodeError as error:
        raise StagingAcceptanceError(f"{label} returned invalid JSON") from error


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _receive_json(socket, timeout: float) -> dict:
    try:
        payload = json.loads(await asyncio.wait_for(socket.recv(), timeout))
    except (asyncio.TimeoutError, ConnectionClosed, json.JSONDecodeError) as error:
        raise StagingAcceptanceError(
            f"WebSocket receive failed ({type(error).__name__})"
        ) from error
    if not isinstance(payload, dict):
        raise StagingAcceptanceError("WebSocket frame must be a JSON object")
    return payload


async def _admin_websocket(origin: str, token: str, timeout: float) -> None:
    websocket_origin = origin.replace("https://", "wss://", 1)
    try:
        async with websocket_connect(
            f"{websocket_origin}/ws/admin/orders",
            open_timeout=timeout,
            close_timeout=10,
            ping_interval=10,
            ping_timeout=20,
            max_size=2**20,
        ) as socket:
            await socket.send(json.dumps({"type": "auth", "token": token}))
            ready = await _receive_json(socket, timeout)
            if ready.get("type") != "ready":
                raise StagingAcceptanceError("admin WebSocket did not become ready")
            await socket.send(json.dumps({"type": "ping"}))
            pong = await _receive_json(socket, timeout)
            if pong.get("type") != "pong":
                raise StagingAcceptanceError("admin WebSocket ping failed")
    except StagingAcceptanceError:
        raise
    except Exception as error:
        raise StagingAcceptanceError(
            f"admin WebSocket failed ({type(error).__name__})"
        ) from error


async def _connect_game(
    websocket_origin: str,
    room_code: str,
    token: str,
    player_name: str,
    timeout: float,
):
    try:
        socket = await websocket_connect(
            f"{websocket_origin}/ws/game/{room_code}",
            open_timeout=timeout,
            close_timeout=10,
            ping_interval=10,
            ping_timeout=20,
            max_size=2**20,
        )
        await socket.send(
            json.dumps(
                {
                    "type": "join",
                    "game": "gomoku",
                    "data": {"customer_token": token, "name": player_name},
                },
                ensure_ascii=False,
            )
        )
        first = await _receive_json(socket, timeout)
        if first.get("type") != "state":
            await socket.close()
            raise StagingAcceptanceError("game WebSocket did not return initial state")
        session = await _receive_json(socket, timeout)
        if session.get("type") != "session":
            await socket.close()
            raise StagingAcceptanceError("game WebSocket did not issue room session")
        return socket, first
    except StagingAcceptanceError:
        raise
    except Exception as error:
        raise StagingAcceptanceError(
            f"game WebSocket connect failed ({type(error).__name__})"
        ) from error


async def _game_websocket(
    client: httpx.AsyncClient,
    origin: str,
    first_session: dict,
    second_session: dict,
    timeout: float,
) -> None:
    first_headers = _bearer(str(first_session["customer_token"]))
    created = await client.post(
        "/api/games/rooms",
        headers=first_headers,
        json={
            "game_type": "gomoku",
            "creator": first_session["customer_id"],
            "mode": "couple",
            "difficulty": "rule",
            "invite_code": "",
        },
    )
    _expect_status(created, 201, "game room create")
    room = _json(created, "game room create")
    if not isinstance(room, dict) or not room.get("room_code"):
        raise StagingAcceptanceError("game room response is incomplete")
    room_code = str(room["room_code"])
    websocket_origin = origin.replace("https://", "wss://", 1)
    first = second = None
    try:
        first, first_state = await _connect_game(
            websocket_origin,
            room_code,
            str(first_session["customer_token"]),
            "staging-A",
            timeout,
        )
        second, _ = await _connect_game(
            websocket_origin,
            room_code,
            str(second_session["customer_token"]),
            "staging-B",
            timeout,
        )
        await _receive_json(first, timeout)
        await first.send(json.dumps({"type": "ping", "game": "gomoku", "data": {}}))
        if (await _receive_json(first, timeout)).get("type") != "pong":
            raise StagingAcceptanceError("game WebSocket ping failed")

        initial_version = int(first_state.get("data", {}).get("state_version") or 0)
        await first.send(
            json.dumps({"type": "MOVE", "game": "gomoku", "data": {"x": 3, "y": 7}})
        )
        first_move = await _receive_json(first, timeout)
        second_view = await _receive_json(second, timeout)
        versions = {
            int(first_move.get("data", {}).get("state_version") or 0),
            int(second_view.get("data", {}).get("state_version") or 0),
        }
        if len(versions) != 1 or min(versions) <= initial_version:
            raise StagingAcceptanceError("game WebSocket state did not converge")

        reconnect = await client.post(
            "/api/games/reconnect/token",
            headers=first_headers,
            json={"room_code": room_code},
        )
        _expect_status(reconnect, 200, "game reconnect token")
        reconnect_payload = _json(reconnect, "game reconnect token")
        if not isinstance(reconnect_payload, dict) or not reconnect_payload.get(
            "reconnect_token"
        ):
            raise StagingAcceptanceError("game reconnect token response is incomplete")
        await first.close()
        first = None
        recovered = await client.post(
            "/api/games/reconnect",
            json={"reconnect_token": reconnect_payload["reconnect_token"]},
        )
        _expect_status(recovered, 200, "game HTTP reconnect")
    finally:
        if first is not None:
            await first.close()
        if second is not None:
            await second.close()


async def run_acceptance(
    origin: str,
    credentials: Credentials,
    *,
    timeout: float,
) -> dict[str, object]:
    run_ref = uuid.uuid4().hex[:8]
    checks: list[str] = []
    started = time.perf_counter()
    async with httpx.AsyncClient(
        base_url=origin,
        timeout=timeout,
        follow_redirects=False,
        headers={"Accept": "application/json", "User-Agent": "loveos-staging-acceptance/1"},
    ) as client:
        health = await client.get("/api/health")
        _expect_status(health, 200, "health")
        health_payload = _json(health, "health")
        if not isinstance(health_payload, dict) or health_payload.get("status") != "ok":
            raise StagingAcceptanceError("health payload is not healthy")
        ready = await client.get("/api/ready")
        _expect_status(ready, 200, "readiness")
        ready_payload = _json(ready, "readiness")
        if not isinstance(ready_payload, dict) or ready_payload.get("status") != "ready":
            raise StagingAcceptanceError("staging readiness is not ready")
        checks.append("health_readiness")
        _progress("health_readiness", status="pass")

        sessions: list[dict] = []
        for label in ("A", "B"):
            response = await client.post(
                "/api/customers/session",
                json={
                    "invite_code": credentials.customer_invite_code,
                    "display_name": f"Staging验收{label}-{run_ref}",
                    "device_label": "Codex hosted acceptance",
                },
            )
            _expect_status(response, 200, f"customer session {label}")
            payload = _json(response, f"customer session {label}")
            if not isinstance(payload, dict) or not payload.get("customer_token"):
                raise StagingAcceptanceError("customer session response is incomplete")
            sessions.append(payload)
        first_session, second_session = sessions
        first_headers = _bearer(str(first_session["customer_token"]))
        second_headers = _bearer(str(second_session["customer_token"]))
        bootstrap = await client.get("/api/bootstrap", headers=first_headers)
        _expect_status(bootstrap, 200, "authenticated bootstrap")
        checks.append("customer_session_bootstrap")
        _progress("customer_session_bootstrap", status="pass")

        legacy_id = f"stglegacy{uuid.uuid4().hex[:16]}"
        claimed = await client.post(
            "/api/customers/claim-legacy",
            json={
                "invite_code": credentials.customer_invite_code,
                "legacy_customer_id": legacy_id,
                "display_name": f"Staging恢复-{run_ref}",
                "device_label": "staging old device",
            },
        )
        _expect_status(claimed, 200, "legacy claim")
        claim_payload = _json(claimed, "legacy claim")
        recovered = await client.post(
            "/api/customers/recover",
            json={
                "invite_code": credentials.customer_invite_code,
                "legacy_customer_id": legacy_id,
                "display_name": f"Staging恢复-{run_ref}",
                "device_label": "staging replacement device",
            },
        )
        _expect_status(recovered, 200, "legacy recovery")
        recovery_payload = _json(recovered, "legacy recovery")
        if not isinstance(claim_payload, dict) or not isinstance(recovery_payload, dict):
            raise StagingAcceptanceError("legacy recovery response is incomplete")
        if claim_payload.get("customer_id") != recovery_payload.get("customer_id"):
            raise StagingAcceptanceError("legacy recovery did not preserve identity")
        old_session = await client.get(
            "/api/bootstrap",
            headers=_bearer(str(claim_payload.get("customer_token") or "")),
        )
        _expect_status(old_session, 401, "replaced device session")
        checks.append("legacy_recovery_rotation")
        _progress("legacy_recovery_rotation", status="pass")

        dishes_response = await client.get("/api/dishes")
        _expect_status(dishes_response, 200, "dish catalogue")
        dishes = _json(dishes_response, "dish catalogue")
        if not isinstance(dishes, list) or not dishes:
            raise StagingAcceptanceError("dish catalogue is empty")
        dish_id = int(dishes[0]["id"])
        favorite = await client.post(f"/api/favorites/{dish_id}", headers=first_headers)
        _expect_status(favorite, 200, "favorite add")
        favorite_list = await client.get("/api/favorites", headers=first_headers)
        _expect_status(favorite_list, 200, "favorite list")
        favorite_items = _json(favorite_list, "favorite list")
        if not isinstance(favorite_items, list) or not any(
            int(item.get("id") or 0) == dish_id for item in favorite_items
        ):
            raise StagingAcceptanceError("favorite mutation was not visible")
        removed = await client.delete(f"/api/favorites/{dish_id}", headers=first_headers)
        _expect_status(removed, 204, "favorite remove")
        checks.append("catalogue_favorites")
        _progress("catalogue_favorites", status="pass")

        admin_login = await client.post(
            "/api/admin/login",
            json={
                "password": credentials.admin_password,
                "invite_code": credentials.admin_invite_code,
            },
        )
        _expect_status(admin_login, 200, "admin login")
        admin_payload = _json(admin_login, "admin login")
        if not isinstance(admin_payload, dict) or not admin_payload.get("token"):
            raise StagingAcceptanceError("admin login response is incomplete")
        admin_token = str(admin_payload["token"])
        admin_headers = _bearer(admin_token)
        await _admin_websocket(origin, admin_token, timeout)
        checks.append("admin_auth_websocket")
        _progress("admin_auth_websocket", status="pass")

        upload = await client.post(
            "/api/upload/image",
            headers=admin_headers,
            files={"file": ("staging-acceptance.png", PNG_FIXTURE, "image/png")},
        )
        _expect_status(upload, 200, "image upload")
        upload_payload = _json(upload, "image upload")
        if not isinstance(upload_payload, dict) or not upload_payload.get("image_url"):
            raise StagingAcceptanceError("image upload response is incomplete")
        image = await client.get(str(upload_payload["image_url"]))
        _expect_status(image, 200, "image download")
        if not image.content.startswith(b"\x89PNG"):
            raise StagingAcceptanceError("stored image content is invalid")
        checks.append("durable_image")
        _progress("durable_image", status="pass")

        async def create_order(suffix: str) -> dict:
            response = await client.post(
                "/api/orders",
                headers=first_headers,
                json={
                    "items": [{"dish_id": dish_id, "quantity": 1}],
                    "note": f"Staging验收-{run_ref}-{suffix}",
                    "desired_time": "staging acceptance",
                    "idempotency_key": f"stg-{uuid.uuid4().hex}",
                },
            )
            _expect_status(response, 201, f"order create {suffix}")
            payload = _json(response, f"order create {suffix}")
            if not isinstance(payload, dict) or not payload.get("id"):
                raise StagingAcceptanceError("order response is incomplete")
            return payload

        order = await create_order("complete")
        order_id = int(order["id"])
        cross_owner = await client.get(f"/api/orders/{order_id}", headers=second_headers)
        _expect_status(cross_owner, 404, "cross-customer order isolation")
        preview = await client.post(
            f"/api/orders/{order_id}/repeat-preview", headers=first_headers
        )
        _expect_status(preview, 200, "repeat order preview")
        status_value = "待接单"
        for next_status in ("已接单", "制作中", "已完成"):
            changed = await client.patch(
                f"/api/orders/{order_id}/status",
                headers=admin_headers,
                json={"status": next_status, "expected_status": status_value},
            )
            _expect_status(changed, 200, f"order status {next_status}")
            status_value = next_status
        review = await client.post(
            f"/api/orders/{order_id}/review",
            headers=first_headers,
            json={"rating": 5, "want_again": "想吃", "comment": "staging acceptance"},
        )
        _expect_status(review, 201, "order review")
        admin_page = await client.get(
            "/api/admin/orders?limit=5", headers=admin_headers
        )
        _expect_status(admin_page, 200, "admin order page")

        rollback_order = await create_order("rollback")
        rollback_id = int(rollback_order["id"])
        accepted = await client.patch(
            f"/api/orders/{rollback_id}/status",
            headers=admin_headers,
            json={"status": "已接单", "expected_status": "待接单"},
        )
        _expect_status(accepted, 200, "rollback order forward status")
        rolled_back = await client.post(
            f"/api/admin/orders/{rollback_id}/rollback",
            headers=admin_headers,
            json={"expected_status": "已接单"},
        )
        _expect_status(rolled_back, 200, "order rollback")
        rollback_payload = _json(rolled_back, "order rollback")
        if not isinstance(rollback_payload, dict) or rollback_payload.get("status") != "待接单":
            raise StagingAcceptanceError("order rollback did not restore previous status")
        checks.append("orders_review_rollback")
        _progress("orders_review_rollback", status="pass")

        await _game_websocket(
            client,
            origin,
            first_session,
            second_session,
            timeout,
        )
        checks.append("game_websocket_reconnect")
        _progress("game_websocket_reconnect", status="pass")

    return {
        "status": "pass",
        "target_ref": _safe_target_ref(origin),
        "checks": checks,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "wechat_real_credentials": "pending",
        "physical_device": "pending",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run authenticated write-path acceptance against isolated staging."
    )
    parser.add_argument(
        "--credentials-stdin",
        action="store_true",
        help="Read one JSON credential object from stdin instead of environment variables.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-operation timeout in seconds (default: 60).",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.timeout <= 0 or args.timeout > 120:
        print("staging business acceptance failed: timeout must be between 0 and 120 seconds")
        return 2
    production_origin = _dotenv_value(
        ROOT / "miniprogram" / ".env.production", "TARO_APP_API_ORIGIN"
    )
    try:
        origin = validate_staging_origin(
            os.getenv("STAGING_API_ORIGIN", ""), production_origin
        )
        credentials = _read_credentials(from_stdin=args.credentials_stdin)
        summary = asyncio.run(
            run_acceptance(origin, credentials, timeout=args.timeout)
        )
    except (StagingReadinessError, StagingAcceptanceError) as error:
        print(f"staging business acceptance failed: {error}")
        return 1
    except Exception as error:
        print(
            "staging business acceptance failed: "
            f"unexpected {type(error).__name__}"
        )
        return 1
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
