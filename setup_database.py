#!/usr/bin/env python3
"""
Script para configurar o banco de dados PostgreSQL
Baseado nas estruturas desenvolvidas nos notebooks originais
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def get_db_config():
    """Obtém configurações do banco de dados"""
    return {
        'host': os.getenv('HOST', 'localhost'),
        'port': os.getenv('PORT', '5432'),
        'user': os.getenv('USER', 'postgres'),
        'password': os.getenv('PASSWORD', ''),
        'dbname': os.getenv('DBNAME', 'prefeitura')
    }

def create_database():
    """Cria o banco de dados se não existir"""
    config = get_db_config()
    dbname = config['dbname']
    
    # Conectar sem especificar o banco para criar o banco
    conn_config = config.copy()
    conn_config.pop('dbname')
    
    try:
        print(f"Conectando ao PostgreSQL em {config['host']}:{config['port']}...")
        conn = psycopg2.connect(**conn_config)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        cursor = conn.cursor()
        
        # Verificar se o banco já existe
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (dbname,))
        exists = cursor.fetchone()
        
        if not exists:
            print(f"Criando banco de dados '{dbname}'...")
            cursor.execute(f'CREATE DATABASE "{dbname}"')
            print(f"✅ Banco de dados '{dbname}' criado com sucesso!")
        else:
            print(f"✅ Banco de dados '{dbname}' já existe.")
        
        cursor.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"❌ Erro ao criar banco de dados: {e}")
        raise

def create_tables():
    """Cria todas as tabelas necessárias baseadas nos notebooks"""
    config = get_db_config()
    
    try:
        print(f"Conectando ao banco '{config['dbname']}'...")
        conn = psycopg2.connect(**config)
        cursor = conn.cursor()
        
        print("Criando tabelas...")
        
        # Tabela de vereadores (baseada no Ciclo1 e Ciclo2)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vereadores (
                id SERIAL PRIMARY KEY,
                nome_vereador VARCHAR(100) NOT NULL,
                partido_vereador VARCHAR(100) NOT NULL,
                link_vereador VARCHAR(300),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(nome_vereador)
            );
        """)
        print("✅ Tabela 'vereadores' criada/verificada")
        
        # Tabela de proposituras resumidas (baseada no Ciclo3)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proposituras (
                id SERIAL PRIMARY KEY,
                tipo VARCHAR(100) NOT NULL,
                quantidade INTEGER NOT NULL,
                ano VARCHAR(10) NOT NULL,
                vereador VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX_KEY VARCHAR(200) GENERATED ALWAYS AS (vereador || '_' || tipo || '_' || ano) STORED,
                UNIQUE(vereador, tipo, ano)
            );
        """)
        print("✅ Tabela 'proposituras' criada/verificada")
        
        # Tabela de proposituras detalhadas (baseada no Ciclo4 e Ciclo5)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proposituras_detalhadas (
                id SERIAL PRIMARY KEY,
                nome_vereador VARCHAR(100) NOT NULL,
                tipo VARCHAR(100) NOT NULL,
                situacao VARCHAR(100) NOT NULL,
                data_propositura DATE NOT NULL,
                link_propositura VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(nome_vereador, tipo, data_propositura, situacao)
            );
        """)
        print("✅ Tabela 'proposituras_detalhadas' criada/verificada")
        
        # Tabela de imagens dos vereadores (baseada no Ciclo2 e Ciclo3)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS imagens_vereadores (
                id SERIAL PRIMARY KEY,
                vereador VARCHAR(100) NOT NULL,
                imagem BYTEA NOT NULL,
                nome_arquivo VARCHAR(200),
                tamanho_bytes INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(vereador)
            );
        """)
        print("✅ Tabela 'imagens_vereadores' criada/verificada")
        
        # Tabela de controle de links processados (baseada no Ciclo4)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS links_proposituras_vereadores (
                id SERIAL PRIMARY KEY,
                nome_vereador VARCHAR(100) NOT NULL,
                link VARCHAR(500) NOT NULL,
                processed BOOLEAN DEFAULT FALSE,
                processed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(nome_vereador, link)
            );
        """)
        print("✅ Tabela 'links_proposituras_vereadores' criada/verificada")
        
        # Tabela de log de scraping (nova - para monitoramento)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scraping_log (
                id SERIAL PRIMARY KEY,
                operation VARCHAR(100) NOT NULL,
                status VARCHAR(50) NOT NULL,
                vereador VARCHAR(100),
                details TEXT,
                error_message TEXT,
                started_at TIMESTAMP NOT NULL,
                finished_at TIMESTAMP,
                duration_seconds INTEGER
            );
        """)
        print("✅ Tabela 'scraping_log' criada/verificada")
        
        # Criar índices para melhor performance
        print("Criando índices para otimização...")
        
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_proposituras_vereador ON proposituras(vereador);",
            "CREATE INDEX IF NOT EXISTS idx_proposituras_ano ON proposituras(ano);",
            "CREATE INDEX IF NOT EXISTS idx_proposituras_tipo ON proposituras(tipo);",
            "CREATE INDEX IF NOT EXISTS idx_proposituras_detalhadas_vereador ON proposituras_detalhadas(nome_vereador);",
            "CREATE INDEX IF NOT EXISTS idx_proposituras_detalhadas_data ON proposituras_detalhadas(data_propositura);",
            "CREATE INDEX IF NOT EXISTS idx_proposituras_detalhadas_tipo ON proposituras_detalhadas(tipo);",
            "CREATE INDEX IF NOT EXISTS idx_links_processed ON links_proposituras_vereadores(processed);",
            "CREATE INDEX IF NOT EXISTS idx_links_vereador ON links_proposituras_vereadores(nome_vereador);",
            "CREATE INDEX IF NOT EXISTS idx_scraping_log_operation ON scraping_log(operation);",
            "CREATE INDEX IF NOT EXISTS idx_scraping_log_status ON scraping_log(status);",
        ]
        
        for index_sql in indices:
            cursor.execute(index_sql)
        
        print("✅ Índices criados/verificados")
        
        # Commit das alterações
        conn.commit()
        
        # Verificar tabelas criadas
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        
        tabelas = cursor.fetchall()
        print(f"\n📊 Tabelas disponíveis no banco '{config['dbname']}':")
        for i, (tabela,) in enumerate(tabelas, 1):
            cursor.execute(f"SELECT COUNT(*) FROM {tabela}")
            count = cursor.fetchone()[0]
            print(f"   {i}. {tabela} ({count} registros)")
        
        cursor.close()
        conn.close()
        
        print(f"\n🎉 Banco de dados configurado com sucesso!")
        
    except psycopg2.Error as e:
        print(f"❌ Erro ao criar tabelas: {e}")
        raise

def insert_sample_data():
    """Insere dados de exemplo para teste"""
    config = get_db_config()
    
    try:
        conn = psycopg2.connect(**config)
        cursor = conn.cursor()
        
        print("Inserindo dados de exemplo...")
        
        # Inserir vereador de exemplo
        cursor.execute("""
            INSERT INTO vereadores (nome_vereador, partido_vereador, link_vereador)
            VALUES (%s, %s, %s)
            ON CONFLICT (nome_vereador) DO NOTHING
        """, ("Vereador Teste", "Partido Teste", "http://exemplo.com"))
        
        # Inserir propositura de exemplo
        cursor.execute("""
            INSERT INTO proposituras (tipo, quantidade, ano, vereador)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (vereador, tipo, ano) DO NOTHING
        """, ("Requerimentos", 10, "2024", "Vereador Teste"))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Dados de exemplo inseridos")
        
    except psycopg2.Error as e:
        print(f"❌ Erro ao inserir dados de exemplo: {e}")

def test_connection():
    """Testa a conexão com o banco"""
    config = get_db_config()
    
    try:
        print("Testando conexão...")
        conn = psycopg2.connect(**config)
        cursor = conn.cursor()
        
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✅ Conexão bem-sucedida!")
        print(f"   PostgreSQL: {version}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Erro de conexão: {e}")
        return False

def main():
    """Função principal"""
    print("🐘 Configurador do Banco PostgreSQL - Scraper Câmara de Vereadores")
    print("=" * 70)
    
    # Verificar se arquivo .env existe
    if not os.path.exists('.env'):
        print("❌ Arquivo .env não encontrado!")
        print("   Crie um arquivo .env com as configurações do banco:")
        print("""
HOST=localhost
PORT=5432
USER=postgres
PASSWORD=sua_senha
DBNAME=prefeitura
        """)
        return
    
    config = get_db_config()
    print(f"📋 Configurações:")
    print(f"   Host: {config['host']}:{config['port']}")
    print(f"   Usuário: {config['user']}")
    print(f"   Banco: {config['dbname']}")
    print()
    
    try:
        # Passo 1: Criar banco de dados
        create_database()
        
        # Passo 2: Testar conexão
        if not test_connection():
            return
        
        # Passo 3: Criar tabelas
        create_tables()
        
        # Passo 4: Inserir dados de exemplo (opcional)
        resposta = input("\n🤔 Deseja inserir dados de exemplo para teste? (s/N): ")
        if resposta.lower() in ['s', 'sim', 'y', 'yes']:
            insert_sample_data()
        
        print("\n🎉 Configuração concluída com sucesso!")
        print("\nPróximos passos:")
        print("1. Execute o scraper: python -m src.main --mode basic")
        print("2. Ou use o notebook: exemplo_uso.ipynb")
        
    except Exception as e:
        print(f"\n❌ Erro durante a configuração: {e}")
        print("\nVerifique:")
        print("- PostgreSQL está rodando?")
        print("- Credenciais no .env estão corretas?")
        print("- Usuário tem permissões para criar banco/tabelas?")

if __name__ == "__main__":
    main() 