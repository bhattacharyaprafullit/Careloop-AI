"""LangGraph checkpointer factory: PostgresSaver on Supabase session pooler, SqliteSaver locally."""
import logging
import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_CHECKPOINTER: Any = None
_CHECKPOINTER_KEY: str = ""


def _sqlite_path_from_url(database_url: str) -> str:
    if database_url.startswith("sqlite:///"):
        raw = database_url[len("sqlite:///") :]
        p = Path(raw).resolve()
        return str(p.with_suffix(".checkpoints.sqlite"))
    return "careloop.checkpoints.sqlite"


def get_checkpointer(database_url: str | None = None) -> Any:
    """Return a configured PostgresSaver or SqliteSaver instance (cached by URL)."""
    global _CHECKPOINTER, _CHECKPOINTER_KEY
    url = database_url or get_settings().database_url
    if _CHECKPOINTER is not None and url == _CHECKPOINTER_KEY:
        return _CHECKPOINTER

    if url.startswith("postgresql"):
        import psycopg
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg.rows import dict_row

        pg_uri = url.replace("postgresql+psycopg://", "postgresql://")
        conn: Any = psycopg.connect(
            pg_uri,
            autocommit=True,
            prepare_threshold=0,
            row_factory=dict_row,
        )
        saver: Any = PostgresSaver(conn)
        saver.setup()
        _CHECKPOINTER = saver
        _CHECKPOINTER_KEY = url
        logger.info("initialized PostgresSaver checkpointer")
        return saver

    ckpt_file = _sqlite_path_from_url(url)
    sqlite_conn = sqlite3.connect(ckpt_file, check_same_thread=False)
    saver = SqliteSaver(sqlite_conn)
    saver.setup()
    _CHECKPOINTER = saver
    _CHECKPOINTER_KEY = url
    logger.info("initialized SqliteSaver checkpointer", extra={"path": ckpt_file})
    return saver


def reset_checkpointer(database_url: str | None = None) -> Any:
    """Force re-creation of the checkpointer (used in restart tests)."""
    global _CHECKPOINTER, _CHECKPOINTER_KEY
    _CHECKPOINTER = None
    _CHECKPOINTER_KEY = ""
    return get_checkpointer(database_url)
