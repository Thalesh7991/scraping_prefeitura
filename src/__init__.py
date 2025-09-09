"""
Scraper da Câmara de Vereadores de Botucatu

Este pacote contém ferramentas para coletar dados dos vereadores
e suas proposituras do site da Câmara Municipal de Botucatu.
"""

__version__ = "2.0.0"
__author__ = "Thales Pinto"

from .config import config
from .database import db_manager, Vereador, Propositura
from .scraper import CamaraScraper, scrape_vereadores_sync
from .main import ScrapingOrchestrator
from .utils import setup_logging, metrics

__all__ = [
    'config',
    'db_manager', 
    'Vereador',
    'Propositura',
    'CamaraScraper',
    'scrape_vereadores_sync',
    'ScrapingOrchestrator',
    'setup_logging',
    'metrics'
] 