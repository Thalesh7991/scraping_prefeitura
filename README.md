# Câmara de Botucatu em Dados

Dashboard público com a atuação dos vereadores da Câmara Municipal de Botucatu: proposituras
apresentadas, taxa de aprovação de projetos, rankings e busca — construído a partir de scraping
do site oficial (`camarabotucatu.sp.gov.br`).

Projeto pessoal de aprendizado que evoluiu de notebooks exploratórios (`src/Ciclo1..5.ipynb`,
histórico mantido no repositório) para um pipeline de coleta + banco SQLite + dashboard Streamlit.

## Arquitetura

```
src/
├── config.py               # URLs do site, parâmetros de busca, taxonomia de tipos/famílias
├── database.py              # Schema e acesso ao SQLite (data/camara_botucatu.db)
├── utils.py                  # HTTP com rate limiting/retry, parsing de datas/texto
├── scraper_vereadores.py    # Lista de vereadores + perfil (bio, legislaturas, comissões)
├── scraper_proposituras.py  # Busca paginada de proposituras (Siscam), autoria multi-vereador
└── main.py                   # CLI orquestrador
streamlit_app.py              # Dashboard (Streamlit)
setup_database.py             # Cria o arquivo SQLite e as tabelas
.github/workflows/scrape.yml  # Roda o scraper sob demanda (validação)
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

# Dashboard local
streamlit run streamlit_app.py
```

O banco gerado é um único arquivo (`data/camara_botucatu.db`), **não versionado no repositório**
(está no `.gitignore` - é um binário que muda todo dia, sem diff legível). Rode o comando acima
localmente para gerá-lo antes de usar o dashboard.

## Atualização automática

`.github/workflows/scrape.yml` hoje só roda sob demanda (`workflow_dispatch`), como verificação
de que o scraper continua funcionando contra o site oficial - o agendamento diário e a publicação
dos dados estão sendo redesenhados (ver branch `web-publico`: a ideia é exportar os dados para
JSON e publicar um site estático via GitHub Pages, em vez de commitar o `.db`).

## Notebooks antigos

`src/Ciclo1.ipynb` a `Ciclo5.ipynb` e `exemplo_uso.ipynb` são o histórico de aprendizado que deu
origem a este projeto (scraping da versão antiga do site, hoje fora do ar). Não fazem mais parte
do pipeline ativo, mas ficam no repositório como registro da evolução do projeto.
