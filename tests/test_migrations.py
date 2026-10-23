from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_primeira_migration_e_head_do_alembic() -> None:
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "api" / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)

    head = scripts.get_revision("head")

    assert head is not None
    assert head.revision == "20261023_002"
    assert head.down_revision == "20261022_001"
