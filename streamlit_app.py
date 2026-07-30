"""Dashboard público da atuação dos vereadores de Botucatu.

Lê o SQLite gerado por `python -m src.main` (ver README) e apresenta a
produção legislativa por vereador, tipo de proposta e situação.
"""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.config import FAMILIA_POR_TIPO, config

# --------------------------------------------------------------------------- #
# Paleta (fixa, validada para acessibilidade - ver skill de dataviz do projeto)
# --------------------------------------------------------------------------- #

CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
STATUS_COLORS = {
    "Aprovado": "#0ca30c",
    "Rejeitado": "#d03b3b",
    "Em tramitação": "#fab219",
    "Arquivado/Retirado": "#ec835a",
    "Outra situação": "#898781",
}

# Nomes internos de agrupamento (usados na lógica/filtragem) vs. rótulos em
# linguagem simples mostrados ao usuário (a "família" é uma categoria que este
# projeto cria para análise - não existe esse nome no site oficial da Câmara).
FAMILIA_ORDEM = ["Normativos", "Fiscalização/Solicitações", "Manifestações políticas", "Outros"]
FAMILIA_LABEL = {
    "Normativos": "Propostas de lei e normas",
    "Fiscalização/Solicitações": "Pedidos e solicitações",
    "Manifestações políticas": "Homenagens e manifestações",
    "Outros": "Outros",
}
FAMILIA_CORES = dict(zip(FAMILIA_ORDEM, CATEGORICAL))
FAMILIA_CORES_LABEL = {FAMILIA_LABEL[k]: v for k, v in FAMILIA_CORES.items()}

PLOTLY_TEMPLATE = "plotly_white"

COLUNAS_PROPOSITURA_LABELS = {
    "data": "Data",
    "tipo": "Tipo",
    "numero": "Número",
    "ano": "Ano",
    "situacao": "Situação",
    "ementa": "Assunto",
    "pdf_url": "Documento",
}


def status_de_situacao(situacao: str) -> str:
    s = (situacao or "").upper()
    if any(k in s for k in ["APROVADO", "DEFERIDO", "CONVERTIDO", "TRANSFORMADO"]):
        return "Aprovado"
    if any(k in s for k in ["REJEITADO", "INDEFERIDO", "PREJUDICADO"]):
        return "Rejeitado"
    if any(k in s for k in ["TRAMITANDO", "ENCAMINHA", "APRESENTADO"]):
        return "Em tramitação"
    if any(k in s for k in ["ARQUIVADO", "RETIRADO", "ADIADO", "REVOGADA"]):
        return "Arquivado/Retirado"
    return "Outra situação"


def tabela_proposituras(df: pd.DataFrame, colunas=None):
    """Renderiza uma tabela de proposituras com colunas em português, data formatada
    e o link do documento como botão clicável (em vez de colunas cruas do banco)."""
    colunas = colunas or ["data", "tipo", "numero", "ano", "situacao", "ementa", "pdf_url"]
    exibir = df[colunas].sort_values("data", ascending=False).copy()
    if "data" in exibir.columns:
        exibir["data"] = pd.to_datetime(exibir["data"]).dt.strftime("%d/%m/%Y")
    exibir = exibir.rename(columns=COLUNAS_PROPOSITURA_LABELS)

    column_config = {}
    if "Documento" in exibir.columns:
        column_config["Documento"] = st.column_config.LinkColumn("Documento", display_text="Ver documento")

    st.dataframe(exibir, use_container_width=True, hide_index=True, column_config=column_config)


# --------------------------------------------------------------------------- #
# Dados
# --------------------------------------------------------------------------- #

@st.cache_data(ttl=3600)
def carregar_dados():
    """Carrega o banco e recorta para a legislatura atual.

    O banco guarda o histórico completo (legislatura atual + anterior) para permitir
    análises futuras, mas o dashboard é público e voltado a acompanhar os vereadores
    EM EXERCÍCIO - por isso só expõe dados a partir do início do mandato vigente e
    apenas vereadores com perfil completo (ou seja, que estão na listagem atual do site).
    """
    if not Path(config.db_path).exists():
        return None

    conn = sqlite3.connect(config.db_path)
    proposituras = pd.read_sql_query("SELECT * FROM proposituras", conn)
    vereadores = pd.read_sql_query("SELECT * FROM vereadores", conn)
    autores = pd.read_sql_query(
        """
        SELECT pa.propositura_id, v.id as vereador_id, v.nome as vereador_nome,
               v.apelido, v.partido
        FROM propositura_autores pa
        JOIN vereadores v ON v.id = pa.vereador_id
        """,
        conn,
    )
    legislaturas = pd.read_sql_query("SELECT * FROM legislaturas", conn)
    comissoes = pd.read_sql_query("SELECT * FROM comissoes", conn)
    ultima_atualizacao = conn.execute("SELECT MAX(updated_at) FROM proposituras").fetchone()[0]
    conn.close()

    legislaturas["data_inicio"] = pd.to_datetime(legislaturas["data_inicio"])
    legislaturas["data_fim"] = pd.to_datetime(legislaturas["data_fim"])
    legislatura_atual_inicio = legislaturas["data_inicio"].max()

    vereadores = vereadores[vereadores["perfil_completo"] == 1].copy()
    autores = autores[autores["vereador_id"].isin(vereadores["id"])].copy()
    legislaturas = legislaturas[legislaturas["vereador_id"].isin(vereadores["id"])]
    comissoes = comissoes[comissoes["vereador_id"].isin(vereadores["id"])]

    proposituras["data"] = pd.to_datetime(proposituras["data"])
    proposituras = proposituras[proposituras["data"] >= legislatura_atual_inicio].copy()
    proposituras["familia"] = proposituras["tipo"].map(FAMILIA_POR_TIPO).fillna("Outros")
    proposituras["familia_label"] = proposituras["familia"].map(FAMILIA_LABEL)
    proposituras["status"] = proposituras["situacao"].apply(status_de_situacao)

    return {
        "proposituras": proposituras,
        "vereadores": vereadores,
        "autores": autores,
        "legislaturas": legislaturas,
        "comissoes": comissoes,
        "legislatura_atual_inicio": legislatura_atual_inicio,
        "ultima_atualizacao": ultima_atualizacao,
    }


def proposituras_com_autores(dados) -> pd.DataFrame:
    """Uma linha por (propositura, autor) - usada para métricas por vereador (coautoria conta
    para todos os autores)."""
    return dados["autores"].merge(dados["proposituras"], left_on="propositura_id", right_on="id")


# --------------------------------------------------------------------------- #
# Páginas
# --------------------------------------------------------------------------- #

def pagina_visao_geral(dados):
    st.header("Visão geral")
    prop = dados["proposituras"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Propostas apresentadas", f"{len(prop):,}".replace(",", "."))
    normativos = prop[prop["familia"] == "Normativos"]
    aprovados = normativos[normativos["status"] == "Aprovado"]
    taxa = (len(aprovados) / len(normativos) * 100) if len(normativos) else 0
    col2.metric("Propostas de lei e normas", f"{len(normativos):,}".replace(",", "."))
    col3.metric("Taxa de aprovação (leis e normas)", f"{taxa:.0f}%")
    col4.metric("Vereadores em exercício", len(dados["vereadores"]))

    st.subheader("O que os vereadores têm proposto")
    st.caption(
        "Nem toda proposta é uma lei - veja abaixo os diferentes tipos de atuação "
        "e o que cada um significa."
    )
    por_familia = (
        prop.groupby("familia_label").size().reindex(FAMILIA_LABEL.values()).dropna().reset_index(name="total")
    )
    fig = px.bar(
        por_familia, x="total", y="familia_label", orientation="h",
        color="familia_label", color_discrete_map=FAMILIA_CORES_LABEL,
        template=PLOTLY_TEMPLATE, text="total",
    )
    fig.update_layout(showlegend=False, yaxis_title="", xaxis_title="Propostas")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("O que significa cada tipo?"):
        st.markdown(
            "- **Propostas de lei e normas**: Projetos de Lei e afins - podem virar lei/norma se aprovados.\n"
            "- **Pedidos e solicitações**: Indicações (sugestões ao Executivo) e Requerimentos "
            "(pedidos formais/fiscalização).\n"
            "- **Homenagens e manifestações**: Moções - aplausos, repúdio, pesar. Não têm efeito de lei.\n"
            "- **Outros**: prestação de contas e vetos."
        )

    st.subheader("Evolução ao longo do mandato")
    prop_ano = prop.dropna(subset=["data"]).copy()
    prop_ano["ano"] = prop_ano["data"].dt.year
    evolucao = prop_ano.groupby(["ano", "familia_label"]).size().reset_index(name="total")
    fig2 = px.line(
        evolucao, x="ano", y="total", color="familia_label",
        category_orders={"familia_label": list(FAMILIA_LABEL.values())},
        color_discrete_map=FAMILIA_CORES_LABEL, markers=True, template=PLOTLY_TEMPLATE,
    )
    fig2.update_layout(xaxis_title="Ano", yaxis_title="Propostas", legend_title="")
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Situação das propostas de lei e normas")
    st.caption(
        "Só faz sentido falar em 'aprovado/rejeitado' para propostas de lei e normas - "
        "homenagens e pedidos não passam pelo mesmo tipo de votação."
    )
    situ = normativos.groupby("status").size().reindex(STATUS_COLORS.keys()).dropna().reset_index(name="total")
    fig3 = px.bar(
        situ, x="status", y="total", color="status",
        color_discrete_map=STATUS_COLORS, template=PLOTLY_TEMPLATE, text="total",
    )
    fig3.update_layout(showlegend=False, xaxis_title="", yaxis_title="Propostas")
    st.plotly_chart(fig3, use_container_width=True)

    with st.expander("Ver tabela"):
        st.dataframe(
            por_familia.rename(columns={"familia_label": "Tipo de atuação", "total": "Total"}),
            use_container_width=True, hide_index=True,
        )


def pagina_perfil_vereador(dados):
    st.header("Perfil do vereador")
    prop_autores = proposituras_com_autores(dados)
    vereadores = dados["vereadores"].sort_values("nome")

    nomes = vereadores["nome"].tolist()
    nome_escolhido = st.selectbox("Selecione um vereador", nomes)
    vereador = vereadores[vereadores["nome"] == nome_escolhido].iloc[0]

    col_foto, col_info = st.columns([1, 3])
    with col_foto:
        if vereador["foto_url"]:
            st.image(vereador["foto_url"], width=160)
    with col_info:
        st.subheader(f"{vereador['nome']}" + (f" ({vereador['apelido']})" if vereador["apelido"] else ""))
        st.write(f"**Partido:** {vereador['partido'] or 'não informado'}")
        if vereador["bio"]:
            with st.expander("Biografia"):
                st.write(vereador["bio"])

    legislaturas = dados["legislaturas"][dados["legislaturas"]["vereador_id"] == vereador["id"]]
    comissoes = dados["comissoes"][dados["comissoes"]["vereador_id"] == vereador["id"]]
    if not legislaturas.empty:
        periodos = ", ".join(
            f"{r.data_inicio:%d/%m/%Y} a {r.data_fim:%d/%m/%Y}" for r in legislaturas.itertuples()
        )
        st.write(f"**Mandato atual:** {periodos}")
    if not comissoes.empty:
        with st.expander(f"Comissões ({len(comissoes)})"):
            comissoes_exibir = comissoes[["nome", "cargo", "data_inicio", "data_fim"]].copy()
            comissoes_exibir["data_inicio"] = pd.to_datetime(comissoes_exibir["data_inicio"]).dt.strftime("%d/%m/%Y")
            comissoes_exibir["data_fim"] = pd.to_datetime(comissoes_exibir["data_fim"]).dt.strftime("%d/%m/%Y")
            comissoes_exibir = comissoes_exibir.rename(columns={
                "nome": "Comissão", "cargo": "Cargo", "data_inicio": "Início", "data_fim": "Fim",
            })
            st.dataframe(comissoes_exibir, use_container_width=True, hide_index=True)

    minhas = prop_autores[prop_autores["vereador_id"] == vereador["id"]]
    st.subheader(f"Propostas apresentadas ({len(minhas)})")

    if minhas.empty:
        st.warning("Nenhuma proposta encontrada para este vereador na legislatura atual.")
        return

    por_tipo = minhas.groupby(["familia_label", "tipo"]).size().reset_index(name="total").sort_values("total", ascending=True)
    fig = px.bar(
        por_tipo, x="total", y="tipo", color="familia_label", orientation="h",
        color_discrete_map=FAMILIA_CORES_LABEL, category_orders={"familia_label": list(FAMILIA_LABEL.values())},
        template=PLOTLY_TEMPLATE, text="total",
    )
    fig.update_layout(yaxis_title="", xaxis_title="Propostas", legend_title="")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Filtrar propostas deste vereador"):
        tipos_sel = st.multiselect(
            "Tipo", sorted(minhas["tipo"].unique()), key="perfil_tipo", placeholder="Todos os tipos",
        )
        situacoes_sel = st.multiselect(
            "Situação", sorted(minhas["situacao"].dropna().unique()), key="perfil_situacao",
            placeholder="Todas as situações",
        )
        filtradas = minhas.copy()
        if tipos_sel:
            filtradas = filtradas[filtradas["tipo"].isin(tipos_sel)]
        if situacoes_sel:
            filtradas = filtradas[filtradas["situacao"].isin(situacoes_sel)]
        tabela_proposituras(filtradas)


def pagina_ranking(dados):
    st.header("Comparar vereadores")
    st.caption(
        "Cada tipo de atuação é comparado separadamente, para não misturar coisas muito "
        "diferentes (uma homenagem não é o mesmo que uma proposta de lei)."
    )

    prop_autores = proposituras_com_autores(dados)
    familias_disponiveis = [f for f in FAMILIA_ORDEM if f in prop_autores["familia"].unique()]
    labels_disponiveis = [FAMILIA_LABEL[f] for f in familias_disponiveis]

    label_sel = st.radio("Tipo de atuação", labels_disponiveis, horizontal=True)
    familia_sel = {v: k for k, v in FAMILIA_LABEL.items()}[label_sel]
    subset = prop_autores[prop_autores["familia"] == familia_sel]

    ranking = subset.groupby("vereador_nome").size().sort_values(ascending=False).head(15).reset_index(name="total")

    if familia_sel == "Normativos":
        aprovados = subset[subset["status"] == "Aprovado"].groupby("vereador_nome").size()
        ranking["aprovados"] = ranking["vereador_nome"].map(aprovados).fillna(0).astype(int)
        ranking["taxa_aprovacao"] = (ranking["aprovados"] / ranking["total"] * 100).round(0)

        fig = px.bar(
            ranking.sort_values("total"), x="total", y="vereador_nome", orientation="h",
            color_discrete_sequence=[FAMILIA_CORES[familia_sel]], template=PLOTLY_TEMPLATE, text="total",
        )
        fig.update_layout(yaxis_title="", xaxis_title="Propostas")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Taxa de aprovação")
        st.caption("Considerando só vereadores com pelo menos 3 propostas de lei/normas apresentadas.")
        ranking_taxa = ranking[ranking["total"] >= 3].sort_values("taxa_aprovacao")
        fig2 = px.bar(
            ranking_taxa, x="taxa_aprovacao", y="vereador_nome", orientation="h",
            color_discrete_sequence=[STATUS_COLORS["Aprovado"]], template=PLOTLY_TEMPLATE, text="taxa_aprovacao",
        )
        fig2.update_layout(yaxis_title="", xaxis_title="% aprovadas")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        fig = px.bar(
            ranking.sort_values("total"), x="total", y="vereador_nome", orientation="h",
            color_discrete_sequence=[FAMILIA_CORES[familia_sel]], template=PLOTLY_TEMPLATE, text="total",
        )
        fig.update_layout(yaxis_title="", xaxis_title="Propostas")
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("Ver tabela"):
        colunas_tabela = {"vereador_nome": "Vereador", "total": "Total",
                           "aprovados": "Aprovadas", "taxa_aprovacao": "Taxa de aprovação (%)"}
        st.dataframe(
            ranking.rename(columns=colunas_tabela), use_container_width=True, hide_index=True,
        )


def pagina_explorar_tipo(dados):
    st.header("Explorar por tipo de proposta")
    prop = dados["proposituras"]

    tipo_sel = st.selectbox("Escolha um tipo", sorted(prop["tipo"].unique()))
    subset = prop[prop["tipo"] == tipo_sel]

    st.metric("Total na legislatura atual", len(subset))

    situ = subset.groupby("status").size().reindex(STATUS_COLORS.keys()).dropna().reset_index(name="total")
    fig = px.bar(
        situ, x="status", y="total", color="status",
        color_discrete_map=STATUS_COLORS, template=PLOTLY_TEMPLATE, text="total",
    )
    fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Propostas")
    st.plotly_chart(fig, use_container_width=True)

    tabela_proposituras(subset)


def pagina_busca(dados):
    st.header("Buscar propostas")
    prop_autores = proposituras_com_autores(dados)

    texto = st.text_input(
        "Buscar por assunto", placeholder="Ex.: iluminação, buraco na rua, saúde, transporte...",
    )
    col1, col2, col3 = st.columns(3)
    tipos_sel = col1.multiselect(
        "Tipo de proposta", sorted(dados["proposituras"]["tipo"].unique()), placeholder="Todos os tipos",
    )
    situacoes_sel = col2.multiselect(
        "Situação", sorted(dados["proposituras"]["situacao"].dropna().unique()), placeholder="Todas as situações",
    )
    vereadores_sel = col3.multiselect(
        "Vereador", sorted(dados["vereadores"]["nome"].unique()), placeholder="Todos os vereadores",
    )

    resultado = prop_autores.drop_duplicates(subset=["propositura_id"]).copy()
    if texto:
        resultado = resultado[resultado["ementa"].str.contains(texto, case=False, na=False)]
    if tipos_sel:
        resultado = resultado[resultado["tipo"].isin(tipos_sel)]
    if situacoes_sel:
        resultado = resultado[resultado["situacao"].isin(situacoes_sel)]
    if vereadores_sel:
        ids_prop = prop_autores[prop_autores["vereador_nome"].isin(vereadores_sel)]["propositura_id"]
        resultado = resultado[resultado["propositura_id"].isin(ids_prop)]

    st.write(f"{len(resultado)} resultado(s)")
    tabela_proposituras(resultado)


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #

def main():
    st.set_page_config(page_title="Câmara de Botucatu em Dados", page_icon="🏛️", layout="wide")
    st.title("🏛️ Câmara de Vereadores de Botucatu em Dados")

    dados = carregar_dados()
    if dados is None:
        st.error(
            f"Banco de dados não encontrado em `{config.db_path}`. "
            "Rode `python -m src.main --mode full` para coletar os dados primeiro."
        )
        return

    inicio = dados["legislatura_atual_inicio"].strftime("%m/%Y")
    atualizado = pd.to_datetime(dados["ultima_atualizacao"]).strftime("%d/%m/%Y às %H:%M") \
        if dados["ultima_atualizacao"] else "desconhecida"
    st.caption(
        f"Veja o que os vereadores de Botucatu em exercício têm proposto desde o início do "
        f"mandato atual ({inicio}). Dados coletados automaticamente do site oficial da Câmara "
        f"Municipal de Botucatu. Última atualização: {atualizado}."
    )

    pagina = st.sidebar.radio(
        "Navegação",
        ["Visão geral", "Perfil do vereador", "Comparar vereadores", "Por tipo de proposta", "Buscar"],
    )

    if pagina == "Visão geral":
        pagina_visao_geral(dados)
    elif pagina == "Perfil do vereador":
        pagina_perfil_vereador(dados)
    elif pagina == "Comparar vereadores":
        pagina_ranking(dados)
    elif pagina == "Por tipo de proposta":
        pagina_explorar_tipo(dados)
    elif pagina == "Buscar":
        pagina_busca(dados)


if __name__ == "__main__":
    main()
