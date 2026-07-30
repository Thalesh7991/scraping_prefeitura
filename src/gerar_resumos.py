#!/usr/bin/env python3
"""Gera o resumo crítico da atuação de cada vereador via Gemini.

Script OFFLINE - NÃO roda no pipeline diário do GitHub Actions (ver ROADMAP.md, item 1,
"Decisão de arquitetura pra não pesar o deploy diário"). Rode manualmente quando quiser
atualizar os resumos; os números de entrada não mudam todo dia, então não há necessidade de
automatizar isso. O resultado é salvo em src/resumos_atuacao.json (versionado no git) e lido
por export_json.py no dia a dia - o pipeline normal nunca chama o Gemini.

Cache por hash: só chama a API de novo para quem os números de entrada mudaram desde a
última vez que este script rodou.

Uso:
    python -m src.gerar_resumos              # gera/atualiza todos
    python -m src.gerar_resumos --forcar      # ignora o cache, regenera todo mundo

Requer GEMINI_API_KEY no .env local (nunca commitar - já está no .gitignore).
"""

import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from .config import config
from .export_json import _estimativas_por_vereador, categoria_de_ementa, status_de_situacao

load_dotenv()

RESUMOS_PATH = Path("src/resumos_atuacao.json")

INSTRUCOES = """Você resume, para um site independente de transparência cívica, a atuação \
legislativa de um vereador brasileiro na legislatura atual.

Regras obrigatórias:
- Use SOMENTE os dados fornecidos abaixo. Nunca invente números, nomes de projetos ou fatos \
que não estejam listados.
- Não julgue o caráter da pessoa (nunca use adjetivos como "preguiçoso", "bom", "ruim"). \
Descreva apenas o que os números mostram.
- Se a categoria mais frequente for cerimonial/simbólica (homenagens, denominação de rua ou \
prédio, data comemorativa, utilidade pública), diga isso claramente e sem suavizar - é uma \
informação relevante para o cidadão, mesmo que não seja lisonjeira.
- Se a pessoa estiver licenciada ou tiver assumido o mandato depois do início da legislatura, \
mencione isso como contexto (não é justo comparar o volume dela com quem está desde o início).
- Escreva em português, tom analítico e neutro, entre 3 e 5 frases corridas (sem tópicos, \
sem markdown, sem saudação).
"""


def _montar_fatos_por_vereador(conn, legislatura_atual_inicio):
    vereadores_rows = conn.execute(
        "SELECT * FROM vereadores WHERE perfil_completo = 1 ORDER BY nome"
    ).fetchall()
    proposituras_rows = conn.execute(
        "SELECT * FROM proposituras WHERE data >= ?", (legislatura_atual_inicio,)
    ).fetchall()
    autores_rows = conn.execute("SELECT * FROM propositura_autores").fetchall()
    remuneracao_rows = conn.execute(
        "SELECT * FROM remuneracao_vereadores WHERE vereador_id IS NOT NULL ORDER BY ano, mes"
    ).fetchall()

    proposituras_por_id = {p["id"]: p for p in proposituras_rows}
    props_por_vereador = {}
    for a in autores_rows:
        if a["propositura_id"] in proposituras_por_id:
            props_por_vereador.setdefault(a["vereador_id"], []).append(proposituras_por_id[a["propositura_id"]])

    estimativas, competencia = _estimativas_por_vereador(remuneracao_rows, legislatura_atual_inicio)
    max_meses = max((e["meses_estimados"] for e in estimativas.values()), default=0)

    fatos = {}
    for v in vereadores_rows:
        props = props_por_vereador.get(v["id"], [])
        contagem_categoria = {}
        contagem_tipo = {}
        for p in props:
            cat = categoria_de_ementa(p["ementa"])
            contagem_categoria[cat] = contagem_categoria.get(cat, 0) + 1
            contagem_tipo[p["tipo"]] = contagem_tipo.get(p["tipo"], 0) + 1

        normativos = [p for p in props if p["tipo"] == "Projeto de Lei"]
        status_normativos = {}
        for p in normativos:
            s = status_de_situacao(p["situacao"])
            status_normativos[s] = status_normativos.get(s, 0) + 1

        estim = estimativas.get(v["id"])
        contexto_mandato = "Em exercício desde o início da legislatura atual."
        if v["licenciado"]:
            contexto_mandato = "Atualmente licenciado(a) - substituído(a) por um(a) suplente."
        elif estim and max_meses and estim["meses_estimados"] < max_meses:
            contexto_mandato = (
                f"Assumiu o mandato depois do início da legislatura "
                f"({estim['meses_estimados']} de {max_meses} meses do mandato até agora)."
            )

        fatos[v["nome"]] = {
            "apelido": v["apelido"],
            "partido": v["partido"],
            "contexto_mandato": contexto_mandato,
            "total_proposituras": len(props),
            "por_categoria": sorted(contagem_categoria.items(), key=lambda kv: -kv[1]),
            "por_tipo": sorted(contagem_tipo.items(), key=lambda kv: -kv[1]),
            "projetos_de_lei_status": sorted(status_normativos.items(), key=lambda kv: -kv[1]),
            "remuneracao_mensal_atual": estim["ultimo_proventos"] if estim else None,
        }
    return fatos


def _formatar_prompt(nome, fatos):
    linhas = [f"Vereador(a): {fatos['apelido'] or nome} (nome completo: {nome})"]
    linhas.append(f"Partido: {fatos['partido'] or 'não informado'}")
    linhas.append(f"Situação no mandato: {fatos['contexto_mandato']}")
    linhas.append(f"Total de proposituras na legislatura atual: {fatos['total_proposituras']}")
    if fatos["total_proposituras"]:
        linhas.append("Por categoria (assunto real do texto, do mais para o menos frequente):")
        for cat, n in fatos["por_categoria"]:
            pct = n / fatos["total_proposituras"] * 100
            linhas.append(f"  - {cat}: {n} ({pct:.0f}%)")
        linhas.append("Por tipo formal: " + ", ".join(f"{t} ({n})" for t, n in fatos["por_tipo"]))
    if fatos["projetos_de_lei_status"]:
        linhas.append(
            "Situação dos Projetos de Lei apresentados: "
            + ", ".join(f"{s} ({n})" for s, n in fatos["projetos_de_lei_status"])
        )
    if fatos["remuneracao_mensal_atual"]:
        linhas.append(f"Remuneração bruta mensal atual: R$ {fatos['remuneracao_mensal_atual']:.2f}")
    return INSTRUCOES + "\n\nDados:\n" + "\n".join(linhas)


def _hash_fatos(fatos):
    bruto = json.dumps(fatos, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()[:16]


def gerar(forcar=False):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY não encontrada no ambiente/.env. Abortando.", file=sys.stderr)
        sys.exit(1)
    modelo = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    from google import genai
    client = genai.Client(api_key=api_key)

    conn = sqlite3.connect(config.db_path)
    conn.row_factory = sqlite3.Row
    legislaturas_rows = conn.execute("SELECT * FROM legislaturas").fetchall()
    legislatura_atual_inicio = max(r["data_inicio"] for r in legislaturas_rows if r["data_inicio"])

    fatos_por_vereador = _montar_fatos_por_vereador(conn, legislatura_atual_inicio)
    conn.close()

    existentes = json.loads(RESUMOS_PATH.read_text(encoding="utf-8")) if RESUMOS_PATH.exists() else {}

    resultado = {}
    gerados, reaproveitados = 0, 0
    for nome, fatos in fatos_por_vereador.items():
        h = _hash_fatos(fatos)
        if not forcar and nome in existentes and existentes[nome].get("hash") == h:
            resultado[nome] = existentes[nome]
            reaproveitados += 1
            continue

        prompt = _formatar_prompt(nome, fatos)
        resposta = client.models.generate_content(model=modelo, contents=prompt)
        resultado[nome] = {
            "hash": h,
            "resumo": resposta.text.strip(),
            "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        gerados += 1
        print(f"Gerado: {nome}")

    RESUMOS_PATH.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nConcluído: {gerados} gerados, {reaproveitados} reaproveitados do cache -> {RESUMOS_PATH}")


if __name__ == "__main__":
    gerar(forcar="--forcar" in sys.argv)
