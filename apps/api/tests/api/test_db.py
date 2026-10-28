"""M4 database tests: alembic upgrade head, seed loader, and insert-only protections."""
import logging
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from alembic import command
from app.db.models import Case, CaseEvent, Closure, LLMOutput
from app.db.repo import create_sandbox_with_seed
from app.db.session import build_engine

logger = logging.getLogger(__name__)


def _upgrade_clean_db(db_path: Path) -> str:
    url = f"sqlite:///{db_path.as_posix()}"
    ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[2] / "alembic")
    )
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    return url


def test_alembic_upgrade_head_and_seed_loader(tmp_path: Path) -> None:
    url = _upgrade_clean_db(tmp_path / "m4_clean.db")
    engine = build_engine(url)
    with Session(engine) as db:
        token, sb, count = create_sandbox_with_seed(db)
        assert count == 60
        assert token.startswith("sbx_")
        cases = list(db.scalars(select(Case).where(Case.sandbox_id == sb.id)))
        assert len(cases) == 60
    engine.dispose()


def test_update_and_delete_on_insert_only_tables_fail(tmp_path: Path) -> None:
    """UPDATE and direct DELETE on case_events, closures, and llm_outputs must fail."""
    url = _upgrade_clean_db(tmp_path / "m4_immutable.db")
    engine = build_engine(url)
    with Session(engine) as db:
        _, sb, _ = create_sandbox_with_seed(db)
        ev = db.scalar(select(CaseEvent).where(CaseEvent.sandbox_id == sb.id))
        cl = db.scalar(select(Closure).where(Closure.sandbox_id == sb.id))
        lo = db.scalar(select(LLMOutput).where(LLMOutput.sandbox_id == sb.id))
        assert ev is not None and cl is not None and lo is not None

        # 1. Raw SQL UPDATE on case_events must fail via DB trigger
        with pytest.raises(DBAPIError, match="insert-only: UPDATE forbidden"):
            db.execute(
                text("UPDATE case_events SET event_type = 'HACKED' WHERE id = :id"),
                {"id": ev.id},
            )
        db.rollback()

        # 2. Raw SQL UPDATE on closures and llm_outputs must fail
        with pytest.raises(DBAPIError, match="insert-only: UPDATE forbidden"):
            db.execute(
                text("UPDATE closures SET kind = 'HACKED' WHERE id = :id"),
                {"id": cl.id},
            )
        db.rollback()

        with pytest.raises(DBAPIError, match="insert-only: UPDATE forbidden"):
            db.execute(
                text("UPDATE llm_outputs SET source = 'HACKED' WHERE id = :id"),
                {"id": lo.id},
            )
        db.rollback()

        # 3. Raw SQL DELETE on case_events while sandbox exists must fail
        with pytest.raises(DBAPIError, match="insert-only: DELETE forbidden"):
            db.execute(
                text("DELETE FROM case_events WHERE id = :id"),
                {"id": ev.id},
            )
        db.rollback()

        # 4. ORM mutation on CaseEvent must fail on flush
        ev_again = db.scalar(select(CaseEvent).where(CaseEvent.sandbox_id == sb.id))
        assert ev_again is not None
        ev_again.event_type = "MUTATED"
        with pytest.raises(PermissionError, match="insert-only: UPDATE forbidden"):
            db.flush()
        db.rollback()
    engine.dispose()
