"""Production WeChat identity binding and compatibility recovery contracts."""

from __future__ import annotations

from fastapi.testclient import TestClient

from integrations.wechat import WeChatIdentity
import models
from services import wechat_auth_service
from test_api import app
from database import SessionLocal


def _login(client: TestClient, code: str, invite_code: str = ""):
    """Call the public endpoint with one synthetic temporary login code."""
    return client.post(
        "/api/customers/wechat-session",
        json={
            "code": code,
            "invite_code": invite_code,
            "display_name": "她",
            "device_label": "微信测试设备",
        },
    )


def test_first_wechat_login_requires_invite_and_never_stores_session_key(monkeypatch):
    """Authorize a new private-app identity once, then persist only durable IDs."""
    monkeypatch.setattr(
        wechat_auth_service,
        "exchange_login_code",
        lambda code: WeChatIdentity("wx-test-app", f"openid-{code}", "union-one"),
    )
    with TestClient(app) as client:
        assert _login(client, "first").status_code == 401
        created = _login(client, "first", "test-invite")
        assert created.status_code == 200
        session = created.json()
        assert client.get(
            "/api/orders/me",
            headers={"Authorization": f"Bearer {session['customer_token']}"},
        ).status_code == 200

    with SessionLocal() as db:
        identity = db.query(models.WeChatUser).filter_by(openid="openid-first").one()
        assert identity.customer_id == session["customer_id"]
        assert identity.unionid == "union-one"
        assert not hasattr(identity, "session_key")


def test_bound_wechat_login_restores_same_customer_on_another_phone(monkeypatch):
    """Issue independent active sessions so changing phones does not lose history."""
    monkeypatch.setattr(
        wechat_auth_service,
        "exchange_login_code",
        lambda code: WeChatIdentity("wx-test-app", "stable-openid"),
    )
    with TestClient(app) as client:
        first = _login(client, "phone-one", "test-invite").json()
        second_response = _login(client, "phone-two")
        assert second_response.status_code == 200
        second = second_response.json()
        assert second["customer_id"] == first["customer_id"]
        assert second["customer_token"] != first["customer_token"]
        for session in (first, second):
            assert client.get(
                "/api/orders/me",
                headers={"Authorization": f"Bearer {session['customer_token']}"},
            ).status_code == 200

    with SessionLocal() as db:
        assert db.query(models.WeChatUser).filter_by(openid="stable-openid").count() == 1
        assert db.query(models.CustomerSession).filter_by(
            customer_id=first["customer_id"],
            revoked_at=None,
        ).count() == 2


def test_existing_device_customer_is_bound_in_place(monkeypatch):
    """Upgrade a pre-WeChat session without splitting its orders or identity."""
    monkeypatch.setattr(
        wechat_auth_service,
        "exchange_login_code",
        lambda code: WeChatIdentity("wx-test-app", "upgrade-openid"),
    )
    with TestClient(app) as client:
        legacy = client.post(
            "/api/customers/session",
            json={
                "invite_code": "test-invite",
                "display_name": "存量用户",
                "device_label": "旧设备",
            },
        ).json()
        response = client.post(
            "/api/customers/wechat-session",
            headers={"Authorization": f"Bearer {legacy['customer_token']}"},
            json={
                "code": "bind-current",
                "display_name": "不会新建",
                "device_label": "微信小程序",
            },
        )
        assert response.status_code == 200
        bound = response.json()
        assert bound["customer_id"] == legacy["customer_id"]
        assert bound["customer_token"] != legacy["customer_token"]
        for session in (legacy, bound):
            assert client.get(
                "/api/orders/me",
                headers={"Authorization": f"Bearer {session['customer_token']}"},
            ).status_code == 200

    with SessionLocal() as db:
        identity = db.query(models.WeChatUser).filter_by(openid="upgrade-openid").one()
        assert identity.customer_id == legacy["customer_id"]
        assert db.query(models.Customer).filter_by(id=legacy["customer_id"]).count() == 1


def test_wechat_login_is_release_gated_when_server_credentials_are_disabled(monkeypatch):
    """Fail safely without contacting WeChat or exposing a configuration secret."""
    monkeypatch.setenv("WECHAT_LOGIN_ENABLED", "false")
    with TestClient(app) as client:
        response = _login(client, "unused", "test-invite")
    assert response.status_code == 503
    assert response.json()["detail"] == "微信登录尚未启用"
