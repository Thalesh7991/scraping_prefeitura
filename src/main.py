#!/usr/bin/env python3
"""
Script principal para execução do scraping da Câmara de Vereadores
"""

import asyncio
import logging
import sys
import argparse
from datetime import datetime
from pathlib import Path

from .config import config
from .database import db_manager
from .scraper import CamaraScraper, scrape_vereadores_sync
from .utils import setup_logging, measure_time

logger = logging.getLogger(__name__)

class ScrapingOrchestrator:
    """Orquestrador principal do processo de scraping"""
    
    def __init__(self):
        self.scraper = None
        self.start_time = None
    
    async def initialize(self):
        """Inicializa componentes necessários"""
        logger.info("Inicializando sistema de scraping...")
        
        # Setup do banco de dados
        db_manager.initialize_pool(min_connections=2, max_connections=10)
        db_manager.create_tables()
        
        # Setup do scraper
        self.scraper = CamaraScraper()
        
        logger.info("Sistema inicializado com sucesso")
    
    async def run_full_scraping(self):
        """Executa o processo completo de scraping"""
        self.start_time = datetime.now()
        logger.info("=== INICIANDO SCRAPING COMPLETO ===")
        
        try:
            await self.initialize()
            
            async with self.scraper:
                # Etapa 1: Coletar informações básicas dos vereadores
                await self._step_basic_info()
                
                # Etapa 2: Download das imagens
                await self._step_download_images()
                
                # Etapa 3: Coletar proposituras resumidas
                await self._step_proposituras_summary()
                
                # Etapa 4: Coletar proposituras detalhadas
                await self._step_proposituras_detailed()
                
                # Etapa 5: Gerar relatório final
                await self._step_final_report()
            
        except Exception as e:
            logger.error(f"Erro durante o scraping: {e}")
            raise
        finally:
            await self._cleanup()
    
    async def _step_basic_info(self):
        """Etapa 1: Coleta informações básicas dos vereadores"""
        logger.info("=== ETAPA 1: Informações Básicas dos Vereadores ===")
        
        with measure_time("coleta_vereadores"):
            vereadores = await self.scraper.scrape_vereadores_info()
        
        if not vereadores:
            raise Exception("Nenhum vereador encontrado")
        
        # Salvar no banco
        rows_affected = db_manager.insert_vereadores(vereadores)
        logger.info(f"Salvos {rows_affected} vereadores no banco de dados")
    
    async def _step_download_images(self):
        """Etapa 2: Download das imagens dos vereadores"""
        logger.info("=== ETAPA 2: Download de Imagens ===")
        
        with measure_time("download_imagens"):
            images_count = await self.scraper.scrape_vereadores_images()
        
        logger.info(f"Download concluído: {images_count} imagens")
    
    async def _step_proposituras_summary(self):
        """Etapa 3: Coleta proposituras resumidas"""
        logger.info("=== ETAPA 3: Proposituras Resumidas ===")
        
        # Buscar vereadores do banco
        vereadores = scrape_vereadores_sync()  # Usar versão sync para compatibilidade
        
        all_proposituras = []
        
        for i, vereador in enumerate(vereadores, 1):
            logger.info(f"Processando resumo {i}/{len(vereadores)}: {vereador.nome}")
            
            with measure_time(f"resumo_{vereador.nome}"):
                proposituras = await self.scraper.scrape_proposituras_summary(vereador)
                all_proposituras.extend(proposituras)
            
            # Delay entre vereadores
            await asyncio.sleep(config.scraping.batch_delay)
        
        # Salvar proposituras resumidas usando pandas (compatibilidade com código existente)
        if all_proposituras:
            import pandas as pd
            df = pd.DataFrame(all_proposituras)
            df.to_sql('proposituras', db_manager.engine, if_exists='replace', index=False)
            logger.info(f"Salvadas {len(all_proposituras)} proposituras resumidas")
    
    async def _step_proposituras_detailed(self):
        """Etapa 4: Coleta proposituras detalhadas"""
        logger.info("=== ETAPA 4: Proposituras Detalhadas ===")
        
        # Obter links para proposituras detalhadas
        links_vereadores = await self.scraper.get_vereadores_proposituras_links()
        
        if not links_vereadores:
            logger.warning("Nenhum link para proposituras detalhadas encontrado")
            return
        
        all_proposituras = []
        
        for i, item in enumerate(links_vereadores, 1):
            vereador_nome = item['vereador']
            link = item['link']
            
            logger.info(f"Processando detalhadas {i}/{len(links_vereadores)}: {vereador_nome}")
            
            with measure_time(f"detalhadas_{vereador_nome}"):
                proposituras = await self.scraper.scrape_proposituras_detalhadas(
                    vereador_nome, link
                )
                all_proposituras.extend(proposituras)
            
            # Salvar em batches para não perder dados
            if len(all_proposituras) >= 100:
                rows_affected = db_manager.insert_proposituras_detalhadas(all_proposituras)
                logger.info(f"Salvadas {rows_affected} proposituras detalhadas (batch)")
                all_proposituras.clear()
            
            # Delay entre vereadores
            await asyncio.sleep(config.scraping.batch_delay)
        
        # Salvar proposituras restantes
        if all_proposituras:
            rows_affected = db_manager.insert_proposituras_detalhadas(all_proposituras)
            logger.info(f"Salvadas {rows_affected} proposituras detalhadas (final)")
    
    async def _step_final_report(self):
        """Etapa 5: Gerar relatório final"""
        logger.info("=== ETAPA 5: Relatório Final ===")
        
        stats = db_manager.get_statistics()
        
        logger.info("=== ESTATÍSTICAS FINAIS ===")
        logger.info(f"Vereadores: {stats.get('vereadores_count', 0)}")
        logger.info(f"Proposituras resumidas: {stats.get('proposituras_count', 0)}")
        logger.info(f"Proposituras detalhadas: {stats.get('proposituras_detalhadas_count', 0)}")
        logger.info(f"Links processados: {stats.get('links_proposituras_vereadores_count', 0)}")
        
        # Top 5 vereadores mais ativos
        top_vereadores = stats.get('proposituras_por_vereador', [])[:5]
        if top_vereadores:
            logger.info("=== TOP 5 VEREADORES MAIS ATIVOS ===")
            for i, item in enumerate(top_vereadores, 1):
                logger.info(f"{i}. {item['nome_vereador']}: {item['total']} proposituras")
        
        # Top 5 tipos de proposituras
        top_tipos = stats.get('proposituras_por_tipo', [])[:5]
        if top_tipos:
            logger.info("=== TOP 5 TIPOS DE PROPOSITURAS ===")
            for i, item in enumerate(top_tipos, 1):
                logger.info(f"{i}. {item['tipo']}: {item['total']} proposituras")
        
        # Tempo total
        if self.start_time:
            duration = datetime.now() - self.start_time
            logger.info(f"Tempo total de execução: {duration}")
    
    async def _cleanup(self):
        """Limpeza final"""
        logger.info("Executando limpeza final...")
        db_manager.close_pool()
        logger.info("Scraping finalizado")

async def run_basic_scraping():
    """Executa apenas coleta básica (vereadores + imagens)"""
    orchestrator = ScrapingOrchestrator()
    
    try:
        await orchestrator.initialize()
        
        async with orchestrator.scraper:
            await orchestrator._step_basic_info()
            await orchestrator._step_download_images()
            
        logger.info("Scraping básico concluído com sucesso")
        
    except Exception as e:
        logger.error(f"Erro no scraping básico: {e}")
        raise
    finally:
        await orchestrator._cleanup()

async def run_detailed_scraping():
    """Executa apenas coleta detalhada (proposituras)"""
    orchestrator = ScrapingOrchestrator()
    
    try:
        await orchestrator.initialize()
        
        async with orchestrator.scraper:
            await orchestrator._step_proposituras_detailed()
            await orchestrator._step_final_report()
        
        logger.info("Scraping detalhado concluído com sucesso")
        
    except Exception as e:
        logger.error(f"Erro no scraping detalhado: {e}")
        raise
    finally:
        await orchestrator._cleanup()

def main():
    """Função principal"""
    parser = argparse.ArgumentParser(description='Scraper da Câmara de Vereadores')
    parser.add_argument(
        '--mode', 
        choices=['full', 'basic', 'detailed'], 
        default='full',
        help='Modo de execução (default: full)'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Nível de log (default: INFO)'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(level=getattr(logging, args.log_level))
    
    # Executar modo selecionado
    try:
        if args.mode == 'full':
            orchestrator = ScrapingOrchestrator()
            asyncio.run(orchestrator.run_full_scraping())
        elif args.mode == 'basic':
            asyncio.run(run_basic_scraping())
        elif args.mode == 'detailed':
            asyncio.run(run_detailed_scraping())
            
    except KeyboardInterrupt:
        logger.info("Execução interrompida pelo usuário")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 