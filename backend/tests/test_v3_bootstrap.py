"""V3 bootstrap must aggregate existing contracts without replacing them."""

from fastapi.testclient import TestClient
import pytest

from main import app


@pytest.fixture(autouse=True)
def _customer_invite(monkeypatch) -> None:
    """Keep this module independent from import order in the full test suite."""
    monkeypatch.setenv("CUSTOMER_INVITE_CODE", "test-invite")


def _session_headers(client: TestClient) -> dict[str, str]:
    """Create an isolated customer session through the public compatibility API."""
    response = client.post(
        "/api/customers/session",
        json={
            "invite_code": "test-invite",
            "display_name": "Bootstrap User",
            "device_label": "pytest",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['customer_token']}"}


def test_bootstrap_requires_the_existing_customer_session() -> None:
    """Do not turn the aggregation endpoint into an authentication bypass."""
    with TestClient(app) as client:
        response = client.get("/api/bootstrap")
        assert response.status_code == 401


def test_bootstrap_matches_the_three_existing_home_endpoints() -> None:
    """Guarantee additive API behavior while the mini program can still fall back."""
    with TestClient(app) as client:
        headers = _session_headers(client)
        bootstrap = client.get("/api/bootstrap", headers=headers)
        dishes = client.get("/api/dishes", headers=headers)
        ranking = client.get("/api/stats/favorite-ranking", headers=headers)
        score = client.get("/api/couple/score", headers=headers)
        assert bootstrap.status_code == 200
        assert bootstrap.json() == {
            "dishes": dishes.json(),
            "favorite_ranking": ranking.json(),
            "couple_score": score.json(),
        }


def test_game_room_factory_accepts_legacy_plugin_aliases() -> None:
    """Route old vocabulary through the registry while persisting canonical types."""
    with TestClient(app) as client:
        headers = _session_headers(client)
        response = client.post(
            "/api/games/rooms",
            headers=headers,
            json={
                "game_type": "flight",
                "creator": "ignored",
                "invite_code": "test-invite",
            },
        )
        assert response.status_code == 201
        assert response.json()["game_type"] == "aeroplane"
