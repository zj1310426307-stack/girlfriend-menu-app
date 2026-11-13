"""WebSocket-level coverage for gomoku undo/draw negotiation."""
from fastapi.testclient import TestClient

from test_api import app


def _join(player_id, name):
    return {
        "type": "join",
        "game": "gomoku",
        "data": {"player_id": player_id, "name": name, "invite_code": "test-invite"},
    }


def _send(socket, action):
    socket.send_json({"type": action, "game": "gomoku", "data": {}})


def _receive_pair(first, second):
    first_state = first.receive_json()
    second_state = second.receive_json()
    assert first_state["type"] == second_state["type"] == "state"
    return first_state["data"], second_state["data"]


def _open_room(client, room_game, first_id, first_name, second_id, second_name):
    created = client.post(
        "/api/games/rooms",
        json={"game_type": room_game, "creator": first_id, "invite_code": "test-invite"},
    )
    assert created.status_code == 201
    return created.json()["room_code"]


def test_gomoku_socket_undo_offer_accept_reverts_board():
    first_id = "gf_undo_black"
    second_id = "gf_undo_white"
    with TestClient(app) as client:
        room_code = _open_room(client, "gomoku", first_id, "我", second_id, "女朋友")
        with client.websocket_connect(f"/ws/game/{room_code}") as first:
            first.send_json(_join(first_id, "我"))
            first.receive_json()
            with client.websocket_connect(f"/ws/game/{room_code}") as second:
                second.send_json(_join(second_id, "女朋友"))
                _receive_pair(first, second)

                first.send_json({"type": "move", "game": "gomoku", "data": {"x": 7, "y": 7}})
                _receive_pair(first, second)

                _send(first, "undo_offer")
                offer_first, offer_second = _receive_pair(first, second)
                assert offer_first["negotiation"] == {"type": "undo", "by": first_id}
                assert offer_second["negotiation"] == {"type": "undo", "by": first_id}

                _send(second, "undo_accept")
                done_first, done_second = _receive_pair(first, second)
                assert done_first["negotiation"] is None
                assert done_first["move_count"] == 0
                assert done_first["board"][7][7] == 0
                assert done_first["turn_id"] == first_id
                assert done_second["move_count"] == 0


def test_gomoku_socket_draw_agreement_finishes_round():
    first_id = "gf_draw_black"
    second_id = "gf_draw_white"
    with TestClient(app) as client:
        room_code = _open_room(client, "gomoku", first_id, "我", second_id, "女朋友")
        with client.websocket_connect(f"/ws/game/{room_code}") as first:
            first.send_json(_join(first_id, "我"))
            first.receive_json()
            with client.websocket_connect(f"/ws/game/{room_code}") as second:
                second.send_json(_join(second_id, "女朋友"))
                _receive_pair(first, second)

                _send(second, "draw_offer")
                _receive_pair(first, second)
                _send(first, "draw_accept")
                first_state, second_state = _receive_pair(first, second)

                assert first_state["phase"] == "finished"
                assert first_state["winner_id"] is None
                assert first_state["is_draw"] is True
                assert first_state["outcome"]["is_draw"] is True
                assert second_state["phase"] == "finished"


def test_gomoku_socket_offer_requires_opponent():
    first_id = "gf_self_black"
    second_id = "gf_self_white"
    with TestClient(app) as client:
        room_code = _open_room(client, "gomoku", first_id, "我", second_id, "女朋友")
        with client.websocket_connect(f"/ws/game/{room_code}") as first:
            first.send_json(_join(first_id, "我"))
            first.receive_json()
            with client.websocket_connect(f"/ws/game/{room_code}") as second:
                second.send_json(_join(second_id, "女朋友"))
                _receive_pair(first, second)

                first.send_json({"type": "move", "game": "gomoku", "data": {"x": 5, "y": 5}})
                _receive_pair(first, second)

                _send(first, "undo_offer")
                _receive_pair(first, second)

                # The offerer cannot accept their own request.
                _send(first, "undo_accept")
                rejected = first.receive_json()
                assert rejected["type"] == "error"
                assert "对方" in rejected["message"]
