import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import config

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS vereadores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER UNIQUE,        -- id de /Vereadores/Details?id=; NULL se conhecido só via Autoria
    nome TEXT NOT NULL UNIQUE,
    apelido TEXT,
    partido TEXT,
    email TEXT,
    foto_url TEXT,
    licenciado INTEGER NOT NULL DEFAULT 0,
    perfil_completo INTEGER NOT NULL DEFAULT 0,
    bio TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS legislaturas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vereador_id INTEGER NOT NULL REFERENCES vereadores(id),
    legislatura TEXT,
    data_inicio TEXT,
    data_fim TEXT,
    UNIQUE(vereador_id, legislatura, data_inicio)
);

CREATE TABLE IF NOT EXISTS comissoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vereador_id INTEGER NOT NULL REFERENCES vereadores(id),
    nome TEXT,
    cargo TEXT,
    data_inicio TEXT,
    data_fim TEXT,
    UNIQUE(vereador_id, nome, cargo, data_inicio)
);

CREATE TABLE IF NOT EXISTS proposituras (
    id INTEGER PRIMARY KEY,        -- id do Siscam (Documentos/Details?id=), estável -> upsert idempotente
    tipo TEXT NOT NULL,
    subtipo TEXT,
    numero INTEGER,
    ano INTEGER,
    data TEXT,
    regime TEXT,
    quorum TEXT,
    situacao TEXT,
    ementa TEXT,
    pdf_url TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS propositura_autores (
    propositura_id INTEGER NOT NULL REFERENCES proposituras(id),
    vereador_id INTEGER NOT NULL REFERENCES vereadores(id),
    PRIMARY KEY (propositura_id, vereador_id)
);

CREATE INDEX IF NOT EXISTS idx_proposituras_data ON proposituras(data);
CREATE INDEX IF NOT EXISTS idx_proposituras_tipo ON proposituras(tipo);
CREATE INDEX IF NOT EXISTS idx_proposituras_situacao ON proposituras(situacao);
CREATE INDEX IF NOT EXISTS idx_propositura_autores_vereador ON propositura_autores(vereador_id);
"""


@dataclass
class VereadorInfo:
    site_id: int
    nome: str
    apelido: Optional[str] = None
    partido: Optional[str] = None
    email: Optional[str] = None
    foto_url: Optional[str] = None
    licenciado: bool = False
    bio: Optional[str] = None


@dataclass
class LegislaturaInfo:
    legislatura: str
    data_inicio: Optional[date]
    data_fim: Optional[date]


@dataclass
class ComissaoInfo:
    nome: str
    cargo: Optional[str]
    data_inicio: Optional[date]
    data_fim: Optional[date]


@dataclass
class PropositutaInfo:
    id: int
    tipo: str
    subtipo: Optional[str]
    numero: Optional[int]
    ano: Optional[int]
    data: Optional[date]
    regime: Optional[str]
    quorum: Optional[str]
    situacao: Optional[str]
    ementa: Optional[str]
    pdf_url: Optional[str]
    # Pares (nome, apelido) extraídos do campo "Autoria" - uma propositura pode ter coautoria
    autores: List[tuple] = field(default_factory=list)


class DatabaseManager:
    """Gerenciador de acesso ao banco SQLite (arquivo único, sem servidor)."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.db_path

    @contextmanager
    def get_connection(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_tables(self):
        with self.get_connection() as conn:
            conn.executescript(SCHEMA_SQL)

    # ------------------------------------------------------------------ #
    # Vereadores
    # ------------------------------------------------------------------ #

    def upsert_vereador(self, info: VereadorInfo) -> int:
        """Insere/atualiza um vereador com perfil completo (vem de /Vereadores/Details).

        Verifica manualmente por site_id e, em seguida, por nome (em vez de confiar num único
        alvo de ON CONFLICT) porque um mesmo vereador pode já existir como registro mínimo
        (perfil_completo=0), criado antes a partir do texto de "Autoria" de uma propositura.
        """
        with self.get_connection() as conn:
            row = conn.execute("SELECT id FROM vereadores WHERE site_id = ?", (info.site_id,)).fetchone()
            if not row:
                row = conn.execute("SELECT id FROM vereadores WHERE nome = ?", (info.nome,)).fetchone()

            if row:
                conn.execute(
                    """
                    UPDATE vereadores SET
                        site_id = ?, nome = ?, apelido = ?, partido = ?, email = ?, foto_url = ?,
                        licenciado = ?, perfil_completo = 1, bio = ?, updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (info.site_id, info.nome, info.apelido, info.partido, info.email,
                     info.foto_url, int(info.licenciado), info.bio, row["id"]),
                )
                return row["id"]

            cur = conn.execute(
                """
                INSERT INTO vereadores (site_id, nome, apelido, partido, email, foto_url,
                                         licenciado, perfil_completo, bio)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (info.site_id, info.nome, info.apelido, info.partido, info.email,
                 info.foto_url, int(info.licenciado), info.bio),
            )
            return cur.lastrowid

    def get_or_create_vereador_by_nome(self, nome: str, apelido: Optional[str] = None) -> int:
        """Usado para autores encontrados apenas via 'Autoria' de proposituras (ex-vereadores
        de legislaturas anteriores que não têm mais perfil em /Vereadores)."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT id FROM vereadores WHERE nome = ?", (nome,)).fetchone()
            if row:
                return row["id"]
            cur = conn.execute(
                """
                INSERT INTO vereadores (site_id, nome, apelido, perfil_completo)
                VALUES (NULL, ?, ?, 0)
                """,
                (nome, apelido),
            )
            return cur.lastrowid

    def replace_legislaturas(self, vereador_id: int, legislaturas: List[LegislaturaInfo]):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM legislaturas WHERE vereador_id = ?", (vereador_id,))
            for leg in legislaturas:
                conn.execute(
                    """INSERT OR IGNORE INTO legislaturas (vereador_id, legislatura, data_inicio, data_fim)
                       VALUES (?, ?, ?, ?)""",
                    (vereador_id, leg.legislatura,
                     leg.data_inicio.isoformat() if leg.data_inicio else None,
                     leg.data_fim.isoformat() if leg.data_fim else None),
                )

    def replace_comissoes(self, vereador_id: int, comissoes: List[ComissaoInfo]):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM comissoes WHERE vereador_id = ?", (vereador_id,))
            for com in comissoes:
                conn.execute(
                    """INSERT OR IGNORE INTO comissoes (vereador_id, nome, cargo, data_inicio, data_fim)
                       VALUES (?, ?, ?, ?, ?)""",
                    (vereador_id, com.nome, com.cargo,
                     com.data_inicio.isoformat() if com.data_inicio else None,
                     com.data_fim.isoformat() if com.data_fim else None),
                )

    # ------------------------------------------------------------------ #
    # Proposituras
    # ------------------------------------------------------------------ #

    def upsert_propositura(self, info: PropositutaInfo) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO proposituras (id, tipo, subtipo, numero, ano, data, regime, quorum,
                                           situacao, ementa, pdf_url, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                    tipo = excluded.tipo,
                    subtipo = excluded.subtipo,
                    numero = excluded.numero,
                    ano = excluded.ano,
                    data = excluded.data,
                    regime = excluded.regime,
                    quorum = excluded.quorum,
                    situacao = excluded.situacao,
                    ementa = excluded.ementa,
                    pdf_url = excluded.pdf_url,
                    updated_at = datetime('now')
                """,
                (info.id, info.tipo, info.subtipo, info.numero, info.ano,
                 info.data.isoformat() if info.data else None,
                 info.regime, info.quorum, info.situacao, info.ementa, info.pdf_url),
            )
            # Autoria pode mudar de página para página em reprocessamentos raros; garantir consistência
            conn.execute("DELETE FROM propositura_autores WHERE propositura_id = ?", (info.id,))

    def link_autor(self, propositura_id: int, vereador_id: int):
        with self.get_connection() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO propositura_autores (propositura_id, vereador_id)
                   VALUES (?, ?)""",
                (propositura_id, vereador_id),
            )

    # ------------------------------------------------------------------ #
    # Estatísticas (usadas pelo CLI e como sanity-check)
    # ------------------------------------------------------------------ #

    def get_statistics(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            stats: Dict[str, Any] = {}
            stats["vereadores_count"] = conn.execute("SELECT COUNT(*) c FROM vereadores").fetchone()["c"]
            stats["vereadores_perfil_completo"] = conn.execute(
                "SELECT COUNT(*) c FROM vereadores WHERE perfil_completo = 1"
            ).fetchone()["c"]
            stats["proposituras_count"] = conn.execute("SELECT COUNT(*) c FROM proposituras").fetchone()["c"]

            stats["proposituras_por_tipo"] = [
                dict(row) for row in conn.execute(
                    """SELECT tipo, COUNT(*) as total FROM proposituras
                       GROUP BY tipo ORDER BY total DESC"""
                ).fetchall()
            ]
            stats["proposituras_por_situacao"] = [
                dict(row) for row in conn.execute(
                    """SELECT situacao, COUNT(*) as total FROM proposituras
                       GROUP BY situacao ORDER BY total DESC"""
                ).fetchall()
            ]
            stats["proposituras_por_vereador"] = [
                dict(row) for row in conn.execute(
                    """SELECT v.nome, COUNT(*) as total
                       FROM propositura_autores pa
                       JOIN vereadores v ON v.id = pa.vereador_id
                       GROUP BY v.nome ORDER BY total DESC"""
                ).fetchall()
            ]
            return stats


db_manager = DatabaseManager()
