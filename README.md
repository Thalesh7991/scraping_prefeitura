# Câmara de Botucatu em Dados

Site público com a atuação dos vereadores da Câmara Municipal de Botucatu: propostas
apresentadas, taxa de aprovação, comparativos e busca — construído a partir de scraping do site
oficial (`camarabotucatu.sp.gov.br`).

Projeto pessoal de aprendizado que evoluiu de notebooks exploratórios (`notebooks/Ciclo1..5.ipynb`,
histórico mantido no repositório) para um pipeline de coleta (Python + SQLite) que alimenta dois
front-ends: um site estático (HTML/CSS/JS, a "porta de entrada" pública) e um dashboard Streamlit
(ferramenta interna para análises mais profundas).

## Arquitetura

```
src/
├── config.py               # URLs do site, parâmetros de busca, taxonomia de tipos/famílias
├── database.py              # Schema e acesso ao SQLite (data/camara_botucatu.db)
├── utils.py                  # HTTP com rate limiting/retry, parsing de datas/texto
├── scraper_vereadores.py    # Lista de vereadores + perfil (bio, legislaturas, comissões)
├── scraper_proposituras.py  # Busca paginada de proposituras (Siscam), autoria multi-vereador
├── export_json.py            # Exporta o recorte da legislatura atual para site/data/*.json
└── main.py                   # CLI orquestrador do scraper
site/                          # Site público estático (HTML/CSS/JS puro, identidade navy/dourado)
├── index.html                # Visão geral
├── vereador.html               # Perfil do vereador
├── comparar.html                # Comparar vereadores por tipo de atuação
├── buscar.html                    # Busca textual + filtros
├── assets/{style.css,data.js,layout.js,charts.js}
└── data/*.json                # Gerado por export_json.py - não versionado (ver .gitignore)
apps: streamlit_app.py        # Dashboard interno (Streamlit) - ferramenta de análise
setup_database.py             # Cria o arquivo SQLite e as tabelas
.github/workflows/
├── scrape.yml                # Roda o scraper sob demanda (validação, na main)
└── deploy-site.yml            # Scraper + export_json + publica site/ no GitHub Pages
```

## Fonte dos dados

O site da Câmara usa um sistema de busca avançada ("Siscam") para proposituras, acessível via
GET com filtros estruturados — sem necessidade de JavaScript/headless browser. A coleta usa:

- `GET /Vereadores` e `/Vereadores/Details?id=X` — vereadores atuais, biografia, legislaturas,
  mandatos em mesas diretoras e comissões.
- `GET /Siscam/Documentos?GrupoId=3&TipoAutorId=1&...` — proposituras de autoria de vereadores,
  paginada e ordenada por data decrescente. A coleta cobre a legislatura atual + anterior
  (2021–2028) e para automaticamente ao cruzar essa data de corte.

### Taxonomia das proposituras

"Propositura" é a categoria guarda-chuva; dentro dela existem tipos com naturezas bem diferentes,
agrupados em famílias usadas no dashboard:

| Família | Tipos | O que significa |
|---|---|---|
| Normativos | Projetos de Lei, Lei Complementar, Decreto Legislativo, Emenda à Lei Orgânica, Resolução | Pode virar lei/norma — é onde "taxa de aprovação" faz sentido |
| Fiscalização/Solicitações | Indicações, Requerimentos | Pedidos/sugestões ao Executivo ou à Mesa |
| Manifestações políticas | Moções | Manifestação simbólica (aplauso, repúdio, pesar), sem efeito normativo |
| Outros | Contas, Vetos | Naturezas distintas, tratadas à parte |

Vereadores da legislatura 2021–2024 que não estão mais em exercício não têm página de perfil
própria no site atual — são conhecidos apenas pelo nome extraído do campo "Autoria" das
proposituras (marcados com `perfil_completo=0` no banco).

### Escopo do banco vs. escopo do dashboard

O **banco de dados** guarda o histórico completo coletado (legislatura atual + anterior,
2021–2028) para permitir análises futuras (ex.: comparar mandatos, estudar reeleições).

O **dashboard público**, por outro lado, existe para a população acompanhar o trabalho dos
vereadores *em exercício* — por isso ele filtra automaticamente para mostrar apenas: (1)
proposituras a partir do início do mandato vigente e (2) vereadores com perfil completo (ou
seja, que estão na listagem atual do site). Vereadores da legislatura anterior que não foram
reeleitos não aparecem no dashboard, mesmo estando no banco.

## Uso

```bash
pip install -r requirements.txt

# Cria o banco (idempotente, roda também na primeira vez que o scraper for executado)
python setup_database.py

# Coleta completa (vereadores + proposituras)
python -m src.main --mode full

# Só vereadores, ou só proposituras
python -m src.main --mode vereadores
python -m src.main --mode proposituras

# Exporta o recorte da legislatura atual para site/data/*.json
python -m src.export_json

# Site estático local (a partir da pasta site/)
cd site && python -m http.server 8080   # depois abra http://localhost:8080/index.html

# Dashboard interno (Streamlit)
streamlit run streamlit_app.py
```

O banco (`data/camara_botucatu.db`) e o JSON exportado (`site/data/*.json`) **não são
versionados** (estão no `.gitignore`) - são gerados localmente pelos comandos acima, ou pelo
workflow de deploy antes de publicar o site. Abrir os arquivos `.html` direto (`file://`) não
funciona - o navegador bloqueia o carregamento do JSON local por segurança; é preciso servir via
um servidor (local, acima, ou o GitHub Pages em produção).

## Atualização automática e publicação

`.github/workflows/deploy-site.yml` roda diariamente (e a cada push nesta branch): executa o
scraper, gera o JSON com `export_json.py` e publica a pasta `site/` no GitHub Pages via
`actions/deploy-pages`. **Configuração única necessária no GitHub**: em Settings → Pages,
definir Source = "GitHub Actions" no repositório.

`.github/workflows/scrape.yml` continua existindo só como verificação sob demanda de que o
scraper funciona contra o site oficial (não publica nada).

## Notebooks antigos

`notebooks/Ciclo1.ipynb` a `Ciclo5.ipynb` e `exemplo_uso.ipynb` são o histórico de aprendizado que
deu origem a este projeto (scraping da versão antiga do site, hoje fora do ar). Não fazem mais
parte do pipeline ativo, mas ficam no repositório como registro da evolução do projeto.

`archive/img/` guarda as fotos baixadas pelo scraper antigo (site anterior) - mantidas por
histórico; o scraper atual não baixa mais fotos, usa o link direto (`foto_url`) do site oficial.
