"""Server-only adapter for the official WeChat code2Session endpoint."""

from __future__ import annotations

from dataclasses import dataclass
import json
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from core.settings import load_settings


CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"


class WeChatLoginError(RuntimeError):
    """Base error carrying a safe public status and message."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class WeChatIdentity:
    """Keep only durable identity fields and deliberately discard session_key."""

    app_id: str
    openid: str
    unionid: str | None = None


def exchange_login_code(code: str) -> WeChatIdentity:
    """Exchange one temporary mini-program code at the official server endpoint."""
    normalized_code = code.strip()
    if not normalized_code:
        raise WeChatLoginError(422, "微信登录凭证不能为空")
    try:
        app_id, app_secret = load_settings().require_wechat_login()
    except RuntimeError as error:
        raise WeChatLoginError(503, "微信登录尚未启用") from error
    query = urlencode({
        "appid": app_id,
        "secret": app_secret,
        "js_code": normalized_code,
        "grant_type": "authorization_code",
    })
    request = Request(f"{CODE2SESSION_URL}?{query}", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - fixed HTTPS endpoint.
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, socket.timeout, json.JSONDecodeError) as error:
        raise WeChatLoginError(503, "微信登录服务暂时不可用") from error

    if not isinstance(payload, dict):
        raise WeChatLoginError(503, "微信登录服务暂时不可用")
    try:
        error_code = int(payload.get("errcode") or 0)
    except (TypeError, ValueError) as error:
        raise WeChatLoginError(503, "微信登录服务暂时不可用") from error
    if error_code == 40029:
        raise WeChatLoginError(401, "微信登录凭证已失效，请重试")
    if error_code in {45011, 40226}:
        raise WeChatLoginError(429, "微信登录请求过于频繁，请稍后重试")
    openid = payload.get("openid")
    unionid = payload.get("unionid")
    if (
        error_code
        or not isinstance(openid, str)
        or not openid.strip()
        or (unionid is not None and not isinstance(unionid, str))
    ):
        raise WeChatLoginError(503, "微信登录服务暂时不可用")
    return WeChatIdentity(
        app_id=app_id,
        openid=openid.strip(),
        unionid=unionid.strip() if unionid else None,
    )


__all__ = ["WeChatIdentity", "WeChatLoginError", "exchange_login_code"]
