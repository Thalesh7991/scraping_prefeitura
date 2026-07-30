import os
from dataclasses import dataclass, field
from datetime import date
from typing import Dict


@dataclass
class ScrapingConfig:
    """Configurações de scraping para o novo site (Siscam)"""
    base_url: str = "https://www.camarabotucatu.sp.gov.br"

    @property
    def vereadores_url(self) -> str:
        return f"{self.base_url}/Vereadores"

    @property
    def vereador_details_url(self) -> str:
        return f"{self.base_url}/Vereadores/Details"

    @property
    def documentos_url(self) -> str:
        return f"{self.base_url}/Siscam/Documentos"

    headers: Dict[str, str] = field(default_factory=lambda: {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })

    # Rate limiting / retry
    request_delay: float = 1.0
    max_retries: int = 3
    retry_delay: float = 5.0

    # Escopo: legislatura atual + anterior (2021-2028)
    data_inicio: date = date(2021, 1, 1)

    # Parâmetros fixos da busca de proposituras no Siscam
    grupo_id_proposituras: int = 3
    tipo_autor_vereadores: int = 1
    items_per_page: int = 100
    ordenacao_data_decrescente: int = 3


@dataclass
class Config:
    scraping: ScrapingConfig = field(default_factory=ScrapingConfig)

    data_dir: str = "data"
    img_dir: str = "img"
    logs_dir: str = "logs"

    @property
    def db_path(self) -> str:
        return os.path.join(self.data_dir, "camara_botucatu.db")

    def __post_init__(self):
        for directory in [self.data_dir, self.img_dir, self.logs_dir]:
            os.makedirs(directory, exist_ok=True)


config = Config()

# Nomes legíveis dos tipos de propositura (TipoId do Siscam), para referência.
# A coleta grava o texto do "tipo" exatamente como aparece no site (não usa este dicionário),
# mas ele documenta a taxonomia usada nas famílias do dashboard.
TIPO_ID_NOMES = {
    44: "Projeto de Lei",
    45: "Projeto de Lei Complementar",
    46: "Projeto de Decreto Legislativo",
    48: "Projeto de Emenda à Lei Orgânica",
    47: "Projeto de Resolução",
    50: "Indicação",
    51: "Moção",
    49: "Requerimento",
    39: "Veto",
    67: "Conta",
}

# Famílias de tipo usadas para agrupar métricas no dashboard (ver plano do projeto).
# As chaves usam o texto exatamente como o site grava em "tipo" (singular, sem "Nº ano/num").
FAMILIA_POR_TIPO = {
    "Projeto de Lei": "Normativos",
    "Projeto de Lei Complementar": "Normativos",
    "Projeto de Decreto Legislativo": "Normativos",
    "Projeto de Emenda à Lei Orgânica": "Normativos",
    "Projeto de Resolução": "Normativos",
    "Indicação": "Fiscalização/Solicitações",
    "Requerimento": "Fiscalização/Solicitações",
    "Moção": "Manifestações políticas",
    "Conta": "Outros",
    "Veto": "Outros",
}
