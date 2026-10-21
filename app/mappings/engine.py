"""
MappingEngine — núcleo do processamento de importação.

Recebe linha bruta do CSV + FieldMappingGroup, aplica transformers
e validators, retorna dict pronto para a Moskit API.
Lança MappingValidationError com campo e mensagem em caso de falha.
"""
from dataclasses import dataclass

from app.mappings.transformers import TRANSFORMER_REGISTRY
from app.models.field_mapping_group import FieldMappingGroup


@dataclass
class MappingValidationError(Exception):
    field: str
    message: str

    def __str__(self) -> str:
        return f"[{self.field}] {self.message}"


class MappingEngine:
    def __init__(self, group: FieldMappingGroup):
        self.group = group
        self.mappings = group.mappings  # list[FieldMapping] carregado via relationship

    def process(self, raw_row: dict[str, str]) -> dict:
        """
        Processa uma linha bruta e retorna dict transformado.
        Lança MappingValidationError se campo obrigatório ausente
        ou transformer falhar.
        """
        result: dict = {}

        for mapping in self.mappings:
            raw_value = raw_row.get(mapping.source_column)

            # Campo obrigatório ausente ou vazio
            if not raw_value or not str(raw_value).strip():
                if mapping.is_required:
                    raise MappingValidationError(
                        field=mapping.source_column,
                        message=f"Campo obrigatorio '{mapping.source_column}' ausente ou vazio",
                    )
                # Opcional ausente — ignora
                continue

            transformer = TRANSFORMER_REGISTRY.get(mapping.transformer_type)
            if transformer is None:
                raise MappingValidationError(
                    field=mapping.source_column,
                    message=f"Transformer desconhecido: '{mapping.transformer_type}'",
                )

            try:
                transformed = transformer.transform(
                    str(raw_value), mapping.transformer_config
                )
            except ValueError as exc:
                raise MappingValidationError(
                    field=mapping.source_column,
                    message=str(exc),
                ) from exc

            result[mapping.target_field] = transformed

        return result

    def process_preview(
        self, rows: list[dict[str, str]]
    ) -> list[dict]:
        """
        Processa lista de linhas (preview das primeiras N).
        Retorna lista de dicts com raw, transformed e error por linha.
        Nunca lança — captura erros por linha individualmente.
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
