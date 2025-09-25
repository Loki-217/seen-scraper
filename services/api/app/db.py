from __future__ import annotations
from pathlib import Path
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# SQLite 文件放在 ./data/seenscraper.db
DATA_DIR = Path("./data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_URL = f"sqlite:///{(DATA_DIR / 'seenscraper.db').as_posix()}"

# future=True 走 SA2 API，check_same_thread=False 允许多线程访问同一连接
engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

class Base(DeclarativeBase):
    pass

def init_db() -> None:
    """在程序启动或一次性脚本里调用，建表。"""
    from . import models  # noqa: F401  确保模型已注册
    Base.metadata.create_all(engine)

@contextmanager
def session_scope() -> Iterator[sessionmaker]:
    """
    事务上下文管理器:
        with session_scope() as s:
            ...  # s is Session
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
# 末尾附近加
from typing import Generator
from sqlalchemy.orm import Session

def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
