import logging
import re
from typing import List, Optional
from urllib.parse import urljoin

from .config import config
from .database import PropositutaInfo, db_manager
from .utils import clean_text, extract_id_from_href, fetch_soup, parse_date_br

logger = logging.getLogger(__name__)

_TITULO_RE = re.compile(r"^(.*?)\s*N[ºo]\s*(\d+)\s*/\s*(\d{4})\s*$", re.IGNORECASE)
_NOME_APELIDO_RE = re.compile(r"^(.*?)\s*\(([^)]+)\)\s*$")
_TOTAL_REGISTROS_RE = re.compile(r"([\d.]+)\s*registros encontrados", re.IGNORECASE)


def _valor_apos_label(container, label: str) -> Optional[str]:
    """Busca um <p><strong>Label:</strong> valor</p> dentro do container e retorna 'valor'."""
    label_normalizado = label.rstrip(": ").strip().lower()
    for p in container.find_all("p"):
        strong = p.find("strong")
        if not strong:
            continue
        strong_text = clean_text(strong.get_text())
        if strong_text.rstrip(": ").strip().lower() != label_normalizado:
            continue
        full_text = clean_text(p.get_text())
        return full_text[len(strong_text):].strip(" :")
    return None


_AUTOR_COLETIVO_RE = re.compile(r"^Mesa\b", re.IGNORECASE)


def _split_autores(autoria_text: Optional[str]) -> List[tuple]:
    """Separa o campo 'Autoria' em pares (nome, apelido).

    Mesmo filtrando a busca por TipoAutorId=1 (Vereadores), uma propositura pode ter
    coautoria de um órgão coletivo (ex.: "Mesa Diretora 2025/2026", autoria tipo "Mesas").
    Esses não são vereadores individuais e são descartados para não poluir o cadastro.
    """
    if not autoria_text:
        return []
    autores = []
    for parte in autoria_text.split(","):
        parte = parte.strip()
        if not parte or _AUTOR_COLETIVO_RE.match(parte):
            continue
        match = _NOME_APELIDO_RE.match(parte)
        if match:
            autores.append((match.group(1).strip(), match.group(2).strip()))
        else:
            autores.append((parte, None))
    return autores


def parse_documento_item(item) -> Optional[PropositutaInfo]:
    """Converte um <div class="data-list-item"> da busca de Documentos num PropositutaInfo."""
    titulo_link = item.find("h4")
    titulo_link = titulo_link.find("a") if titulo_link else None
    if not titulo_link:
        return None

    doc_id = extract_id_from_href(titulo_link.get("href"))
    if doc_id is None:
        return None

    titulo_texto = clean_text(titulo_link.get_text())
    match = _TITULO_RE.match(titulo_texto)
    if match:
        tipo, numero, ano = match.group(1).strip(), int(match.group(2)), int(match.group(3))
    else:
        logger.warning(f"Não foi possível separar tipo/número/ano do título: '{titulo_texto}' (id={doc_id})")
        tipo, numero, ano = titulo_texto, None, None

    data_texto = _valor_apos_label(item, "Data:")
    data = parse_date_br(data_texto)

    pdf_link = item.find("a", href=re.compile(r"handler=Arquivo"))
    pdf_url = urljoin(config.scraping.base_url, pdf_link.get("href")) if pdf_link else None

    # O site usa "Autoria:" quando há coautoria e "Autor:" (singular) quando há um único autor
    autoria_texto = _valor_apos_label(item, "Autoria:") or _valor_apos_label(item, "Autor:")

    return PropositutaInfo(
        id=doc_id,
        tipo=tipo,
        subtipo=_valor_apos_label(item, "Subtipo:"),
        numero=numero,
        ano=ano,
        data=data,
        regime=_valor_apos_label(item, "Regime:"),
        quorum=_valor_apos_label(item, "Quórum:"),
        situacao=_valor_apos_label(item, "Situação:"),
        ementa=_valor_apos_label(item, "Ementa:"),
        pdf_url=pdf_url,
        autores=_split_autores(autoria_texto),
    )


def _log_total_registros(soup):
    texto = soup.get_text()
    match = _TOTAL_REGISTROS_RE.search(texto)
    if match:
        logger.info(f"Site reporta {match.group(1)} registros encontrados para os filtros aplicados")


def scrape_proposituras() -> dict:
    """Pagina /Siscam/Documentos (Proposituras, autoria de Vereadores), ordenado por data
    decrescente, parando assim que a data cruzar `config.scraping.data_inicio`."""
    cfg = config.scraping
    pagina = 1
    total_processadas = 0

    while True:
        soup = fetch_soup(cfg.documentos_url, params={
            "GrupoId": cfg.grupo_id_proposituras,
            "Pesquisa": "Avancada",
            "ShowSearch": "true",
            "TipoAutorId": cfg.tipo_autor_vereadores,
            "ItemsPerPage": cfg.items_per_page,
            "Ordenacao": cfg.ordenacao_data_decrescente,
            "CurrentPage": pagina,
        })
        if not soup:
            logger.error(f"Falha ao buscar página {pagina} de proposituras, interrompendo")
            break

        if pagina == 1:
            _log_total_registros(soup)

        itens = soup.find_all("div", class_="data-list-item")
        if not itens:
            logger.info(f"Página {pagina} sem resultados, fim da paginação")
            break

        cortou_por_data = False
        for item in itens:
            info = parse_documento_item(item)
            if info is None:
                logger.warning("Item de propositura não pôde ser parseado, ignorando")
                continue

            if info.data and info.data < cfg.data_inicio:
                cortou_por_data = True
                break  # ordenado por data decrescente: todo o restante é ainda mais antigo

            db_manager.upsert_propositura(info)
            for nome, apelido in info.autores:
                vereador_id = db_manager.get_or_create_vereador_by_nome(nome, apelido)
                db_manager.link_autor(info.id, vereador_id)
            total_processadas += 1

        logger.info(f"Página {pagina}: {len(itens)} itens processados, total acumulado {total_processadas}")

        if cortou_por_data:
            logger.info(f"Corte de data ({cfg.data_inicio.isoformat()}) atingido, parando paginação")
            break

        pagina += 1

    return {"total_proposituras": total_processadas, "paginas_lidas": pagina}
