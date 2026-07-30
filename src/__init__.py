"""
Scraper da Câmara de Vereadores de Botucatu

Coleta dados de vereadores e proposituras do site da Câmara Municipal de Botucatu
(sistema Siscam) para alimentar um dashboard público em Streamlit.
"""

__version__ = "3.0.0"
__author__ = "Thales Pinto"

from .config import config
from .database import db_manager
from .scraper_proposituras import scrape_proposituras
from .scraper_vereadores import scrape_vereadores

__all__ = [
    "config",
    "db_manager",
    "scrape_vereadores",
    "scrape_proposituras",
]
