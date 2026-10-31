from pydantic import BaseModel


class DashboardStats(BaseModel):
    active_connections: int
    total_exports: int
    exports_completed: int
    exports_processing: int
    total_records_exported: int
    total_imports: int
    imports_completed: int
    imports_processing: int
    total_records_imported: int
