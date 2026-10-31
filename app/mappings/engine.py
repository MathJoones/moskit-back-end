"""
MappingEngine — nucleo do processamento de importacao.

Recebe linha bruta do CSV + lista de mapeamentos (column_mappings do ImportJob),
aplica transformers e validators, retorna dict pronto para a Moskit API.
Lanca MappingValidationError com campo e mensagem em caso de falha.

Estrutura de cada item em column_mappings:
  {
    "csv_column":        str,        # coluna no CSV
    "target_field":      str,        # campo no payload da Moskit API
    "transformer":       str | null, # "string" | "number" | "date" | "phone" | "enum"
    "transformer_config": dict | null,
    "is_required":       bool        # default false
  }
"""
from dataclasses import dataclass

from app.mappings.transformers import TRANSFORMER_REGISTRY


@dataclass
class MappingValidationError(Exception):
    field: str
    message: str

    def __str__(self) -> str:
        return f"[{self.field}] {self.message}"


class MappingEngine:
    def __init__(self, column_mappings: list[dict]):
        self.column_mappings = column_mappings

    def process(self, raw_row: dict[str, str]) -> dict:
        """
        Processa uma linha bruta e retorna dict transformado.
        Lanca MappingValidationError se campo obrigatorio ausente
        ou transformer falhar.
        """
        result: dict = {}

        for mapping in self.column_mappings:
            csv_col: str = mapping.get("csv_column", "")
            target_field: str = mapping.get("target_field", "")
            transformer_type: str = mapping.get("transformer") or "string"
            transformer_config: dict | None = mapping.get("transformer_config")
            is_required: bool = mapping.get("is_required", False)

            raw_value = raw_row.get(csv_col)

            if not raw_value or not str(raw_value).strip():
                if is_required:
                    raise MappingValidationError(
                        field=csv_col,
                        message=f"Campo obrigatorio '{csv_col}' ausente ou vazio",
                    )
                continue

            transformer = TRANSFORMER_REGISTRY.get(transformer_type)
            if transformer is None:
                raise MappingValidationError(
                    field=csv_col,
                    message=f"Transformer desconhecido: '{transformer_type}'",
                )

            try:
                transformed = transformer.transform(str(raw_value), transformer_config)
            except ValueError as exc:
                raise MappingValidationError(
                    field=csv_col,
                    message=str(exc),
                ) from exc

            result[target_field] = transformed

        return result

    def process_preview(self, rows: list[dict[str, str]]) -> list[dict]:
        """
        Processa lista de linhas (preview das primeiras N).
        Retorna lista de dicts com raw, transformed e error por linha.
        Nunca lanca — captura erros por linha individualmente.
        """
        preview = []
        for i, raw_row in enumerate(rows, start=1):
            try:
                transformed = self.process(raw_row)
                preview.append({
                    "row_number": i,
                    "raw": raw_row,
                    "transformed": transformed,
                    "error": None,
                })
            except MappingValidationError as exc:
                preview.append({
                    "row_number": i,
                    "raw": raw_row,
                    "transformed": None,
                    "error": str(exc),
                })
        return preview
