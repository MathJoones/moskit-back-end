"""Initial schema — users, sessions, connections, exports, audit_logs

Revision ID: 001
Revises:
Create Date: 2026-06-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID, INET

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("admin", "operator", "viewer", name="user_role"), nullable=False, server_default="operator"),
        sa.Column("status", sa.Enum("active", "inactive", "suspended", name="user_status"), nullable=False, server_default="active"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_attempts", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ── user_sessions ──────────────────────────────────────
    op.create_table(
        "user_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("refresh_token", sa.String(512), nullable=False, unique=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("ip_address", INET(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])

    # ── api_connections ────────────────────────────────────
    op.create_table(
        "api_connections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("connection_type", sa.Enum("moskit", "external_api", "csv", "xlsx", "database", name="connection_type", create_type=True), nullable=False),
        sa.Column("base_url", sa.String(1024), nullable=True),
        sa.Column("api_key_enc", sa.LargeBinary(), nullable=True),
        sa.Column("api_secret_enc", sa.LargeBinary(), nullable=True),
        sa.Column("extra_config", JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_ok", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_api_connections_created_by", "api_connections", ["created_by"])

    # ── exports ────────────────────────────────────────────
    op.create_table(
        "exports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("entity_type", sa.Enum("deal", "contact", "company", "activity", name="export_entity_type", create_type=True), nullable=False),
        sa.Column("status", sa.Enum("pending", "processing", "completed", "failed", name="export_status", create_type=True), nullable=False, server_default="pending"),
        sa.Column("connection_id", UUID(as_uuid=True), sa.ForeignKey("api_connections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("filter_config", JSONB(), nullable=True),
        sa.Column("columns_config", JSONB(), nullable=True),
        sa.Column("output_format", sa.Enum("csv", "xlsx", "json", name="export_format", create_type=True), nullable=False, server_default="xlsx"),
        sa.Column("output_file_path", sa.String(1024), nullable=True),
        sa.Column("output_file_name", sa.String(512), nullable=True),
        sa.Column("total_records", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_exports_created_by", "exports", ["created_by"])
    op.create_index("ix_exports_status", "exports", ["status"])
    op.create_index("ix_exports_created_at", "exports", ["created_at"])

    # ── audit_logs ─────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.Enum("create", "update", "delete", "login", "logout", "import", "export", name="audit_action", create_type=True), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=True),
        sa.Column("entity_id", sa.String(255), nullable=True),
        sa.Column("old_value", JSONB(), nullable=True),
        sa.Column("new_value", JSONB(), nullable=True),
        sa.Column("ip_address", INET(), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("exports")
    op.drop_table("api_connections")
    op.drop_table("user_sessions")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS audit_action")
    op.execute("DROP TYPE IF EXISTS export_format")
    op.execute("DROP TYPE IF EXISTS export_status")
    op.execute("DROP TYPE IF EXISTS export_entity_type")
    op.execute("DROP TYPE IF EXISTS connection_type")
    op.execute("DROP TYPE IF EXISTS user_status")
    op.execute("DROP TYPE IF EXISTS user_role")
