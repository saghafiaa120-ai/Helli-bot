"""فاز ۲: محدودیت‌ها، اخطارها، سابقه اقدامات و آمار پیام‌های روزانه

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-07
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

MYSQL = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def upgrade() -> None:
    op.create_table(
        "restrictions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("until", sa.DateTime(), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("end_reason", sa.String(16), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.PrimaryKeyConstraint("id", name="pk_restrictions"),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["chat_groups.id"],
            name="fk_restrictions_group_id_chat_groups",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_restrictions_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_restrictions_created_by_user_id_users",
            ondelete="SET NULL",
        ),
        **MYSQL,
    )
    op.create_index(
        "ix_restrictions_group_id_user_id_kind", "restrictions", ["group_id", "user_id", "kind"]
    )
    op.create_index("ix_restrictions_is_active_until", "restrictions", ["is_active", "until"])

    op.create_table(
        "warnings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("end_reason", sa.String(16), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_warnings"),
        sa.ForeignKeyConstraint(
            ["group_id"], ["chat_groups.id"], name="fk_warnings_group_id_chat_groups", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_warnings_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_warnings_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_user_id"],
            ["users.id"],
            name="fk_warnings_revoked_by_user_id_users",
            ondelete="SET NULL",
        ),
        **MYSQL,
    )
    op.create_index(
        "ix_warnings_group_id_user_id_is_active", "warnings", ["group_id", "user_id", "is_active"]
    )
    op.create_index("ix_warnings_group_id_created_at", "warnings", ["group_id", "created_at"])

    op.create_table(
        "moderation_actions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("target_user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_moderation_actions"),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["chat_groups.id"],
            name="fk_moderation_actions_group_id_chat_groups",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_moderation_actions_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"],
            ["users.id"],
            name="fk_moderation_actions_target_user_id_users",
            ondelete="SET NULL",
        ),
        **MYSQL,
    )
    op.create_index(
        "ix_moderation_actions_group_id_created_at",
        "moderation_actions",
        ["group_id", "created_at"],
    )
    op.create_index(
        "ix_moderation_actions_target_user_id", "moderation_actions", ["target_user_id"]
    )

    op.create_table(
        "daily_message_counts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("group_external_id", sa.BigInteger(), nullable=False),
        sa.Column("user_external_id", sa.BigInteger(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_daily_message_counts"),
        sa.UniqueConstraint(
            "platform",
            "group_external_id",
            "user_external_id",
            "day",
            name="uq_daily_message_counts_key",
        ),
        **MYSQL,
    )
    op.create_index(
        "ix_daily_message_counts_group_external_id_day",
        "daily_message_counts",
        ["group_external_id", "day"],
    )
    op.create_index(
        "ix_daily_message_counts_user_external_id", "daily_message_counts", ["user_external_id"]
    )
    op.create_index("ix_daily_message_counts_day", "daily_message_counts", ["day"])


def downgrade() -> None:
    op.drop_table("daily_message_counts")
    op.drop_table("moderation_actions")
    op.drop_table("warnings")
    op.drop_table("restrictions")
