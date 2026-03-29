# services/api/app/activity_log.py
"""Activity logging utility — fire-and-forget, never breaks business logic."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from .db import SessionLocal
from .models import ActivityLogDB


def log_activity(
    action: str,
    *,
    user_id: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    target_url: Optional[str] = None,
    status: str = "success",
    error_step: Optional[str] = None,
    error_message: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Write one activity log row using an independent session.

    The entire call is wrapped in try/except — a logging failure must
    never propagate to the caller.
    """
    try:
        s = SessionLocal()
        try:
            row = ActivityLogDB(
                user_id=user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                target_url=target_url,
                status=status,
                error_step=error_step,
                error_message=error_message[:1000] if error_message else None,
                details=json.dumps(details, ensure_ascii=False) if details else None,
                ip_address=ip_address,
                created_at=datetime.utcnow(),
            )
            s.add(row)
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()
    except Exception as exc:
        print(f"[ActivityLog] WARNING: failed to write log ({action}): {exc}")
