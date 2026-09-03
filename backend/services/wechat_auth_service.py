"""Bind official WeChat identities to existing LoveOS customer sessions."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

import customer_service
from integrations.wechat import WeChatLoginError, exchange_login_code
import models


def _identity_query(db: Session, app_id: str, openid: str):
    """Build the one eager query used by normal and concurrent login paths."""
    return (
        db.query(models.WeChatUser)
        .options(joinedload(models.WeChatUser.customer))
        .filter(
            models.WeChatUser.app_id == app_id,
            models.WeChatUser.openid == openid,
        )
    )


def _issue_existing_session(
    db: Session,
    identity: models.WeChatUser,
    unionid: str | None,
    device_label: str | None,
) -> dict:
    """Issue a new phone session while keeping other active devices signed in."""
    customer = identity.customer
    if not customer or not customer.is_active:
        raise HTTPException(status_code=403, detail="微信账号绑定的用户已停用")
    now = customer_service.utc_now()
    identity.last_login_at = now
    if unionid and not identity.unionid:
        identity.unionid = unionid
    customer.last_seen_at = now
    token, session = customer_service.stage_customer_session(
        db,
        customer,
        device_label,
    )
    db.commit()
    return customer_service.session_payload(customer, token, session.expires_at)


def login_with_wechat(
    db: Session,
    code: str,
    invite_code: str,
    display_name: str,
    device_label: str | None,
    current_customer: models.Customer | None = None,
) -> dict:
    """Restore, bind, or atomically create one durable WeChat identity."""
    try:
        exchanged = exchange_login_code(code)
    except WeChatLoginError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error

    identity = _identity_query(db, exchanged.app_id, exchanged.openid).first()
    if identity:
        if current_customer and identity.customer_id != current_customer.id:
            raise HTTPException(status_code=409, detail="该微信账号已绑定其他用户")
        return _issue_existing_session(db, identity, exchanged.unionid, device_label)

    if current_customer:
        current_identity = (
            db.query(models.WeChatUser)
            .filter(models.WeChatUser.customer_id == current_customer.id)
            .first()
        )
        if current_identity:
            raise HTTPException(status_code=409, detail="当前用户已绑定其他微信账号")
        identity = models.WeChatUser(
            customer=current_customer,
            app_id=exchanged.app_id,
            openid=exchanged.openid,
            unionid=exchanged.unionid,
            last_login_at=customer_service.utc_now(),
        )
        db.add(identity)
        token, session = customer_service.stage_customer_session(
            db,
            current_customer,
            device_label,
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            identity = _identity_query(db, exchanged.app_id, exchanged.openid).first()
            if not identity:
                raise HTTPException(status_code=409, detail="当前用户已绑定其他微信账号")
            if identity.customer_id != current_customer.id:
                raise HTTPException(status_code=409, detail="该微信账号已绑定其他用户")
            return _issue_existing_session(db, identity, exchanged.unionid, device_label)
        return customer_service.session_payload(
            current_customer,
            token,
            session.expires_at,
        )

    if not invite_code.strip():
        raise HTTPException(status_code=401, detail="首次微信登录请输入邀请码")
    customer_service.verify_invite(invite_code)

    customer, token, session = customer_service.stage_new_customer(
        db,
        display_name,
        device_label,
    )
    db.add(models.WeChatUser(
        customer=customer,
        app_id=exchanged.app_id,
        openid=exchanged.openid,
        unionid=exchanged.unionid,
        last_login_at=customer_service.utc_now(),
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        identity = _identity_query(db, exchanged.app_id, exchanged.openid).first()
        if not identity:
            raise HTTPException(status_code=503, detail="微信身份绑定暂时失败")
        return _issue_existing_session(db, identity, exchanged.unionid, device_label)
    return customer_service.session_payload(customer, token, session.expires_at)


__all__ = ["login_with_wechat"]
