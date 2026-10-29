"""Database engine, session factory, and insert-only table enforcement (M4)."""
import logging
from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import Base, CaseEvent, Closure, LLMOutput

logger = logging.getLogger(__name__)

INSERT_ONLY_TABLES: tuple[str, ...] = ("case_events", "closures", "llm_outputs")
INSERT_ONLY_MODELS: tuple[type[Any], ...] = (CaseEvent, Closure, LLMOutput)

_ENGINE: Engine | None = None
_SESSION_LOCAL: sessionmaker[Session] | None = None


def install_insert_only_guards(engine: Engine) -> None:
    """Install database triggers blocking UPDATE and direct DELETE on insert-only tables."""
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == "sqlite":
            for tbl in INSERT_ONLY_TABLES:
                conn.execute(
                    text(
                        f"CREATE TRIGGER IF NOT EXISTS trg_{tbl}_no_update "
                        f"BEFORE UPDATE ON {tbl} BEGIN "
                        f"SELECT RAISE(ABORT, '{tbl} is insert-only: UPDATE forbidden'); END;"
                    )
                )
                # Direct DELETE is forbidden while the owning sandbox still exists
                conn.execute(
                    text(
                        f"CREATE TRIGGER IF NOT EXISTS trg_{tbl}_no_delete "
                        f"BEFORE DELETE ON {tbl} "
                        f"WHEN EXISTS (SELECT 1 FROM sandboxes s WHERE s.id = OLD.sandbox_id) "
                        f"BEGIN SELECT RAISE(ABORT, '{tbl} is insert-only: DELETE forbidden'); END;"
                    )
                )
        elif dialect == "postgresql":
            conn.execute(
                text(
                    """
                    CREATE OR REPLACE FUNCTION forbid_insert_only_mutation()
                    RETURNS trigger AS $$
                    BEGIN
                        IF TG_OP = 'UPDATE' THEN
                            RAISE EXCEPTION '% is insert-only: UPDATE forbidden', TG_TABLE_NAME;
                        ELSIF TG_OP = 'DELETE' THEN
                            IF EXISTS (SELECT 1 FROM sandboxes s WHERE s.id = OLD.sandbox_id) THEN
                                RAISE EXCEPTION '% is insert-only: DELETE forbidden', TG_TABLE_NAME;
                            END IF;
                            RETURN OLD;
                        END IF;
                        RETURN NEW;
                    END;
                    $$ LANGUAGE plpgsql;
                    """
                )
            )
            for tbl in INSERT_ONLY_TABLES:
                conn.execute(
                    text(f"DROP TRIGGER IF EXISTS trg_{tbl}_immutable ON {tbl};")
                )
                conn.execute(
                    text(
                        f"CREATE TRIGGER trg_{tbl}_immutable "
                        f"BEFORE UPDATE OR DELETE ON {tbl} "
                        f"FOR EACH ROW EXECUTE FUNCTION forbid_insert_only_mutation();"
                    )
                )


@event.listens_for(Session, "before_flush")
def _forbid_orm_update_or_delete(
    session: Session, _flush_context: Any, _instances: Any
) -> None:
    for obj in session.dirty:
        if isinstance(obj, INSERT_ONLY_MODELS) and session.is_modified(obj):
            raise PermissionError(f"{type(obj).__tablename__} is insert-only: UPDATE forbidden")
    for obj in session.deleted:
        if isinstance(obj, INSERT_ONLY_MODELS):
            raise PermissionError(f"{type(obj).__tablename__} is insert-only: DELETE forbidden")


def build_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy 2.0 Engine configured for SQLite or Supabase Postgres."""
    url = database_url or get_settings().effective_database_url
    connect_args: dict[str, Any] = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    elif "postgresql" in url:
        connect_args["prepare_threshold"] = 0
    eng = create_engine(url, future=True, pool_pre_ping=True, connect_args=connect_args)
    if url.startswith("sqlite") and ":memory:" not in url:
        @event.listens_for(eng, "connect")
        def _set_sqlite_pragma(dbapi_conn: Any, _conn_record: Any) -> None:
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA temp_store=MEMORY;")
            cursor.close()
    return eng


def get_engine() -> Engine:
    """Return or initialize the singleton Engine."""
    global _ENGINE, _SESSION_LOCAL
    if _ENGINE is None:
        _ENGINE = build_engine()
        _SESSION_LOCAL = sessionmaker(bind=_ENGINE, autoflush=False, autocommit=False)
    return _ENGINE


def reset_engine(database_url: str | None = None) -> Engine:
    """Reset the cached engine (used by tests switching temporary SQLite databases)."""
    global _ENGINE, _SESSION_LOCAL
    if _ENGINE is not None:
        _ENGINE.dispose()
    _ENGINE = build_engine(database_url)
    _SESSION_LOCAL = sessionmaker(bind=_ENGINE, autoflush=False, autocommit=False)
    return _ENGINE


def init_db(engine: Engine | None = None) -> None:
    """Create all tables and install insert-only triggers if not already present."""
    eng = engine or get_engine()
    Base.metadata.create_all(bind=eng)
    install_insert_only_guards(eng)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database Session."""
    global _SESSION_LOCAL
    if _SESSION_LOCAL is None:
        get_engine()
    assert _SESSION_LOCAL is not None
    db = _SESSION_LOCAL()
    try:
        yield db
    finally:
        db.close()
