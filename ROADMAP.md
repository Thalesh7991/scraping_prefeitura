# Roadmap — FiscalizAI Botucatu

Backlog de ideias discutidas e ainda não implementadas, para não perder o contexto entre sessões.

## Feito

### Remuneração dos vereadores (salário) — `src/scraper_transparencia.py`
Implementado em 2026-07-30. Usa Playwright contra o portal de transparência de terceiros
(Fiorilli) - ver detalhes técnicos da investigação no item "Gastos da Câmara" abaixo. Resultado:
seção **Servidores → Servidores Ativos** do portal tem nome, cargo e valor líquido/mês, batendo
100% com os nomes da nossa tabela `vereadores` (76 registros coletados para 2026, zero sem
correspondência). Sabe distinguir titular licenciado de suplente que assumiu o cargo (o suplente
aparece com cargo "VEREADOR SUPLENTE" recebendo o salário, o titular licenciado não aparece).

**Limitação conhecida - investigada a fundo em 2026-07-30, é um bug real do portal**: trocar
"Escolha o Exercício" (ano) e em seguida pesquisar por mês nunca completa (fica "Processando..."
ou, quando o indicador some, a busca volta pro formulário em branco, sem dado nenhum). Tentei
7 abordagens diferentes pra contornar isso antes de concluir que é bug do lado do portal, não
algo resolvível do nosso lado:
1. Esperar mais tempo (até 54s) - nunca completa.
2. Ignorar o indicador visual de "Processando" (hipótese: só o indicador travava, o dado por trás
   já tinha mudado) - confirmado que o valor do combo de *ano* realmente muda rápido, mas o passo
   seguinte (pesquisar por mês) não - o dado real não aparece, não é só o indicador.
3. Forçar o clique no botão de exportar mesmo "escondido" (`force=True`) - falha: o elemento
   realmente não está renderizado (não é só CSS escondendo), Playwright recusa o clique.
4. Reautenticar com navegação do zero a cada mês (mesma técnica que resolveu o problema pro ano
   corrente) - não resolve quando combinado com troca de ano.
5. Esperar bem mais (até 54s) checando a contagem real de linhas da tabela (não só o botão) -
   fica em 0 linhas indefinidamente.
6. Inspecionar o texto final da página - o formulário volta pro estado inicial (mês em branco),
   sugerindo que o servidor erra e a página se reseta, em vez de só estar lenta.
7. Contexto de navegador totalmente novo (sem cookie/sessão compartilhada) pra essa tentativa -
   mesmo resultado.

**Conclusão**: só coletamos o ano corrente de forma confiável. Anos anteriores (2025, ou
histórico 2021-2024) ficam bloqueados até acharmos um caminho totalmente diferente (ex.: um
parâmetro de URL que pule a interação da UI, se existir - não encontrado ainda) ou até o próprio
portal corrigir esse bug. Não vale reabrir essa investigação sem uma ideia nova e concreta.

Diárias e Passagens e Verbas Indenizatórias foram descartadas nessa investigação (ver abaixo) -
não fazem parte do que foi implementado.

`src/export_json.py` já gera `site/data/remuneracao.json` com esses dados, e o site já exibe:
tile agregado + tabela mensal por vereador em `vereador.html`.

### Estimativa de gasto desde o início do mandato
Implementado em 2026-07-30, em `src/export_json.py` (`_estimativas_por_vereador`). Resolve a
pergunta "dá pra multiplicar salário × meses de mandato?" com precisão, usando dado que já
coletamos (sem scraping novo): o campo `data_admissao` do portal de transparência já grava,
por pessoa, quando ela passou a receber - `2025-01-01` pros titulares em exercício desde o
início, `2025-01-08` pros dois suplentes que assumiram no lugar de titulares licenciados. Isso
resolve exatamente a dúvida original ("como saber quando foi a licença e por quanto tempo o
suplente está substituindo") sem precisar de uma fonte nova: o titular licenciado simplesmente
nunca aparece na folha (contribui R$0, corretamente), e o suplente já entra com a data certa.

Cálculo: `meses = meses entre max(data_admissao, início da legislatura atual) e a última
competência coletada`, multiplicado pelo valor bruto mais recente conhecido da pessoa. Validado
em 2026-07-30: 11 pessoas com 19 meses (01/2025 a 07/2026), total R$ 1.245.246,70, batendo com a
soma manual. Sempre rotulado como "estimativa" (não "gasto confirmado"), com aviso explícito de
que reajustes salariais no meio do caminho não são considerados - não temos como saber disso
sem o histórico 2025, que está bloqueado (ver limitação acima). Exibido em `index.html` (tile +
legenda) e por vereador em `vereador.html` (linha "Estimativa desde o início do mandato..." logo
acima da tabela mensal). De brinde, o perfil do vereador agora mostra um selo "Licenciado"
quando aplicável (`vereador.licenciado`, já coletado há tempo mas nunca exibido antes) - sem
isso, sumir a seção de Remuneração pra um licenciado ficava sem explicação visível.

### Classificação por assunto real (honesta sobre o que é cerimonial) + resumo crítico gerado por IA
Implementado em 2026-07-30, em resposta à pergunta "os vereadores não estão fazendo coisas
inúteis?". Tipo formal e família não respondem isso (um "Projeto de Lei" pode ser só pra dar nome
a uma rua) - era necessário classificar pelo **conteúdo real da ementa**.

**Taxonomia final - uma lista só, não dois eixos separados** (`CATEGORIA_PATTERNS` em
`src/config.py`, aplicada em `categoria_de_ementa()` em `src/export_json.py`). Decisão importante,
motivada por feedback direto do usuário: uma versão inicial tinha "Natureza" (simbólico/
substantivo) e "Tema" (assunto) como dois eixos independentes, com as categorias cerimoniais
escondidas atrás de uma flag `Natureza=Simbólico`. Isso foi rejeitado: **as categorias cerimoniais
precisam ser nomeadas explicitamente na mesma lista de assuntos**, senão uma "Denominação de rua"
pode acabar parecendo "Trânsito" só por mencionar uma via. A ordem dos padrões importa muito por
isso: os 4 padrões cerimoniais são testados **antes** de qualquer categoria de política pública.

Lista final (14 categorias, as 4 primeiras são cerimoniais/simbólicas):
Denominação de Ruas/Prédios e Títulos Honoríficos, Datas/Semanas/Campanhas Comemorativas,
Utilidade Pública, Homenagens e Manifestações de Apreço/Pesar, Saúde, Educação, Assistência
Social, Segurança Pública, Meio Ambiente, Trânsito e Segurança Viária, Transporte Coletivo e
Rodovias, Infraestrutura e Obras Urbanas, Cultura/Esporte/Lazer, Administração e Institucional
(+ residual "Outros/Não identificado").

Duas fontes de sinal, nessa ordem: (1) padrão de conteúdo/regex na ementa; (2) se nada bateu,
o **destinatário estruturado** do pedido - muitos Requerimentos/Indicações começam com "Secretário
de X - solicita-se..." e esse "X" já denuncia o assunto (`DESTINATARIO_CATEGORIA`), sem precisar
adivinhar por palavra-chave.

**Validado contra as 7.234 ementas coletadas (todas as legislaturas)**: Infraestrutura e Obras
Urbanas 14,6%, Outros/Não identificado 13,0%, Homenagens e Manifestações 12,9%, Saúde 11,6%,
Educação 9,3%, Trânsito e Segurança Viária 8,9%, Segurança Pública 7,1%, Meio Ambiente 5,3%,
Administração e Institucional 4,3%, Cultura/Esporte/Lazer 3,8%, Denominação de Ruas/Prédios 3,4%,
Transporte Coletivo e Rodovias 2,7%, Assistência Social 2,2%, Datas Comemorativas 0,4%, Utilidade
Pública 0,4%. **Total cerimonial/simbólico: 17,0%** de tudo que a Câmara já produziu desde 2021.
Conferido manualmente que "Denomina a Rua X" nunca cai em Trânsito/Infraestrutura (213/267 casos
com a palavra "denomina" caem certinho na categoria própria - o resto são menções incidentais,
tipo "revoga lei que dispõe sobre denominação").

Exibido em `index.html` (tile "Cerimonial/simbólico" + gráfico "Sobre o que é, de fato", Câmara
inteira) e em `vereador.html` (gráfico "Por assunto" por vereador). Cor por categoria calculada em
`corCategoria()` (`site/assets/data.js`), lendo `meta.categorias_cerimoniais` do JSON (nunca
hardcoded em JS): dourado = cerimonial, azul = com efeito prático, cinza = não identificado.

**Resumo crítico da atuação, gerado por IA** (`src/gerar_resumos.py`, usa Gemini - chave do
usuário, reaproveitada de outro projeto dele, em `.env` local/gitignored como `GEMINI_API_KEY` +
`GEMINI_MODEL=gemini-2.5-flash`). Confirma a decisão de arquitetura registrada antes de programar:
**script totalmente offline, não roda no GitHub Actions**. Lê os números já calculados
deterministicamente (categoria, tipo formal, situação dos Projetos de Lei, remuneração, contexto
de mandato/licença) direto do SQLite, monta um prompt só com esses números (nunca a ementa crua),
chama o Gemini uma vez por vereador, e grava em `src/resumos_atuacao.json` (**committed no git**,
diferente de `site/data/*.json` que é gitignored/regenerado a cada deploy). Cache por hash dos
números de entrada - rodar de novo só chama a API pra quem mudou. `export_json.py` só **lê** esse
arquivo e junta `resumo_atuacao` ao vereador exportado; nunca chama o Gemini no dia a dia.

Rodado pra todos os 13 vereadores em 2026-07-30 e revisado manualmente (por mim): todos os textos
citam só os números fornecidos, nomeiam sem suavizar quando a maioria é cerimonial (entre 28% e
48% "Homenagens e Manifestações" na maioria dos vereadores - achado forte), tratam os 2 licenciados
com contexto justo (0 proposituras porque estão afastados, não porque "não trabalham"), e nenhum
usa julgamento de caráter. Exibido em `vereador.html` como card "Resumo da atuação" (sem legenda
explicativa - removida a pedido do usuário, decisão dele sobre o quanto expor do método aqui,
diferente da remuneração onde "estimativa" vs. "confirmado" continua rotulado). **Ainda vale o
usuário conferir os 13 textos pessoalmente** antes de considerar isso definitivo (revisão
automática por mim não substitui a leitura do dono do projeto).

**Refinamentos feitos ainda em 2026-07-30, depois da primeira revisão**:
- **Bug de adjacência no regex de datas comemorativas**: "Institui **no município de Botucatu** o
  Dia da Conscientização sobre o Daltonismo" não batia no padrão (exigia "institui" colado em
  "o dia"), então caía como "Outros/Não identificado" e quase virou destaque de "projeto de lei
  com efeito prático" no resumo do Carlos Trigo - exatamente o tipo de erro que essa categorização
  existe pra evitar. Corrigido ampliando a janela de caracteres entre "institui" e "dia/semana/mês"
  (`CATEGORIA_PATTERNS` em `src/config.py`); Câmara inteira passou de 17,0% pra 17,2% cerimonial
  (mudança pequena, o achado grande já estava certo).
- **Projetos de lei em destaque, não percentual**: a pedido do usuário, o resumo não fala mais em
  "X% dos Projetos de Lei são de Saúde" - em vez disso, `_montar_fatos_por_vereador` monta uma
  lista real (`projetos_de_lei_destaque`) com número/ano/ementa de cada PL **aprovado e não
  cerimonial** daquele vereador, e o Gemini escolhe até 2 pra descrever concretamente o que fazem
  (ex.: "obriga estabelecimentos a divulgar tratamento gratuito ao tabagismo pelo SUS"). Se a
  lista vier vazia (todos os PLs aprovados são só cerimoniais, ou não há PL aprovado), o resumo diz
  isso explicitamente em vez de forçar um destaque.
- **Fecho fixo com o custo total, calculado em Python (não pelo LLM)**: a pedido do usuário, todo
  resumo termina com "Até o momento, o vereador custou aos cofres públicos R$ X em remuneração
  (estimativa)." - usando a mesma `estimativa_total` já calculada pra remuneração. Importante: essa
  frase é **construída em `export_json.py` a cada exportação**, não gerada pelo Gemini nem
  cacheada junto com o resto do texto - assim o valor em R$ sempre reflete os dados de remuneração
  mais recentes (que atualizam todo dia), mesmo que o texto narrativo do Gemini não seja
  regenerado. Pra licenciados sem dado de remuneração, o fecho explica que não há histórico
  suficiente em vez de afirmar R$ 0,00 (que seria enganoso - não sabemos quanto custaram antes da
  licença, já que falta o histórico de 2025, bloqueado - ver limitação em "Feito" acima).

**Não implementado nessa rodada / possível refinamento futuro**: alguns padrões regex ainda podem
errar por causa de plural em outros pontos (ex.: "licitações" vs. padrão pensado pra "licitação" -
falha silenciosa, reduz um pouco a categoria "Administração e Institucional", não gera
classificação errada). Taxonomia de tema (Saúde/Educação/etc.) além do binário
cerimonial/substantivo não foi revisitada nessa rodada especificamente para refinar por LLM -
segue determinística, como decidido.

## Em aberto

### 1. "Mais atuante" e "menos atuante" lado a lado (ferramenta crítica, não só elogio)
Hoje o vereador com menos proposituras já aparece (implícito) no topo do gráfico de ranking, mas
sem destaque. Pedido explícito: tornar isso simétrico e visível — a ferramenta deve ajudar a
população a ver problemas, não só quem está indo bem.

**Cuidado a resolver antes de implementar**: comparar por quantidade bruta pode ser injusto com
quem está licenciado por parte do mandato, é novo no cargo (suplente que assumiu no meio do
período), ou propôs poucos projetos mas de mais peso/qualidade. Decisão pendente: mostrar o
número cru mesmo assim (é fato) mas com contexto visível ao lado (data de início no mandato,
status licenciado) — a validar o formato exato com o usuário antes de programar.

### 2. Gastos da Câmara — próximos passos (parte já feita, ver "Feito" acima)
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
Alinhar com o usuário: formato de apresentação do "menos atuante" (item 1 acima).
