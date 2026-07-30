# Roadmap — Câmara de Botucatu em Dados

Backlog de ideias discutidas e ainda não implementadas, para não perder o contexto entre sessões.

## Feito

### Remuneração dos vereadores (salário) — `src/scraper_transparencia.py`
Implementado em 2026-07-30. Usa Playwright contra o portal de transparência de terceiros
(Fiorilli) - ver detalhes técnicos da investigação no item "Gastos da Câmara" abaixo. Resultado:
seção **Servidores → Servidores Ativos** do portal tem nome, cargo e valor líquido/mês, batendo
100% com os nomes da nossa tabela `vereadores` (76 registros coletados para 2026, zero sem
correspondência). Sabe distinguir titular licenciado de suplente que assumiu o cargo (o suplente
aparece com cargo "VEREADOR SUPLENTE" recebendo o salário, o titular licenciado não aparece).

**Limitação conhecida**: o seletor global "Escolha o Exercício" (trocar de ano) trava o portal
num estado de "Processando..." que não retorna em tempo hábil (bug do próprio portal, não do
nosso scraper) - por isso só coletamos o ano corrente de forma confiável por enquanto; anos
anteriores (2025, ou histórico 2021-2024) ficam pendentes até resolvermos essa troca de ano ou
encontrarmos outro caminho (ex.: parâmetro de URL direto, se existir).

Diárias e Passagens e Verbas Indenizatórias foram descartadas nessa investigação (ver abaixo) -
não fazem parte do que foi implementado.

`src/export_json.py` já gera `site/data/remuneracao.json` com esses dados. **Ainda falta**: uma
página no site (`site/`) pra exibir isso - não construída nesta rodada, só o scraper + banco +
JSON estão prontos.

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

### 3. Gastos da Câmara — próximos passos (parte já feita, ver "Feito" acima)
Investigação original em 2026-07-30 na página `/Transparencia` do site oficial, que levou ao
portal de terceiros (Fiorilli) em `https://botucatusp.dcfiorilli.com.br:879/transparenciacamara/`
- ver `src/scraper_transparencia.py` pro que já foi implementado (salário/remuneração).

**Ainda não implementado dessa investigação**:
- **Resolver a troca de "Exercício"** (ano) para coletar 2025 e o histórico 2021-2024 - hoje só
  o ano corrente é coletado (ver limitação em "Feito" acima).
- **Diárias e Passagens** (`HomeDiarias.ASPX`) - checado e **descartado por baixo valor**: só 8
  registros em 5+ anos, todos pagos a uma empresa de cartão corporativo (GIMAVE), não a
  vereadores por nome. Se quisermos o gasto individual de viagem, o caminho seria "Cartões
  Corporativos/Suprimentos de Fundos" (não investigado ainda).
- **Verbas Indenizatórias** - checado e **descartado**: zero registros em todo o período
  2021-2026 para essa Câmara.
- Dezenas de outros relatórios de **Despesas** (por fornecedor, elemento, órgão, função, etc.),
  **Contratos** e **Licitações** existem no mesmo portal, não explorados.

**Detalhes técnicos da plataforma** (relevantes se formos mexer em outra seção do mesmo portal):
é DevExpress ASPxGridView sobre ASP.NET WebForms, com o conteúdo de cada seção carregado num
iframe (`frmPaginaAspx`). Filtros de data/ano/mês são controles DevExpress que não respondem a
digitação normal - é preciso usar a API cliente
(`window.<idDoControle>.SetValue(...)` + `.RaiseValueChangedEvent()`), e o valor esperado no
combo de mês é o número com dois dígitos como string (`"07"`), não o nome (`"Julho"`) nem o
número sem zero à esquerda. O botão de exportar CSV (`#btnExportarCSV`) é mais confiável que
raspar a tabela renderizada (evita lidar com paginação). Reaproveitar a página do navegador entre
buscas sucessivas se mostrou instável - navegar do zero a cada consulta funcionou de forma
confiável, só mais lento (~3s por mês).

## Descartado

### Faltas/frequência dos vereadores em sessões
Investigado em 2026-07-30. **Não há dado estruturado disponível publicamente**: as páginas de
sessões (`/Siscam/Reunioes`) só mostram data/hora/observações, sem lista de presença; o "Relatório
Anual de Atividades" (PDF de 477 páginas, baixado e com texto extraído por completo) não contém
nenhuma menção a falta/ausência/presença/frequência. Não achamos vestígio dessa informação em
nenhuma página do site oficial. Conclusão: abandonado por falta de fonte, não por falta de
esforço - só reabrir se descobrirmos uma fonte nova (ex.: pedido via e-SIC).

## Antes de implementar qualquer item acima
Alinhar com o usuário: taxonomia de temas (lista de categorias e palavras-chave) e formato de
apresentação do "menos atuante".
