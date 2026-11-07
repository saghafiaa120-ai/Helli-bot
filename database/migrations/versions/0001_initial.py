"""فاز اول: گروه‌ها، کاربران، عضویت، مدیران، تنظیمات و گزارش اقدامات

Revision ID: 0001
Revises:
Create Date: 2026-11-06
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

MYSQL = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "chat_groups",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("external_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("bot_is_admin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("member_count", sa.Integer(), nullable=True),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.Column("left_at", sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_chat_groups"),
        sa.UniqueConstraint("platform", "external_id", name="uq_chat_groups_platform_external_id"),
        **MYSQL,
    )

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("external_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("first_name", sa.String(255), nullable=True),
        sa.Column("last_name", sa.String(255), nullable=True),
        sa.Column("language_code", sa.String(16), nullable=True),
        sa.Column("is_bot", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("platform", "external_id", name="uq_users_platform_external_id"),
        **MYSQL,
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "group_settings",
        sa.Column("group_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("language", sa.String(8), nullable=False, server_default=sa.text("'fa'")),
        sa.Column(
            "timezone", sa.String(64), nullable=False, server_default=sa.text("'Asia/Tehran'")
        ),
        sa.Column(
            "confirm_sensitive_actions", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column("settings", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("group_id", name="pk_group_settings"),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["chat_groups.id"],
            name="fk_group_settings_group_id_chat_groups",
            ondelete="CASCADE",
        ),
        **MYSQL,
    )

    op.create_table(
        "group_members",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'member'")),
        sa.Column("joined_at", sa.DateTime(), nullable=True),
        sa.Column("left_at", sa.DateTime(), nullable=True),
        sa.Column("last_active_at", sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_group_members"),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["chat_groups.id"],
            name="fk_group_members_group_id_chat_groups",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_group_members_user_id_users", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("group_id", "user_id", name="uq_group_members_group_id_user_id"),
        **MYSQL,
    )
    op.create_index("ix_group_members_group_id_status", "group_members", ["group_id", "status"])
    op.create_index("ix_group_members_user_id", "group_members", ["user_id"])

    op.create_table(
        "group_admins",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("platform_role", sa.String(16), nullable=True),
        sa.Column("permissions", sa.JSON(), nullable=True),
        sa.Column("helli_role", sa.String(16), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_group_admins"),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["chat_groups.id"],
            name="fk_group_admins_group_id_chat_groups",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_group_admins_user_id_users", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("group_id", "user_id", name="uq_group_admins_group_id_user_id"),
        **MYSQL,
    )
    op.create_index("ix_group_admins_user_id", "group_admins", ["user_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("target_user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["chat_groups.id"],
            name="fk_audit_logs_group_id_chat_groups",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_audit_logs_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"],
            ["users.id"],
            name="fk_audit_logs_target_user_id_users",
            ondelete="SET NULL",
        ),
        **MYSQL,
    )
    op.create_index("ix_audit_logs_group_id_created_at", "audit_logs", ["group_id", "created_at"])
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("group_admins")
    op.drop_table("group_members")
    op.drop_table("group_settings")
    op.drop_table("users")
    op.drop_table("chat_groups")
