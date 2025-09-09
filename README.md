# Scraper Câmara de Vereadores - Botucatu

Sistema completo para coleta e análise de dados dos vereadores da Câmara Municipal de Botucatu.

## 🚀 Características

- **Scraping Assíncrono**: Utiliza `aiohttp` para requisições paralelas eficientes
- **Rate Limiting**: Controle inteligente da taxa de requisições
- **Banco de Dados Otimizado**: PostgreSQL com connection pooling e índices
- **Tratamento de Erros**: Sistema robusto com retry automático
- **Logging Completo**: Logs detalhados para monitoramento
- **Métricas**: Coleta de estatísticas de performance
- **Modular**: Arquitetura limpa e extensível

## 📋 Pré-requisitos

- Python 3.8+
- PostgreSQL 12+
- Conexão com internet

## 🛠 Instalação

1. Clone o repositório:
```bash
git clone <seu-repo>
cd scraping_prefeitura
```

2. Crie um ambiente virtual:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Configure as variáveis de ambiente:
```bash
cp .env.example .env
# Edite o arquivo .env com suas configurações
```

## ⚙️ Configuração

Crie um arquivo `.env` na raiz do projeto:

```env
# Configurações do Banco de Dados
HOST=localhost
PORT=5432
USER=postgres
PASSWORD=sua_senha
DBNAME=prefeitura

# Configurações opcionais do scraping
MIN_YEAR=2021
REQUEST_DELAY=1.0
BATCH_DELAY=10.0
```

## 🎯 Uso

### Execução Completa
```bash
python -m src.main --mode full
```

### Apenas Dados Básicos
```bash
python -m src.main --mode basic
```

### Apenas Proposituras Detalhadas
```bash
python -m src.main --mode detailed
```

### Com Nível de Log Personalizado
```bash
python -m src.main --mode full --log-level DEBUG
```

## 📊 Estrutura dos Dados

### Tabelas Principais

1. **vereadores**: Informações básicas dos vereadores
2. **proposituras**: Resumo quantitativo por ano/tipo
3. **proposituras_detalhadas**: Dados detalhados de cada propositura
4. **imagens_vereadores**: Fotos dos vereadores
5. **links_proposituras_vereadores**: Controle de URLs processadas

### Exemplo de Uso Programático

```python
import asyncio
from src import ScrapingOrchestrator, db_manager

async def exemplo():
    orchestrator = ScrapingOrchestrator()
    await orchestrator.run_full_scraping()
    
    # Obter estatísticas
    stats = db_manager.get_statistics()
    print(f"Total de vereadores: {stats['vereadores_count']}")

# Executar
asyncio.run(exemplo())
```

## 🔧 Arquitetura

```
src/
├── __init__.py          # Pacote principal
├── config.py            # Configurações centralizadas
├── database.py          # Gerenciamento do banco de dados
├── scraper.py           # Lógica de scraping
├── main.py              # Orquestrador principal
└── utils.py             # Utilitários e helpers
```

### Principais Classes

- **`CamaraScraper`**: Scraper principal com suporte assíncrono
- **`DatabaseManager`**: Gerenciador de conexões e operações do BD
- **`ScrapingOrchestrator`**: Orquestrador do processo completo
- **`MetricsCollector`**: Coletor de métricas de performance

## 📈 Performance

### Melhorias Implementadas

1. **Requisições Assíncronas**: 3-5x mais rápido que versão síncrona
2. **Connection Pooling**: Reutilização eficiente de conexões
3. **Batch Inserts**: Inserção em lote no banco de dados
4. **Rate Limiting**: Evita sobrecarga do servidor
5. **Retry Logic**: Recuperação automática de falhas

### Benchmarks Típicos

- **Coleta básica**: ~2-3 minutos
- **Proposituras resumidas**: ~5-10 minutos
- **Proposituras detalhadas**: ~30-60 minutos (dependendo da quantidade)

## 🔍 Monitoramento

### Logs
- Logs detalhados salvos em `logs/scraping_YYYYMMDD_HHMMSS.log`
- Diferentes níveis: DEBUG, INFO, WARNING, ERROR

### Métricas
- Tempo de execução por operação
- Número de requisições realizadas
- Taxa de sucesso/erro
- Quantidade de dados coletados

## 🐛 Tratamento de Erros

- **Retry automático** com backoff exponencial
- **Timeouts configuráveis** para requisições
- **Validação de dados** antes da inserção
- **Rollback automático** em caso de erro no banco

## 🔄 Migração dos Notebooks

Se você está vindo dos notebooks antigos:

1. **Ciclo1.ipynb** → `scraper.scrape_vereadores_info()`
2. **Ciclo2.ipynb** → `scraper.scrape_vereadores_images()`
3. **Ciclo3.ipynb** → `database.insert_vereadores()` + melhorias
4. **Ciclo4.ipynb** → `scraper.scrape_proposituras_detalhadas()`
5. **Ciclo5.ipynb** → Versão assíncrona completa

## 🚀 Próximos Passos

### Dashboard (Planejado)
- Interface web com Streamlit/Dash
- Gráficos interativos de produtividade
- Filtros por vereador, partido, período
- Comparativos e rankings

### Analytics (Planejado)
- Análise de sentimento das proposituras
- Clustering de temas/assuntos
- Predição de aprovação de projetos
- Relatórios automatizados

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📝 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## 📞 Contato

Thales Pinto - [seu-email]

Link do Projeto: [https://github.com/seu-usuario/scraping_prefeitura](https://github.com/seu-usuario/scraping_prefeitura)

---

## 🎯 Comparação: Antes vs Depois

### Antes (Notebooks)
- ❌ Código duplicado entre notebooks
- ❌ Sem tratamento robusto de erros
- ❌ Requisições síncronas lentas
- ❌ Sem logging estruturado
- ❌ Conexões de banco não otimizadas
- ❌ Difícil manutenção e extensão

### Depois (Versão Refatorada)
- ✅ Código modular e reutilizável
- ✅ Tratamento robusto de erros com retry
- ✅ Requisições assíncronas 3-5x mais rápidas
- ✅ Logging completo e métricas
- ✅ Connection pooling e batch operations
- ✅ Fácil manutenção e extensão
- ✅ Pronto para produção 