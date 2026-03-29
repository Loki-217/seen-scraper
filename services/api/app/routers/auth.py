# services/api/app/routers/auth.py
"""Auth 路由：注册、登录、刷新 Token、获取当前用户"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)
from ..db import session_scope
from ..models import UserDB, InviteCodeDB

router = APIRouter(prefix="/auth", tags=["auth"])

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,30}$")


# ---------- Request / Response models ----------

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    invite_code: str


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------- POST /auth/register ----------

@router.post("/register", status_code=201)
def register(req: RegisterRequest):
    if not _USERNAME_RE.match(req.username):
        raise HTTPException(
            status_code=422,
            detail="Username must be 3-30 characters, letters/numbers/underscore only",
        )
    if len(req.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    with session_scope() as s:
        # Validate invite code
        invite = s.execute(
            select(InviteCodeDB).where(InviteCodeDB.code == req.invite_code)
        ).scalar_one_or_none()

        if invite is None:
            raise HTTPException(status_code=400, detail="Invalid invite code")
        if invite.used_by is not None:
            raise HTTPException(status_code=400, detail="Invite code already used")
        if invite.expires_at and invite.expires_at < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Invite code expired")

        # Check uniqueness
        existing_username = s.execute(
            select(UserDB).where(UserDB.username == req.username)
        ).scalar_one_or_none()
        if existing_username:
            raise HTTPException(status_code=409, detail="Username already exists")

        existing_email = s.execute(
            select(UserDB).where(UserDB.email == req.email)
        ).scalar_one_or_none()
        if existing_email:
            raise HTTPException(status_code=409, detail="Email already registered")

        # Create user
        user_id = str(uuid.uuid4())
        user = UserDB(
            id=user_id,
            username=req.username,
            email=req.email,
            hashed_password=hash_password(req.password),
        )
        s.add(user)

        # Mark invite code used
        invite.used_by = user_id
        invite.used_at = datetime.utcnow()

    return {"user_id": user_id, "username": req.username, "message": "Registration successful"}


# ---------- POST /auth/login ----------

@router.post("/login")
def login(req: LoginRequest):
    with session_scope() as s:
        user = s.execute(
            select(UserDB).where(UserDB.username == req.username)
        ).scalar_one_or_none()

        if user is None or not verify_password(req.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

        access_token = create_access_token(user.id, user.role)
        refresh_token = create_refresh_token(user.id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {"id": user.id, "username": user.username, "role": user.role},
        }


# ---------- POST /auth/refresh ----------

@router.post("/refresh")
def refresh_token(req: RefreshRequest):
    payload = decode_token(req.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id: Optional[str] = payload.get("sub")
    with session_scope() as s:
        user = s.get(UserDB, user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or disabled")

        access_token = create_access_token(user.id, user.role)

    return {"access_token": access_token, "token_type": "bearer"}


# ---------- GET /auth/me ----------

@router.get("/me")
def me(user: UserDB = Depends(get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at.isoformat(),
    }
