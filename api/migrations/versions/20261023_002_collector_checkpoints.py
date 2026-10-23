"""Cria checkpoint operacional para o coletor Riot.

Revision ID: 20261023_002
Revises: 20261022_001
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261023_002"
down_revision: str | Sequence[str] | None = "20261022_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collector_match_checkpoints",
        sa.Column("match_id", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("patch", sa.Text(), nullable=True),
        sa.Column("match_stored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timeline_stored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("first_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "collector_version",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'complete', 'permanent_failure')",
            name="ck_collector_checkpoints_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0", name="ck_collector_checkpoints_attempt_count"
        ),
        sa.CheckConstraint(
            "status <> 'complete' OR "
            "(match_stored_at IS NOT NULL AND timeline_stored_at IS NOT NULL "
            "AND completed_at IS NOT NULL)",
            name="ck_collector_checkpoints_complete_artifacts",
        ),
        sa.PrimaryKeyConstraint("match_id", name="pk_collector_match_checkpoints"),
    )
    op.create_index(
        "ix_collector_checkpoints_status_updated_at",
        "collector_match_checkpoints",
        ["status", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_collector_checkpoints_status_updated_at",
        table_name="collector_match_checkpoints",
    )
    op.drop_table("collector_match_checkpoints")
