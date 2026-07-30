# Roadmap — Câmara de Botucatu em Dados

Backlog de ideias discutidas e ainda não implementadas, para não perder o contexto entre sessões.

## Em aberto

### 1. Classificação por Tema/Assunto (o que a Câmara está tratando de fato)
Hoje só categorizamos por **tipo formal** (Projeto de Lei, Requerimento, Moção...) e **família**
(Normativos, Fiscalização/Solicitações, Manifestações políticas, Outros). Isso não diz nada sobre
**o assunto** (saúde, educação, infraestrutura, segurança...), que é o que realmente importa pro
cidadão entender o que a Câmara prioriza.

**Proposta**: classificar cada propositura por palavras-chave no campo `ementa` (mesmo padrão
determinístico/transparente usado hoje pra família/situação, calculado em Python no
`export_json.py`, sem depender de API/LLM). Taxonomia a validar antes de implementar: Saúde,
Educação, Infraestrutura/Vias, Segurança, Meio Ambiente, Transporte, Assistência Social,
Cultura/Esporte/Lazer, Administração/Finanças, Homenagens/Datas. Precisa de uma rodada de
validação da lista de palavras-chave por tema antes de programar (ver seção "Antes de
implementar" abaixo).

Contexto: perguntei "os vereadores não estão fazendo coisas inúteis?" — os números atuais não
sustentam essa hipótese com força (Moções = 11% do total, votos de pesar = 5%), mas isso só
mede "quanto é cerimonial", não "sobre o que estão tratando". A classificação por tema resolve
essa lacuna.

### 2. "Mais atuante" e "menos atuante" lado a lado (ferramenta crítica, não só elogio)
Hoje o vereador com menos proposituras já aparece (implícito) no topo do gráfico de ranking, mas
sem destaque. Pedido explícito: tornar isso simétrico e visível — a ferramenta deve ajudar a
população a ver problemas, não só quem está indo bem.

**Cuidado a resolver antes de implementar**: comparar por quantidade bruta pode ser injusto com
quem está licenciado por parte do mandato, é novo no cargo (suplente que assumiu no meio do
período), ou propôs poucos projetos mas de mais peso/qualidade. Decisão pendente: mostrar o
número cru mesmo assim (é fato) mas com contexto visível ao lado (data de início no mandato,
status licenciado) — a validar o formato exato com o usuário antes de programar.

### 3. Gastos da Câmara (salários, diárias/viagens, outras despesas)
Investigação feita em 2026-07-30 na página `/Transparencia` do site oficial.

**O que existe**: a própria Câmara não tem uma seção de gastos na Siscam - o link
"Transparência" do menu principal só repete o menu do site. Porém, o rodapé desse menu aponta pra
um **portal de transparência de terceiros** (fornecedor Fiorilli, comum em prefeituras/câmaras
brasileiras), em `https://botucatusp.dcfiorilli.com.br:879/transparenciacamara/`. Esse portal TEM
dados estruturados relevantes:
- **Diárias e Passagens** (`HomeDiarias.ASPX`) — exatamente "viagens"
- **Servidores / Relatório de Servidores / Relação de Cargos Providos e Vagos** — provavelmente
  folha de pagamento/salários
- **Verbas Indenizatórias** — pagamentos de indenização (item sensível de transparência para
  vereadores especificamente)
- Dezenas de relatórios de **Despesas** (por fornecedor, elemento, órgão, função, etc.),
  **Contratos** e **Licitações**

**O problema técnico**: é um site **ASP.NET WebForms antigo**. As tabelas de dados não vêm num GET
simples (testei `HomeDiarias.ASPX` direto: página carrega mas sem nenhum valor "R$" - os dados só
aparecem depois de um filtro interativo via postback). A página de Servidores
(`ServidoresTeste.aspx`) retornou **erro 500** ao acessar direto, sem uma sessão/contexto válido
vindo da home. Os botões de exportar CSV/XLS também são botões de postback (`__doPostBack`), não
links diretos de download.

Ou seja: dá pra pegar esses dados, mas exige **replicar o ciclo de postback do ASP.NET**
(capturar `__VIEWSTATE`/`__EVENTVALIDATION` da página e reenviar via POST) **ou** automação via
navegador (Playwright) - um scraper bem mais complexo que o da Siscam (que é GET puro). Não é
"fazer rapidinho" - é uma frente de trabalho própria, com um scraper novo e dedicado.

**Recomendação**: vale a pena pela relevância (gasto de dinheiro público é um dos pilares de
fiscalização mais importantes), mas tratar como iniciativa separada do site atual, não como
extensão trivial do scraper existente.

## Descartado

### Faltas/frequência dos vereadores em sessões
Investigado em 2026-07-30. **Não há dado estruturado disponível publicamente**: as páginas de
sessões (`/Siscam/Reunioes`) só mostram data/hora/observações, sem lista de presença; o "Relatório
Anual de Atividades" (PDF de 477 páginas, baixado e com texto extraído por completo) não contém
nenhuma menção a falta/ausência/presença/frequência. Não achamos vestígio dessa informação em
nenhuma página do site oficial. Conclusão: abandonado por falta de fonte, não por falta de
esforço - só reabrir se descobrirmos uma fonte nova (ex.: pedido via e-SIC).

## Antes de implementar qualquer item acima
Alinhar com o usuário: taxonomia de temas (lista de categorias e palavras-chave), formato de
apresentação do "menos atuante", e se/quando vale investir no scraper do portal Fiorilli.
