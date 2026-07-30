#!/usr/bin/env python3
"""Exporta o recorte da legislatura atual para JSON estático, consumido pelo site em site/data/.

A categorização (família/status) é calculada aqui, em Python, para que o JavaScript do site
nunca precise reimplementar essas regras - ele só lê e exibe.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import FAMILIA_POR_TIPO, config

OUTPUT_DIR = Path("site/data")

FAMILIA_LABEL = {
    "Normativos": "Propostas de lei e normas",
    "Fiscalização/Solicitações": "Pedidos e solicitações",
    "Manifestações políticas": "Homenagens e manifestações",
    "Outros": "Outros",
}


def status_de_situacao(situacao):
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


def _escrever(nome, conteudo):
    (OUTPUT_DIR / nome).write_text(json.dumps(conteudo, ensure_ascii=False), encoding="utf-8")


def _meses_entre(inicio_iso, ano_fim, mes_fim):
    """Quantidade de meses entre `inicio_iso` (YYYY-MM-DD) e ano/mes, incluindo ambas as pontas."""
    ano_ini, mes_ini = int(inicio_iso[:4]), int(inicio_iso[5:7])
    return (ano_fim - ano_ini) * 12 + (mes_fim - mes_ini) + 1


def _estimativas_por_vereador(remuneracao_rows, legislatura_atual_inicio):
    """Estima o gasto acumulado desde o início do mandato (ou desde que a pessoa passou a
    receber, se for suplente que assumiu depois), a partir do valor bruto mais recente
    conhecido de cada vereador. Não considera possíveis reajustes salariais no meio do
    caminho - por isso é sempre rotulado como estimativa, nunca como gasto confirmado.
    Quem nunca aparece na folha (ex.: titular licenciado) fica de fora, corretamente.
    """
    if not remuneracao_rows:
        return {}, None

    ano_fim = max(r["ano"] for r in remuneracao_rows)
    mes_fim = max(r["mes"] for r in remuneracao_rows if r["ano"] == ano_fim)

    por_vereador = {}
    for r in remuneracao_rows:
        por_vereador.setdefault(r["vereador_id"], []).append(r)

    estimativas = {}
    for vid, linhas in por_vereador.items():
        linhas.sort(key=lambda r: (r["ano"], r["mes"]))
        ultima = linhas[-1]
        if not ultima["proventos"]:
            continue
        inicio = max(ultima["data_admissao"] or legislatura_atual_inicio, legislatura_atual_inicio)
        meses = _meses_entre(inicio, ano_fim, mes_fim)
        estimativas[vid] = {
            "meses_estimados": meses,
            "ultimo_proventos": ultima["proventos"],
            "ultima_competencia": f"{mes_fim:02d}/{ano_fim}",
            "estimativa_total": round(meses * ultima["proventos"], 2),
        }
    return estimativas, f"{mes_fim:02d}/{ano_fim}"


def exportar():
    conn = sqlite3.connect(config.db_path)
    conn.row_factory = sqlite3.Row

    legislaturas_rows = conn.execute("SELECT * FROM legislaturas").fetchall()
    datas_inicio = [r["data_inicio"] for r in legislaturas_rows if r["data_inicio"]]
    legislatura_atual_inicio = max(datas_inicio)  # ISO "YYYY-MM-DD", comparável como texto

    vereadores_rows = conn.execute(
        "SELECT * FROM vereadores WHERE perfil_completo = 1 ORDER BY nome"
    ).fetchall()
    vereador_ids = {r["id"] for r in vereadores_rows}

    comissoes_rows = conn.execute("SELECT * FROM comissoes").fetchall()
    proposituras_rows = conn.execute(
        "SELECT * FROM proposituras WHERE data >= ? ORDER BY data DESC", (legislatura_atual_inicio,)
    ).fetchall()
    autores_rows = conn.execute("SELECT * FROM propositura_autores").fetchall()
    remuneracao_rows = conn.execute(
        "SELECT * FROM remuneracao_vereadores WHERE vereador_id IS NOT NULL ORDER BY ano, mes"
    ).fetchall()
    conn.close()

    estimativas, competencia_estimativa = _estimativas_por_vereador(remuneracao_rows, legislatura_atual_inicio)

    autores_por_propositura = {}
    for row in autores_rows:
        if row["vereador_id"] in vereador_ids:
            autores_por_propositura.setdefault(row["propositura_id"], []).append(row["vereador_id"])

    vereadores_json = []
    for v in vereadores_rows:
        legs = [
            {"legislatura": r["legislatura"], "data_inicio": r["data_inicio"], "data_fim": r["data_fim"]}
            for r in legislaturas_rows if r["vereador_id"] == v["id"]
        ]
        coms = [
            {"nome": r["nome"], "cargo": r["cargo"], "data_inicio": r["data_inicio"], "data_fim": r["data_fim"]}
            for r in comissoes_rows if r["vereador_id"] == v["id"]
        ]
        vereadores_json.append({
            "id": v["id"], "nome": v["nome"], "apelido": v["apelido"], "partido": v["partido"],
            "email": v["email"], "foto_url": v["foto_url"], "licenciado": bool(v["licenciado"]),
            "bio": v["bio"], "legislaturas": legs, "comissoes": coms,
            "estimativa_remuneracao": estimativas.get(v["id"]),
        })

    proposituras_json = []
    for p in proposituras_rows:
        familia = FAMILIA_POR_TIPO.get(p["tipo"], "Outros")
        proposituras_json.append({
            "id": p["id"], "tipo": p["tipo"], "subtipo": p["subtipo"], "numero": p["numero"],
            "ano": p["ano"], "data": p["data"], "regime": p["regime"], "quorum": p["quorum"],
            "situacao": p["situacao"], "ementa": p["ementa"], "pdf_url": p["pdf_url"],
            "familia": familia, "familia_label": FAMILIA_LABEL.get(familia, familia),
            "status": status_de_situacao(p["situacao"]),
            "autores": autores_por_propositura.get(p["id"], []),
        })

    remuneracao_json = [
        {
            "vereador_id": r["vereador_id"], "ano": r["ano"], "mes": r["mes"], "cargo": r["cargo"],
            "proventos": r["proventos"], "liquido": r["liquido"],
        }
        for r in remuneracao_rows
    ]

    ano, mes, _ = legislatura_atual_inicio.split("-")
    meta = {
        "legislatura_atual_inicio": legislatura_atual_inicio,
        "legislatura_atual_inicio_display": f"{mes}/{ano}",
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_vereadores": len(vereadores_json),
        "total_proposituras": len(proposituras_json),
        "familias_ordem": list(FAMILIA_LABEL.keys()),
        "familia_label": FAMILIA_LABEL,
        "estimativa_gasto_mandato_total": round(sum(e["estimativa_total"] for e in estimativas.values()), 2) if estimativas else None,
        "estimativa_gasto_mandato_competencia": competencia_estimativa,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _escrever("vereadores.json", vereadores_json)
    _escrever("proposituras.json", proposituras_json)
    _escrever("remuneracao.json", remuneracao_json)
    _escrever("meta.json", meta)

    print(
        f"Exportado: {len(vereadores_json)} vereadores, {len(proposituras_json)} proposituras, "
        f"{len(remuneracao_json)} registros de remuneração -> {OUTPUT_DIR}"
    )


if __name__ == "__main__":
    exportar()
