#!/usr/bin/env python3
"""Cria o arquivo SQLite e as tabelas do projeto (idempotente)."""

from src.database import db_manager


def main():
    print(f"Criando/verificando banco SQLite em: {db_manager.db_path}")
    db_manager.create_tables()
    print("Tabelas criadas/verificadas com sucesso.")


if __name__ == "__main__":
    main()
