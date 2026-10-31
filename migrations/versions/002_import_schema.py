"""Import schema — field_mapping_groups, field_mappings, imports, import_rows
Revision ID: 002
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ENUMs ─────────────────────────────────────────────────
    op.execute("CREATE TYPE import_entity_type AS ENUM ('contact', 'company', 'deal')")
    op.execute("CREATE TYPE import_status AS ENUM ('pending', 'processing', 'completed', 'cancelled', 'error')")
    op.execute("CREATE TYPE import_row_status AS ENUM ('created', 'duplicate', 'error')")
    op.execute("CREATE TYPE transformer_type AS ENUM ('date', 'phone', 'enum', 'string', 'number')")

    # ── field_mapping_groups ───────────────────────────────────
    op.create_table(
        "field_mapping_groups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("entity_type", sa.Enum("contact", "company", "deal", name="import_entity_type", create_type=False), nullable=False),
        sa.Column("dedup_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("dedup_keys", JSONB(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_field_mapping_groups_created_by", "field_mapping_groups", ["created_by"])
    op.create_index("ix_field_mapping_groups_entity_type", "field_mapping_groups", ["entity_type"])

    # ── field_mappings ─────────────────────────────────────────
    op.create_table(
        "field_mappings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("group_id", UUID(as_uuid=True), sa.ForeignKey("field_mapping_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_column", sa.String(255), nullable=False),
        sa.Column("target_field", sa.String(255), nullable=False),
        sa.Column("transformer_type", sa.Enum("date", "phone", "enum", "string", "number", name="transformer_type", create_type=False), nullable=False, server_default="string"),
        sa.Column("transformer_config", JSONB(), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_field_mappings_group_id", "field_mappings", ["group_id"])

    # ── imports ────────────────────────────────────────────────
    op.create_table(
        "imports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("entity_type", sa.Enum("contact", "company", "deal", name="import_entity_type", create_type=False), nullable=False),
        sa.Column("status", sa.Enum("pending", "processing", "completed", "cancelled", "error", name="import_status", create_type=False), nullable=False, server_default="pending"),
        sa.Column("connection_id", UUID(as_uuid=True), sa.ForeignKey("api_connections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("mapping_group_id", UUID(as_uuid=True), sa.ForeignKey("field_mapping_groups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("input_file_path", sa.String(1024), nullable=True),
        sa.Column("input_file_name", sa.String(512), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=True),
        sa.Column("processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_imports_created_by", "imports", ["created_by"])
    op.create_index("ix_imports_status", "imports", ["status"])
    op.create_index("ix_imports_created_at", "imports", ["created_at"])

    # ── import_rows ────────────────────────────────────────────
    op.create_table(
        "import_rows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("import_id", UUID(as_uuid=True), sa.ForeignKey("imports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw_data", JSONB(), nullable=True),
        sa.Column("status", sa.Enum("created", "duplicate", "error", name="import_row_status", create_type=False), nullable=False, server_default="error"),
        sa.Column("moskit_id", sa.String(255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_import_rows_import_id", "import_rows", ["import_id"])
    op.create_index("ix_import_rows_status", "import_rows", ["status"])


def downgrade() -> None:
    op.drop_table("import_rows")
    op.drop_table("imports")
    op.drop_table("field_mappings")
    op.drop_table("field_mapping_groups")

    op.execute("DROP TYPE IF EXISTS import_row_status")
    op.execute("DROP TYPE IF EXISTS import_status")
    op.execute("DROP TYPE IF EXISTS import_entity_type")
    op.execute("DROP TYPE IF EXISTS transformer_type")
