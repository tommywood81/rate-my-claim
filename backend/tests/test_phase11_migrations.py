"""Phase 11: Alembic migration graph integrity."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

_BACKEND = Path(__file__).resolve().parents[1]
_SKIP = os.environ.get("RUN_PG_INTEGRATION") != "1"
_SKIP_REASON = "Set RUN_PG_INTEGRATION=1 to verify DB is at migration head"


def _script_directory() -> ScriptDirectory:
    cfg = Config(str(_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_alembic_has_single_head() -> None:
    """Migration history must not branch unexpectedly."""
    heads = _script_directory().get_heads()
    assert len(heads) == 1, f"expected one head, got {heads}"


def test_alembic_revision_chain_is_linear() -> None:
    """All revisions connect to base without orphans."""
    script = _script_directory()
    revisions = list(script.walk_revisions())
    assert len(revisions) >= 4
    head = script.get_current_head()
    assert head is not None
    down = script.get_revision(head)
    assert down is not None


@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_database_at_alembic_head() -> None:
    """Running stack should match latest migration (docker compose startup)."""
    from sqlalchemy import create_engine, text

    from app.core.config import get_settings

    settings = get_settings()
    sync_url = settings.sync_database_url
    engine = create_engine(sync_url)
    script = _script_directory()
    expected = script.get_current_head()
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
    assert row is not None, "alembic_version table missing — run alembic upgrade head"
    assert row[0] == expected, f"DB at {row[0]!r}, head is {expected!r}"
