import os
from dataclasses import dataclass
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

@dataclass
class DatabaseConfig:
    """Configurações do banco de dados"""
    host: str = os.getenv("HOST", "localhost")
    port: str = os.getenv("PORT", "5432")
    user: str = os.getenv("USER", "postgres")
    password: str = os.getenv("PASSWORD", "")
    dbname: str = os.getenv("DBNAME", "prefeitura")
    
    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"

@dataclass
class ScrapingConfig:
    """Configurações do scraping"""
    base_url: str = "https://www.camarabotucatu.sp.gov.br"
    vereadores_url: str = f"{base_url}/Vereador"
    consulta_url: str = f"{base_url}/Consulta/Vereadores/"
    
    # Headers para requests
    headers: Dict[str, str] = None
    
    # Rate limiting
    request_delay: float = 1.0  # segundos entre requests
    batch_delay: float = 10.0   # segundos entre batches
    
    # Retry configuration
    max_retries: int = 3
    retry_delay: float = 5.0
    
    # Data filtering
    min_year: int = 2021
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

@dataclass
class Config:
    """Configuração principal do projeto"""
    database: DatabaseConfig = None
    scraping: ScrapingConfig = None
    
    # Diretórios
    img_dir: str = "img"
    logs_dir: str = "logs"
    data_dir: str = "data"
    
    def __post_init__(self):
        if self.database is None:
            self.database = DatabaseConfig()
        if self.scraping is None:
            self.scraping = ScrapingConfig()
        
        # Criar diretórios se não existirem
        for directory in [self.img_dir, self.logs_dir, self.data_dir]:
            os.makedirs(directory, exist_ok=True)

# Instância global da configuração
config = Config() 