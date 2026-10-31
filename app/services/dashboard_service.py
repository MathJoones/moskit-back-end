import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.api_connection import ApiConnection
from app.models.export import Export
from app.models.import_job import ImportJob
from app.schemas.dashboard import DashboardStats


class DashboardService:
    def __init__(self, db: Session):
        self.db = db

    def get_stats(self, user_id: uuid.UUID) -> DashboardStats:
        # Conexões ativas (globais — conexões são recurso compartilhado da org)
        active_connections = (
            self.db.query(func.count(ApiConnection.id))
            .filter(
                ApiConnection.deleted_at.is_(None),
                ApiConnection.is_active.is_(True),
            )
            .scalar()
            or 0
        )

        # Stats de exports
        export_rows = (
            self.db.query(Export.status, func.count(Export.id))
            .filter(Export.created_by == user_id)
            .group_by(Export.status)
            .all()
        )
        exports_by_status: dict[str, int] = {row[0]: row[1] for row in export_rows}
        total_exports = sum(exports_by_status.values())
        exports_completed = exports_by_status.get("completed", 0)
        exports_processing = (
            exports_by_status.get("processing", 0)
            + exports_by_status.get("pending", 0)
        )

        total_records_exported = (
            self.db.query(func.coalesce(func.sum(Export.total_records), 0))
            .filter(Export.created_by == user_id, Export.status == "completed")
            .scalar()
            or 0
        )

        # Stats de imports
        import_rows = (
            self.db.query(ImportJob.status, func.count(ImportJob.id))
            .filter(
                ImportJob.created_by == user_id,
                ImportJob.deleted_at.is_(None),
            )
            .group_by(ImportJob.status)
            .all()
        )
        imports_by_status: dict[str, int] = {row[0]: row[1] for row in import_rows}
        total_imports = sum(imports_by_status.values())
        imports_completed = imports_by_status.get("completed", 0)
        imports_processing = (
            imports_by_status.get("processing", 0)
            + imports_by_status.get("pending", 0)
        )

        total_records_imported = (
            self.db.query(func.coalesce(func.sum(ImportJob.created), 0))
            .filter(
                ImportJob.created_by == user_id,
                ImportJob.status == "completed",
                ImportJob.deleted_at.is_(None),
            )
            .scalar()
            or 0
        )

        return DashboardStats(
            active_connections=active_connections,
            total_exports=total_exports,
            exports_completed=exports_completed,
            exports_processing=exports_processing,
            total_records_exported=total_records_exported,
            total_imports=total_imports,
            imports_completed=imports_completed,
            imports_processing=imports_processing,
            total_records_imported=total_records_imported,
        )
