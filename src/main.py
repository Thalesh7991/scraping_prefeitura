#!/usr/bin/env python3
"""Orquestrador do scraping da Câmara de Vereadores de Botucatu."""

import argparse
import logging
import sys
import time

from .database import db_manager
from .scraper_proposituras import scrape_proposituras
from .scraper_vereadores import scrape_vereadores
from .utils import setup_logging

logger = logging.getLogger(__name__)


def run_vereadores():
    logger.info("=== Coletando vereadores ===")
    inicio = time.time()
    total = scrape_vereadores()
    logger.info(f"Vereadores processados: {total} em {time.time() - inicio:.1f}s")


def run_proposituras():
    logger.info("=== Coletando proposituras ===")
    inicio = time.time()
    resultado = scrape_proposituras()
    logger.info(f"Proposituras: {resultado} em {time.time() - inicio:.1f}s")


def run_relatorio_final():
    stats = db_manager.get_statistics()
    logger.info("=== ESTATÍSTICAS FINAIS ===")
    logger.info(
        f"Vereadores: {stats['vereadores_count']} "
        f"(perfil completo: {stats['vereadores_perfil_completo']})"
    )
    logger.info(f"Proposituras: {stats['proposituras_count']}")

    logger.info("Por tipo:")
    for item in stats["proposituras_por_tipo"]:
        logger.info(f"  {item['tipo']}: {item['total']}")

    logger.info("Por situação:")
    for item in stats["proposituras_por_situacao"]:
        logger.info(f"  {item['situacao']}: {item['total']}")

    logger.info("Top 10 vereadores por nº de proposituras (autoria/coautoria):")
    for item in stats["proposituras_por_vereador"][:10]:
        logger.info(f"  {item['nome']}: {item['total']}")


def main():
    parser = argparse.ArgumentParser(description="Scraper da Câmara de Vereadores de Botucatu")
    parser.add_argument(
        "--mode",
        choices=["vereadores", "proposituras", "full"],
        default="full",
        help="Modo de execução (default: full)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
    )
    args = parser.parse_args()

    setup_logging(level=getattr(logging, args.log_level))
    db_manager.create_tables()

    try:
        if args.mode in ("vereadores", "full"):
            run_vereadores()
        if args.mode in ("proposituras", "full"):
            run_proposituras()
        run_relatorio_final()
    except KeyboardInterrupt:
        logger.info("Execução interrompida pelo usuário")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Erro fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
