import logging
import re
import sys
import time
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .config import config

logger = logging.getLogger(__name__)

_last_request_time = 0.0


def setup_logging(level: int = logging.INFO):
    """Configura logging para arquivo + console."""
    log_dir = Path(config.logs_dir)
    log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"scraping_{timestamp}.log"

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.info(f"Logging configurado. Arquivo: {log_file}")


def _wait_for_rate_limit():
    global _last_request_time
    elapsed = time.time() - _last_request_time
    delay = config.scraping.request_delay
    if elapsed < delay:
        time.sleep(delay - elapsed)
    _last_request_time = time.time()


def fetch_soup(url: str, params: Optional[dict] = None) -> Optional[BeautifulSoup]:
    """GET com rate limiting simples + retry com backoff exponencial."""
    cfg = config.scraping

    for attempt in range(cfg.max_retries + 1):
        _wait_for_rate_limit()
        try:
            logger.debug(f"GET {url} params={params} (tentativa {attempt + 1})")
            response = requests.get(url, params=params, headers=cfg.headers, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as e:
            logger.warning(f"Erro ao acessar {url} (tentativa {attempt + 1}): {e}")
            if attempt < cfg.max_retries:
                wait_time = cfg.retry_delay * (2 ** attempt)
                time.sleep(wait_time)

    logger.error(f"Falha definitiva ao acessar {url} após {cfg.max_retries + 1} tentativas")
    return None


def fetch_json(url: str, params: Optional[dict] = None) -> Optional[dict]:
    """GET com rate limiting/retry, retornando JSON decodificado."""
    cfg = config.scraping

    for attempt in range(cfg.max_retries + 1):
        _wait_for_rate_limit()
        try:
            logger.debug(f"GET (json) {url} params={params} (tentativa {attempt + 1})")
            response = requests.get(url, params=params, headers=cfg.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning(f"Erro ao acessar {url} (tentativa {attempt + 1}): {e}")
            if attempt < cfg.max_retries:
                time.sleep(cfg.retry_delay * (2 ** attempt))

    logger.error(f"Falha definitiva ao acessar {url} após {cfg.max_retries + 1} tentativas")
    return None


def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    cleaned = " ".join(text.split())
    cleaned = cleaned.replace("\xa0", " ").replace("​", "")
    return cleaned.strip()


_DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def parse_date_br(text: Optional[str]) -> Optional[date]:
    """Extrai uma data dd/mm/aaaa de um texto (tolerante a texto ao redor)."""
    if not text:
        return None
    match = _DATE_RE.search(text)
    if not match:
        return None
    day, month, year = match.groups()
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def parse_periodo_br(text: Optional[str]):
    """Extrai (data_inicio, data_fim) de um texto tipo '01/01/2025 - 31/12/2028'.
    O separador pode ser hífen, en-dash ou em-dash. data_fim pode estar ausente
    (mandato em curso)."""
    if not text:
        return None, None
    dates = _DATE_RE.findall(text)
    inicio = date(int(dates[0][2]), int(dates[0][1]), int(dates[0][0])) if len(dates) >= 1 else None
    fim = date(int(dates[1][2]), int(dates[1][1]), int(dates[1][0])) if len(dates) >= 2 else None
    return inicio, fim


def extract_id_from_href(href: Optional[str]) -> Optional[int]:
    """Extrai o valor do parâmetro ?id=NNN de uma URL/href."""
    if not href:
        return None
    match = re.search(r"[?&]id=(\d+)", href)
    return int(match.group(1)) if match else None
