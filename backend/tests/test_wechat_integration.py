"""Official code2Session adapter contracts without external network access."""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

import pytest

from integrations import wechat


class _Response:
    def __init__(self, payload: dict):
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return self.body


def _enable(monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_LOGIN_ENABLED", "true")
    monkeypatch.setenv("WECHAT_APP_ID", "wx-official-test")
    monkeypatch.setenv("WECHAT_APP_SECRET", "server-only-secret")


def test_code2session_uses_fixed_https_endpoint_and_discards_session_key(monkeypatch):
    """Send the documented fields while returning only durable identity values."""
    _enable(monkeypatch)
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return _Response({
            "openid": "openid-one",
            "unionid": "union-one",
            "session_key": "must-never-leave-adapter",
        })

    monkeypatch.setattr(wechat, "urlopen", fake_urlopen)
    identity = wechat.exchange_login_code("temporary-code")
    target = urlsplit(captured["url"])
    query = parse_qs(target.query)
    assert f"{target.scheme}://{target.netloc}{target.path}" == wechat.CODE2SESSION_URL
    assert captured["timeout"] == 5
    assert query == {
        "appid": ["wx-official-test"],
        "secret": ["server-only-secret"],
        "js_code": ["temporary-code"],
        "grant_type": ["authorization_code"],
    }
    assert identity == wechat.WeChatIdentity(
        app_id="wx-official-test",
        openid="openid-one",
        unionid="union-one",
    )
    assert not hasattr(identity, "session_key")


@pytest.mark.parametrize(
    ("error_code", "status_code"),
    [(40029, 401), (40226, 429), (45011, 429), (-1, 503)],
)
def test_code2session_error_codes_are_safe_and_actionable(
    monkeypatch,
    error_code,
    status_code,
):
    """Normalize official/transient failures without exposing upstream payloads."""
    _enable(monkeypatch)
    monkeypatch.setattr(
        wechat,
        "urlopen",
        lambda request, timeout: _Response({
            "errcode": error_code,
            "errmsg": "upstream-private-detail",
        }),
    )
    with pytest.raises(wechat.WeChatLoginError) as caught:
        wechat.exchange_login_code("temporary-code")
    assert caught.value.status_code == status_code
    assert "upstream-private-detail" not in caught.value.message


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"errcode": "not-a-number"},
        {"openid": {"unexpected": "object"}},
        {"openid": "openid-one", "unionid": ["unexpected"]},
    ],
)
def test_code2session_rejects_malformed_success_payloads(monkeypatch, payload):
    """Map malformed upstream JSON to one safe service error instead of a 500."""
    _enable(monkeypatch)
    monkeypatch.setattr(
        wechat,
        "urlopen",
        lambda request, timeout: _Response(payload),
    )
    with pytest.raises(wechat.WeChatLoginError) as caught:
        wechat.exchange_login_code("temporary-code")
    assert caught.value.status_code == 503
    assert caught.value.message == "微信登录服务暂时不可用"
