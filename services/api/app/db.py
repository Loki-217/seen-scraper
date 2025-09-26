# services/api/app/db.py
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .settings import settings
from . import models  # 确保 Base/模型类都在同一个 Declarative Base 上

# ------------- 配置 -------------
# 兼容字段名 database_url / db_url，默认落到本地 sqlite
DATABASE_URL: str = (
    getattr(settings, "database_url", None)
    or getattr(settings, "db_url", None)
    or "sqlite:///./seen.db"
)

is_sqlite = DATABASE_URL.startswith("sqlite")
engine_args = {"future": True}
if is_sqlite:
    # sqlite 在线程下要关闭同线程检查
    engine_args["connect_args"] = {"check_same_thread": False}

engine: Engine = create_engine(DATABASE_URL, **engine_args)

# sqlite 开外键
if is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)

# ------------- 初始化 -------------
def init_db() -> None:
    """启动时调用：建表"""
    models.Base.metadata.create_all(bind=engine)

# ------------- 两种会话用法 -------------
def get_session() -> Generator[Session, None, None]:
    """
    FastAPI 依赖注入用法：
    def endpoint(db: Session = Depends(get_session)): ...
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    代码块用法：
    with session_scope() as s:
        ...
    """
    s: Session = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
