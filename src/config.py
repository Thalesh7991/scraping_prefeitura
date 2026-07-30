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

# Categoria por ASSUNTO real de cada propositura - eixo independente de tipo/família,
# calculada por regra determinística no texto da ementa (nunca por LLM - ver ROADMAP.md,
# item 1, sobre por que essa parte precisa ser auditável). Validado em 2026-07-30 contra as
# 7.234 ementas já coletadas.
#
# A ORDEM IMPORTA: as categorias cerimoniais/simbólicas são testadas ANTES de qualquer
# categoria de política pública, para que algo como "Denomina a Rua X" nunca seja
# classificado como "Trânsito" só por mencionar uma rua - pedido explícito do usuário: os
# nomes das categorias têm que ser honestos sobre o que a propositura realmente é, mesmo
# quando isso expõe atuação de baixo impacto.
CATEGORIA_PATTERNS = [
    ("Denominação de Ruas/Prédios e Títulos Honoríficos",
     r"\bdenomina\b|\bd[áa]\s+o\s+nome\b|passa\s+a\s+denominar|"
     r"t[íi]tulo\s+de\s+cidad[ãa]o|cidad[ãa]o\s+benem[ée]rito|t[íi]tulo\s+honor[íi]fico"),
    ("Datas, Semanas e Campanhas Comemorativas",
     r"institui.{0,60}\b(dia|semana|m[êe]s)\s+(municipal|d[eao]s?)\b|institui\s+a?\s*campanha|"
     r"data\s+comemorativa"),
    ("Utilidade Pública", r"utilidade\s+p[úu]blica"),
    ("Homenagens e Manifestações de Apreço/Pesar",
     r"congratula|\bp[êe]sames?\b|voto\s+de\s+pesar|falecimento|voto\s+de\s+aplauso|"
     r"voto\s+de\s+rep[úu]dio|manifesta[çc][ãa]o\s+de\s+(apoio|rep[úu]dio)|mo[çc][ãa]o\s+de\s+apelo"),
    ("Saúde", r"\bsaude\b|hospital|clinica|posto de saude|\bubs\b|\bupa\b|medic|enfermeir|vacin|\bsamu\b|paciente"),
    ("Educação", r"\beducac|\bescola|creche|professor|\baluno|\bensino|merenda|pedagog"),
    ("Assistência Social",
     r"assistencia social|vulnerabilidade|pessoa com deficiencia|\bpcd\b|situacao de rua|"
     r"crianca e adolescente|\bidoso|inclusao social|cesta.{0,10}basica"),
    ("Segurança Pública", r"\bseguranca\b|policia|guarda civil|\bfurto|\broubo|criminalidade"),
    ("Meio Ambiente",
     r"\bambient|\barvor|\bpoda\b|area verde|sustentab|causa animal|\banimais\b|reciclagem|"
     r"residuos solidos|assoreamento|nascente"),
    ("Trânsito e Segurança Viária",
     r"\btransito\b|lombada|redutor de velocidade|sinalizacao|semaforo|ciclovia|ciclofaixa|"
     r"pedestre|faixa de pedestre|rotatoria"),
    ("Transporte Coletivo e Rodovias",
     r"\bonibus\b|transporte coletivo|rodovia|passagem de onibus|linha de onibus|mototaxi"),
    ("Infraestrutura e Obras Urbanas",
     r"pavimenta|drenagem|iluminacao publica|\bpraca\b|\bparque\b|limpeza urbana|capina|"
     r"buraco|calcada|obras\s+(de|na|no|para|publicas)|construcao de|reforma de|"
     r"manutencao de|galeria|guias e sarjetas|posteamento"),
    ("Cultura, Esporte e Lazer",
     r"\besporte|\blazer\b|\bcultura\b|turismo|evento cultural|quadra poliesportiva|biblioteca"),
    ("Administração e Institucional",
     r"concurso p[úu]blico|comiss[ãa]o de|audi[êe]ncia p[úu]blica|servidor|altera\s+a\s+lei|"
     r"\bdistrito\b|or[çc]amento|licita[çc][ãa]o|contrato administrativo"),
]

CATEGORIA_RESIDUAL = "Outros/Não identificado"

# Categorias cerimoniais/simbólicas (baixo ou nenhum efeito prático) - usado pra colorir o
# gráfico de forma que salte aos olhos quando a atuação de alguém é majoritariamente isso.
CATEGORIAS_CERIMONIAIS = {
    "Denominação de Ruas/Prédios e Títulos Honoríficos",
    "Datas, Semanas e Campanhas Comemorativas",
    "Utilidade Pública",
    "Homenagens e Manifestações de Apreço/Pesar",
}

# destinatário do pedido (prefixo "X - solicita-se/indica-se" em Indicação/Requerimento) ->
# categoria. Usado só como reforço quando nenhum padrão de conteúdo acima bateu (ex.: pedido
# genérico ao "Secretário de Saúde" sem palavra de saúde explícita no resto do texto).
DESTINATARIO_CATEGORIA = {
    "secretario de saude": "Saúde", "secretaria de saude": "Saúde", "ministro da saude": "Saúde",
    "secretario de educacao": "Educação", "secretaria de educacao": "Educação",
    "secretario de infraestrutura": "Infraestrutura e Obras Urbanas",
    "secretario de zeladoria": "Infraestrutura e Obras Urbanas", "zeladoria": "Infraestrutura e Obras Urbanas",
    "secretario de habitacao e urbanismo": "Infraestrutura e Obras Urbanas",
    "consultor": "Infraestrutura e Obras Urbanas", "superintendente": "Infraestrutura e Obras Urbanas",
    "secretario adjunto para assuntos do transporte": "Transporte Coletivo e Rodovias",
    "secretario adjunto em assuntos do transporte": "Transporte Coletivo e Rodovias",
    "secretario adjunto de assuntos do transporte": "Transporte Coletivo e Rodovias",
    "presidente da concessionaria rodovias": "Transporte Coletivo e Rodovias",
    "secretario de seguranca": "Segurança Pública", "secretaria de seguranca": "Segurança Pública",
    "secretario do verde": "Meio Ambiente", "secretaria de meio ambiente": "Meio Ambiente",
    "secretario de agricultura": "Meio Ambiente",
    "assessora especial de politicas de inclusao": "Assistência Social",
    "secretaria de assistencia social": "Assistência Social", "secretario de assistencia social": "Assistência Social",
    "secretario de esportes": "Cultura, Esporte e Lazer", "secretaria de esportes": "Cultura, Esporte e Lazer",
    "secretaria de cultura": "Cultura, Esporte e Lazer", "secretario de cultura": "Cultura, Esporte e Lazer",
    "secretaria adjunta de turismo": "Cultura, Esporte e Lazer",
    "secretario de participacao popular": "Administração e Institucional",
    "secretario de governo": "Administração e Institucional", "presidente da camara": "Administração e Institucional",
}
