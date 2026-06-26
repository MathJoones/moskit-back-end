"""
Utilitarios para leitura de arquivos CSV/XLSX/JSON com Pandas.
Ativado no Sprint 2.
"""
import io
from typing import Any

import chardet
import pandas as pd


def detect_encoding(raw_bytes: bytes) -> str:
    result = chardet.detect(raw_bytes[:10_000])  # sample para performance
    return result.get("encoding") or "utf-8"


def read_csv(content: bytes) -> pd.DataFrame:
    encoding = detect_encoding(content)
    # Tenta separadores comuns
    for sep in [",", ";", "\t"]:
        try:
            df = pd.read_csv(io.BytesIO(content), encoding=encoding, sep=sep)
            if df.shape[1] > 1:  # mais de 1 coluna = separador correto
                return df
        except Exception:
            continue
    return pd.read_csv(io.BytesIO(content), encoding=encoding)


def read_xlsx(content: bytes) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(content), engine="openpyxl")


def read_json(content: bytes) -> pd.DataFrame:
    return pd.read_json(io.BytesIO(content))


def parse_file(content: bytes, mime_type: str) -> tuple[pd.DataFrame, list[str]]:
    """
    Retorna (DataFrame, colunas_detectadas).
    Raises ValueError se formato nao suportado.
    """
    if mime_type in ("text/csv", "application/csv"):
        df = read_csv(content)
    elif mime_type in (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    ):
        df = read_xlsx(content)
    elif mime_type == "application/json":
        df = read_json(content)
    else:
        raise ValueError(f"Formato nao suportado: {mime_type}")

    # Limpa nomes de colunas
    df.columns = [str(c).strip() for c in df.columns]
    return df, list(df.columns)


def df_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Converte DataFrame em lista de dicts, substituindo NaN por None."""
    return df.where(pd.notna(df), other=None).to_dict(orient="records")
