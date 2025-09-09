import psycopg2
import psycopg2.extras
from psycopg2 import pool
import pandas as pd
from sqlalchemy import create_engine
from typing import List, Dict, Any, Optional, Tuple
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from .config import config

logger = logging.getLogger(__name__)

@dataclass
class Vereador:
    """Modelo de dados para vereador"""
    nome: str
    partido: str
    link: Optional[str] = None

@dataclass
class Propositura:
    """Modelo de dados para propositura"""
    vereador: str
    tipo: str
    situacao: str
    data: datetime

class DatabaseManager:
    """Gerenciador de conexões e operações com banco de dados"""
    
    def __init__(self):
        self.config = config.database
        self._connection_pool = None
        self._engine = None
    
    def initialize_pool(self, min_connections: int = 1, max_connections: int = 10):
        """Inicializa o pool de conexões"""
        try:
            self._connection_pool = psycopg2.pool.ThreadedConnectionPool(
                min_connections,
                max_connections,
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.dbname
            )
            logger.info(f"Pool de conexões inicializado: {min_connections}-{max_connections}")
        except Exception as e:
            logger.error(f"Erro ao inicializar pool de conexões: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Context manager para obter conexão do pool"""
        if not self._connection_pool:
            self.initialize_pool()
        
        connection = None
        try:
            connection = self._connection_pool.getconn()
            yield connection
        except Exception as e:
            if connection:
                connection.rollback()
            logger.error(f"Erro na conexão: {e}")
            raise
        finally:
            if connection:
                self._connection_pool.putconn(connection)
    
    @property
    def engine(self):
        """Lazy loading do SQLAlchemy engine"""
        if not self._engine:
            self._engine = create_engine(self.config.connection_string)
        return self._engine
    
    def create_tables(self):
        """Cria todas as tabelas necessárias"""
        tables_sql = {
            'vereadores': """
                CREATE TABLE IF NOT EXISTS vereadores (
                    id SERIAL PRIMARY KEY,
                    nome_vereador VARCHAR(100) NOT NULL,
                    partido_vereador VARCHAR(100) NOT NULL,
                    link_vereador VARCHAR(200),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(nome_vereador)
                );
            """,
            'proposituras': """
                CREATE TABLE IF NOT EXISTS proposituras (
                    id SERIAL PRIMARY KEY,
                    tipo VARCHAR(100) NOT NULL,
                    quantidade INTEGER NOT NULL,
                    ano VARCHAR(10) NOT NULL,
                    vereador VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """,
            'proposituras_detalhadas': """
                CREATE TABLE IF NOT EXISTS proposituras_detalhadas (
                    id SERIAL PRIMARY KEY,
                    nome_vereador VARCHAR(100) NOT NULL,
                    tipo VARCHAR(100) NOT NULL,
                    situacao VARCHAR(100) NOT NULL,
                    data_propositura DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(nome_vereador, tipo, data_propositura)
                );
            """,
            'imagens_vereadores': """
                CREATE TABLE IF NOT EXISTS imagens_vereadores (
                    id SERIAL PRIMARY KEY,
                    vereador VARCHAR(100) NOT NULL,
                    imagem BYTEA NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(vereador)
                );
            """,
            'links_proposituras_vereadores': """
                CREATE TABLE IF NOT EXISTS links_proposituras_vereadores (
                    id SERIAL PRIMARY KEY,
                    nome_vereador VARCHAR(100) NOT NULL,
                    link VARCHAR(300) NOT NULL,
                    processed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(nome_vereador, link)
                );
            """,
            'scraping_log': """
                CREATE TABLE IF NOT EXISTS scraping_log (
                    id SERIAL PRIMARY KEY,
                    operation VARCHAR(100) NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    details TEXT,
                    started_at TIMESTAMP NOT NULL,
                    finished_at TIMESTAMP,
                    duration_seconds INTEGER
                );
            """
        }
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                for table_name, sql in tables_sql.items():
                    cursor.execute(sql)
                    logger.info(f"Tabela {table_name} criada/verificada")
                
                # Criar índices para melhor performance
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_proposituras_vereador ON proposituras(vereador);",
                    "CREATE INDEX IF NOT EXISTS idx_proposituras_detalhadas_vereador ON proposituras_detalhadas(nome_vereador);",
                    "CREATE INDEX IF NOT EXISTS idx_proposituras_detalhadas_data ON proposituras_detalhadas(data_propositura);",
                    "CREATE INDEX IF NOT EXISTS idx_links_processed ON links_proposituras_vereadores(processed);",
                ]
                
                for index_sql in indexes:
                    cursor.execute(index_sql)
                
                conn.commit()
                logger.info("Todas as tabelas e índices foram criados com sucesso")
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Erro ao criar tabelas: {e}")
                raise
    
    def insert_vereadores(self, vereadores: List[Vereador]) -> int:
        """Insere vereadores em lote usando UPSERT"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                insert_sql = """
                    INSERT INTO vereadores (nome_vereador, partido_vereador, link_vereador)
                    VALUES %s
                    ON CONFLICT (nome_vereador) 
                    DO UPDATE SET 
                        partido_vereador = EXCLUDED.partido_vereador,
                        link_vereador = EXCLUDED.link_vereador
                """
                
                values = [(v.nome, v.partido, v.link) for v in vereadores]
                psycopg2.extras.execute_values(cursor, insert_sql, values)
                
                rows_affected = cursor.rowcount
                conn.commit()
                logger.info(f"{rows_affected} vereadores inseridos/atualizados")
                return rows_affected
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Erro ao inserir vereadores: {e}")
                raise
    
    def insert_proposituras_detalhadas(self, proposituras: List[Propositura]) -> int:
        """Insere proposituras detalhadas em lote"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                insert_sql = """
                    INSERT INTO proposituras_detalhadas (nome_vereador, tipo, situacao, data_propositura)
                    VALUES %s
                    ON CONFLICT (nome_vereador, tipo, data_propositura) 
                    DO UPDATE SET situacao = EXCLUDED.situacao
                """
                
                values = [(p.vereador, p.tipo, p.situacao, p.data) for p in proposituras]
                psycopg2.extras.execute_values(cursor, insert_sql, values)
                
                rows_affected = cursor.rowcount
                conn.commit()
                logger.info(f"{rows_affected} proposituras inseridas/atualizadas")
                return rows_affected
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Erro ao inserir proposituras: {e}")
                raise
    
    def link_exists(self, link: str, nome_vereador: str) -> bool:
        """Verifica se um link já foi processado"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM links_proposituras_vereadores WHERE link = %s AND nome_vereador = %s",
                (link, nome_vereador)
            )
            return cursor.fetchone() is not None
    
    def insert_link(self, link: str, nome_vereador: str):
        """Insere um link processado"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """INSERT INTO links_proposituras_vereadores (nome_vereador, link, processed) 
                       VALUES (%s, %s, TRUE) ON CONFLICT DO NOTHING""",
                    (nome_vereador, link)
                )
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Erro ao inserir link: {e}")
                raise
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estatísticas do banco de dados"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            stats = {}
            
            # Contagem de registros por tabela
            tables = ['vereadores', 'proposituras', 'proposituras_detalhadas', 'links_proposituras_vereadores']
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                stats[f"{table}_count"] = cursor.fetchone()['count']
            
            # Proposituras por vereador
            cursor.execute("""
                SELECT nome_vereador, COUNT(*) as total
                FROM proposituras_detalhadas 
                GROUP BY nome_vereador 
                ORDER BY total DESC
            """)
            stats['proposituras_por_vereador'] = cursor.fetchall()
            
            # Proposituras por tipo
            cursor.execute("""
                SELECT tipo, COUNT(*) as total
                FROM proposituras_detalhadas 
                GROUP BY tipo 
                ORDER BY total DESC
            """)
            stats['proposituras_por_tipo'] = cursor.fetchall()
            
            return stats
    
    def export_to_csv(self, table_name: str, file_path: str):
        """Exporta tabela para CSV"""
        df = pd.read_sql_table(table_name, self.engine)
        df.to_csv(file_path, index=False)
        logger.info(f"Tabela {table_name} exportada para {file_path}")
    
    def close_pool(self):
        """Fecha o pool de conexões"""
        if self._connection_pool:
            self._connection_pool.closeall()
            logger.info("Pool de conexões fechado")

# Instância global do gerenciador
db_manager = DatabaseManager() 