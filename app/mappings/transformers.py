"""
Transformers plugáveis — um por transformer_type.
Interface comum: transform(value, config) -> Any
Novo tipo = nova classe, sem alterar o engine.
"""
from abc import ABC, abstractmethod
from datetime import datetime
import re


class BaseTransformer(ABC):
    @abstractmethod
    def transform(self, value: str, config: dict | None = None) -> object:
        """Transforma valor bruto do CSV. Lança ValueError em falha."""


class StringTransformer(BaseTransformer):
    def transform(self, value: str, config: dict | None = None) -> str:
        return value.strip()


class NumberTransformer(BaseTransformer):
    def transform(self, value: str, config: dict | None = None) -> float | int:
        cleaned = value.strip().replace(",", ".")
        try:
            num = float(cleaned)
            return int(num) if num == int(num) else num
        except (ValueError, OverflowError):
            raise ValueError(f"Valor '{value}' nao e numero valido")


class DateTransformer(BaseTransformer):
    # Formatos tentados em ordem — estende via config["formats"]
    DEFAULT_FORMATS = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%dT%H:%M:%S",
    ]

    def transform(self, value: str, config: dict | None = None) -> str:
        raw = value.strip()
        formats = (config or {}).get("formats", self.DEFAULT_FORMATS)
        output_fmt = (config or {}).get("output_format", "%Y-%m-%d")

        for fmt in formats:
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.strftime(output_fmt)
            except ValueError:
                continue

        raise ValueError(
            f"Data '{raw}' nao corresponde a nenhum formato suportado: {formats}"
        )


class PhoneTransformer(BaseTransformer):
    def transform(self, value: str, config: dict | None = None) -> str:
        digits = re.sub(r"\D", "", value.strip())
        if not digits:
            raise ValueError(f"Telefone '{value}' nao contem digitos")
        # Retorna no formato +55XXXXXXXXXXX se config["country_code"] definido
        country_code = (config or {}).get("country_code", "")
        if country_code and not digits.startswith(country_code.lstrip("+")):
            digits = country_code.lstrip("+") + digits
        return f"+{digits}"


class EnumTransformer(BaseTransformer):
    """
    Mapeia valor textual para ID de opção da Moskit API.
    config["mapping"]: {"Ativo": "1", "Inativo": "2"}
    config["case_insensitive"]: true (default)
    """

    def transform(self, value: str, config: dict | None = None) -> str:
        cfg = config or {}
        mapping: dict = cfg.get("mapping", {})
        case_insensitive: bool = cfg.get("case_insensitive", True)

        raw = value.strip()
        key = raw.lower() if case_insensitive else raw

        lookup = (
            {k.lower(): v for k, v in mapping.items()}
            if case_insensitive
            else mapping
        )

        if key not in lookup:
            raise ValueError(
                f"Valor '{raw}' nao encontrado no mapeamento de enum. "
                f"Valores aceitos: {list(mapping.keys())}"
            )
        return lookup[key]


TRANSFORMER_REGISTRY: dict[str, BaseTransformer] = {
    "string": StringTransformer(),
    "number": NumberTransformer(),
    "date": DateTransformer(),
    "phone": PhoneTransformer(),
    "enum": EnumTransformer(),
}
