"""Cria identidade Atlas e catalogo global de contas Riot.

Revision ID: 20261022_001
Revises:
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'deleted')",
            name="ck_app_users_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_app_users"),
    )

    op.create_table(
        "riot_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("puuid", sa.Text(), nullable=False),
        sa.Column("game_name", sa.Text(), nullable=True),
        sa.Column("tag_line", sa.Text(), nullable=True),
        sa.Column("current_platform", sa.Text(), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_riot_accounts"),
        sa.UniqueConstraint("puuid", name="uq_riot_accounts_puuid"),
    )
    op.create_index(
        "ix_riot_accounts_lookup_riot_id",
        "riot_accounts",
        [sa.text("lower(game_name)"), sa.text("lower(tag_line)")],
        unique=False,
    )

    op.create_table(
        "user_emails",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("email_normalized", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_users.id"], ondelete="CASCADE", name="fk_user_emails_user"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_emails"),
        sa.UniqueConstraint("email_normalized", name="uq_user_emails_normalized"),
    )
    op.create_index("ix_user_emails_user_id", "user_emails", ["user_id"], unique=False)
    op.create_index(
        "uq_user_emails_one_primary",
        "user_emails",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )

    op.create_table(
        "auth_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("issuer", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("last_authenticated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(trim(issuer)) > 0", name="ck_auth_identities_issuer"),
        sa.CheckConstraint("length(trim(subject)) > 0", name="ck_auth_identities_subject"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_users.id"],
            ondelete="CASCADE",
            name="fk_auth_identities_user",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_identities"),
        sa.UniqueConstraint("issuer", "subject", name="uq_auth_identities_issuer_subject"),
    )
    op.create_index(
        "ix_auth_identities_user_id", "auth_identities", ["user_id"], unique=False
    )

    op.create_table(
        "user_riot_account_links",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("riot_account_id", sa.Uuid(), nullable=False),
        sa.Column(
            "link_kind",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'self_reported'"),
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_method", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "length(trim(link_kind)) > 0", name="ck_user_riot_links_link_kind"
        ),
        sa.CheckConstraint(
            "(verified_at IS NULL) = (verification_method IS NULL)",
            name="ck_user_riot_links_verification",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_users.id"],
            ondelete="CASCADE",
            name="fk_user_riot_links_user",
        ),
        sa.ForeignKeyConstraint(
            ["riot_account_id"],
            ["riot_accounts.id"],
            ondelete="CASCADE",
            name="fk_user_riot_links_riot_account",
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "riot_account_id", name="pk_user_riot_account_links"
        ),
    )
    op.create_index(
        "uq_user_riot_links_one_default",
        "user_riot_account_links",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )


def downgrade() -> None:
    op.drop_index("uq_user_riot_links_one_default", table_name="user_riot_account_links")
    op.drop_table("user_riot_account_links")

    op.drop_index("ix_auth_identities_user_id", table_name="auth_identities")
    op.drop_table("auth_identities")

    op.drop_index("uq_user_emails_one_primary", table_name="user_emails")
    op.drop_index("ix_user_emails_user_id", table_name="user_emails")
    op.drop_table("user_emails")

    op.drop_index("ix_riot_accounts_lookup_riot_id", table_name="riot_accounts")
    op.drop_table("riot_accounts")

    op.drop_table("app_users")
