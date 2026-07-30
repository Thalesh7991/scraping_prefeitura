import logging
import re
from typing import List, Optional
from urllib.parse import urljoin

from .config import config
from .database import ComissaoInfo, LegislaturaInfo, VereadorInfo, db_manager
from .utils import clean_text, extract_id_from_href, fetch_soup, parse_periodo_br

logger = logging.getLogger(__name__)

_NOME_APELIDO_RE = re.compile(r"^(.*?)\s*\(([^)]+)\)\s*$")
_EMAIL_RE = re.compile(r"[\w.\-]+@camarabotucatu\.sp\.gov\.br", re.IGNORECASE)
_LICENCIADO_PREFIXO_RE = re.compile(r"^\(Licenciado\)\s*-\s*", re.IGNORECASE)


def _split_nome_apelido(texto: str):
    texto_limpo = _LICENCIADO_PREFIXO_RE.sub("", clean_text(texto)).strip()
    match = _NOME_APELIDO_RE.match(texto_limpo)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return texto_limpo, None


def list_vereadores_basico() -> List[dict]:
    """Lê /Vereadores e retorna a lista básica (site_id, nome, partido, foto, licenciado, link)."""
    soup = fetch_soup(config.scraping.vereadores_url)
    if not soup:
        raise RuntimeError("Não foi possível acessar a página de vereadores")

    resultados = []
    for card in soup.find_all("div", class_="card"):
        foto_img = card.find("img", class_="vereador-foto")
        if not foto_img:
            continue  # não é um card de vereador (ex: cards de notícias/links)

        h6 = card.find("h6")
        link = card.find("a", href=re.compile(r"Vereadores/Details\?id=\d+"))
        if not h6 or not link:
            continue

        nome_raw = clean_text(h6.get_text())
        licenciado = nome_raw.upper().startswith("(LICENCIADO)")
        nome = re.sub(r"^\(Licenciado\)\s*-\s*", "", nome_raw, flags=re.IGNORECASE).strip()

        partido_tag = card.find("p", class_="text-muted")
        partido = clean_text(partido_tag.get_text()) if partido_tag else None

        site_id = extract_id_from_href(link.get("href"))
        foto_url = urljoin(config.scraping.base_url, foto_img.get("src", ""))

        if site_id is None:
            logger.warning(f"Vereador sem site_id identificável: {nome_raw}")
            continue

        resultados.append({
            "site_id": site_id,
            "nome": nome,
            "partido": partido,
            "foto_url": foto_url,
            "licenciado": licenciado,
        })

    logger.info(f"Encontrados {len(resultados)} vereadores na listagem atual")
    return resultados


def _parse_timeline_secao(soup, titulo_contem: str):
    """Retorna os blocos <div class="timeline-item"> da seção cujo <h3> contém `titulo_contem`."""
    for bloco in soup.find_all("div", class_="mt-5"):
        h3 = bloco.find("h3", class_="secao-titulo")
        if h3 and titulo_contem.lower() in clean_text(h3.get_text()).lower():
            return bloco.find_all("div", class_="timeline-item")
    return []


def fetch_perfil_vereador(site_id: int) -> Optional[VereadorInfo]:
    """Lê /Vereadores/Details?id=X e monta o perfil completo do vereador."""
    soup = fetch_soup(config.scraping.vereador_details_url, params={"id": site_id})
    if not soup:
        logger.error(f"Não foi possível acessar o perfil do vereador site_id={site_id}")
        return None

    titulo = soup.find("h1", class_="titulo-vereador")
    if not titulo:
        logger.error(f"Página de perfil sem título esperado: site_id={site_id}")
        return None

    nome, apelido = _split_nome_apelido(titulo.get_text())
    licenciado = "(licenciado)" in clean_text(titulo.get_text()).lower()

    texto_pagina = soup.get_text()
    email_match = _EMAIL_RE.search(texto_pagina)
    email = email_match.group(0) if email_match else None

    partido = None
    for li in soup.find_all("li"):
        strong = li.find("strong")
        if strong and "partido" in clean_text(strong.get_text()).lower():
            partido = clean_text(li.get_text()).split(":", 1)[-1].strip()
            break

    bio = None
    for h5 in soup.find_all("h5", class_="card-title"):
        if "biografia" in clean_text(h5.get_text()).lower():
            card_body = h5.find_parent("div", class_="card-body")
            if card_body:
                h5.extract()
                bio = clean_text(card_body.get_text())
            break

    foto_url = None
    foto_img = soup.find("img", src=re.compile(r"handler=Imagem\b"))
    if foto_img:
        foto_url = urljoin(config.scraping.base_url, foto_img.get("src", ""))

    return VereadorInfo(
        site_id=site_id,
        nome=nome,
        apelido=apelido,
        partido=partido,
        email=email,
        foto_url=foto_url,
        licenciado=licenciado,
        bio=bio,
    ), soup


def extrair_legislaturas(soup) -> List[LegislaturaInfo]:
    resultado = []
    for item in _parse_timeline_secao(soup, "Legislaturas"):
        h5 = item.find("h5")
        periodo_tag = item.find("p", class_="text-muted")
        if not h5:
            continue
        inicio, fim = parse_periodo_br(periodo_tag.get_text() if periodo_tag else None)
        resultado.append(LegislaturaInfo(
            legislatura=clean_text(h5.get_text()),
            data_inicio=inicio,
            data_fim=fim,
        ))
    return resultado


def extrair_comissoes(soup) -> List[ComissaoInfo]:
    resultado = []
    for item in _parse_timeline_secao(soup, "Comiss"):
        h5 = item.find("h5")
        if not h5:
            continue
        cargo = None
        cargo_tag = item.find("p", class_="mb-1")
        if cargo_tag and cargo_tag.find("strong"):
            cargo = clean_text(cargo_tag.get_text()).split(":", 1)[-1].strip()
        periodo_tag = item.find("p", class_="text-muted")
        inicio, fim = parse_periodo_br(periodo_tag.get_text() if periodo_tag else None)
        resultado.append(ComissaoInfo(
            nome=clean_text(h5.get_text()),
            cargo=cargo,
            data_inicio=inicio,
            data_fim=fim,
        ))
    return resultado


def scrape_vereadores() -> int:
    """Coleta a listagem atual + perfil completo de cada vereador e persiste no banco.
    Retorna a quantidade de vereadores processados."""
    basicos = list_vereadores_basico()

    processados = 0
    for item in basicos:
        resultado = fetch_perfil_vereador(item["site_id"])
        if not resultado:
            continue
        perfil, soup = resultado

        # A listagem tem partido/foto/licenciado já prontos; o perfil pode preencher lacunas
        perfil.partido = perfil.partido or item["partido"]
        perfil.foto_url = perfil.foto_url or item["foto_url"]
        perfil.licenciado = perfil.licenciado or item["licenciado"]

        vereador_id = db_manager.upsert_vereador(perfil)
        db_manager.replace_legislaturas(vereador_id, extrair_legislaturas(soup))
        db_manager.replace_comissoes(vereador_id, extrair_comissoes(soup))

        processados += 1
        logger.info(f"Perfil processado: {perfil.nome} (site_id={perfil.site_id})")

    logger.info(f"Total de vereadores processados: {processados}/{len(basicos)}")
    return processados
