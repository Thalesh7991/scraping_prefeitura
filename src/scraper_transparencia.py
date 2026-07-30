"""Scraper do portal de transparência de terceiros (Fiorilli) - remuneração dos vereadores.

Diferente do scraper da Siscam (GET puro), esse portal carrega os dados por JavaScript
(grid ASP.NET/DevExpress com callbacks e postbacks), então usa Playwright (navegador
headless) em vez de requests simples. Ver ROADMAP.md para o histórico da investigação
que validou esse caminho (Diárias e Verbas Indenizatórias foram descartadas; Servidores
Ativos tem o dado certo: nome, cargo e valor líquido por mês, batendo com nossos
vereadores).

Estratégia por mês/ano: define o exercício e o mês na UI, clica "Pesquisar" e usa o botão
de exportar CSV do próprio portal (mais robusto que raspar a tabela paginada renderizada).
"""

import csv
import io
import logging
from datetime import date

from playwright.sync_api import Frame, Page, sync_playwright

from .database import RemuneracaoInfo, db_manager

logger = logging.getLogger(__name__)

BASE_URL = "https://botucatusp.dcfiorilli.com.br:879/transparenciacamara/"
TIMEOUT_MS = 20000

# Só "CORPO LEGISLATIVO" nos interessa aqui (vereadores + presidência da Mesa) - o resto
# do CSV é o quadro de servidores administrativos da Secretaria da Câmara.
UNIDADE_ALVO = "CORPO LEGISLATIVO"


def _frame(page: Page) -> Frame:
    fr = page.frame(name="frmPaginaAspx")
    if fr is None:
        raise RuntimeError("Frame de conteúdo (frmPaginaAspx) não encontrado")
    return fr


def _legislatura_atual_inicio() -> date:
    with db_manager.get_connection() as conn:
        row = conn.execute("SELECT MAX(data_inicio) AS d FROM legislaturas").fetchone()
    if not row or not row["d"]:
        return date(date.today().year, 1, 1)
    ano, mes, dia = row["d"].split("-")
    return date(int(ano), int(mes), int(dia))


def _navegar_para_servidores(page: Page):
    page.goto(BASE_URL, wait_until="networkidle", timeout=60000)
    page.evaluate("() => ProcessaDados('LnkServidores')")
    _frame(page).locator("#btnPesquisar").wait_for(state="visible", timeout=TIMEOUT_MS)


def _selecionar_exercicio(page: Page, ano: int):
    """Troca o ano no seletor global "Escolha o Exercício". Isso dispara uma atualização
    assíncrona (mostra um overlay "Processando...") - não é uma navegação de página, então
    esperar por load_state não adianta; é preciso esperar o overlay sumir."""
    page.evaluate(
        """(ano) => {
            window.cmbExercicio.SetValue(String(ano));
            window.cmbExercicio.RaiseValueChangedEvent();
        }""",
        ano,
    )
    try:
        page.wait_for_selector("text=Processando", state="visible", timeout=3000)
    except Exception:
        pass  # pode já ter passado rápido demais para pegar
    page.wait_for_selector("text=Processando", state="hidden", timeout=TIMEOUT_MS)
    page.wait_for_timeout(500)

    page.evaluate("() => ProcessaDados('LnkServidores')")
    _frame(page).locator("#btnPesquisar").wait_for(state="visible", timeout=TIMEOUT_MS)


def _pesquisar_mes(page: Page, mes: int) -> Frame:
    # o valor esperado pelo combo é o número do mês com dois dígitos ("07"), não o nome
    # ("Julho") nem o número sem zero à esquerda - confirmado testando ao vivo.
    fr = _frame(page)
    fr.evaluate(
        """(mes) => {
            window.cmbMes.SetValue(mes);
            window.cmbMes.RaiseValueChangedEvent();
        }""",
        f"{mes:02d}",
    )
    page.wait_for_timeout(1000)  # a troca de mês também pode recarregar o frame

    fr = _frame(page)
    fr.locator("#btnPesquisar").click(force=True, timeout=TIMEOUT_MS)

    fr = _frame(page)
    fr.locator("#btnExportarCSV").wait_for(state="visible", timeout=TIMEOUT_MS)
    return fr


def _exportar_csv(page: Page, fr: Frame) -> bytes:
    with page.expect_download(timeout=TIMEOUT_MS) as dl_info:
        fr.locator("#btnExportarCSV").click(force=True)
    caminho = dl_info.value.path()
    with open(caminho, "rb") as f:
        return f.read()


def _parse_valor(texto: str):
    if not texto or not texto.strip():
        return None
    texto = texto.strip().replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def _parse_csv(conteudo: bytes, ano: int, mes: int):
    texto = conteudo.decode("latin-1")
    leitor = csv.DictReader(io.StringIO(texto), delimiter=";")
    registros = []
    for linha in leitor:
        if (linha.get("Unidade") or "").strip().upper() != UNIDADE_ALVO:
            continue
        registros.append(RemuneracaoInfo(
            nome_portal=(linha.get("Nome") or "").strip(),
            cargo=(linha.get("Cargo") or "").strip() or None,
            ano=ano,
            mes=mes,
            proventos=_parse_valor(linha.get("Proventos")),
            liquido=_parse_valor(linha.get("Líquido")),
            data_admissao=(linha.get("Data Admissão") or "").strip() or None,
            data_desligamento=(linha.get("Data Desligamento") or "").strip() or None,
            unidade=(linha.get("Unidade") or "").strip(),
        ))
    return registros


def scrape_remuneracao(ano_inicio: int = None, ano_fim: int = None) -> dict:
    ano_inicio = ano_inicio or _legislatura_atual_inicio().year
    ano_fim = ano_fim or date.today().year

    total = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(ignore_https_errors=True, accept_downloads=True)

        for ano in range(ano_inicio, ano_fim + 1):
            ultimo_mes = 12
            if ano == date.today().year:
                ultimo_mes = date.today().month

            for indice_mes in range(1, ultimo_mes + 1):
                try:
                    # Renavegar do zero a cada mês (em vez de reaproveitar a página) -
                    # mais lento, mas evidenciou-se muito mais confiável: reaproveitar
                    # o estado entre pesquisas sucessivas corrompia o botão de exportar
                    # em meses seguintes. Ver ROADMAP.md.
                    _navegar_para_servidores(page)
                    if ano != date.today().year:
                        try:
                            _selecionar_exercicio(page, ano)
                        except Exception as e:
                            logger.warning(f"Não foi possível trocar para o exercício {ano} ({e}); pulando esse ano")
                            break

                    fr = _pesquisar_mes(page, indice_mes)
                    conteudo = _exportar_csv(page, fr)
                    registros = _parse_csv(conteudo, ano, indice_mes)
                    for registro in registros:
                        db_manager.upsert_remuneracao(registro)
                    total += len(registros)
                    logger.info(f"{ano}-{indice_mes:02d}: {len(registros)} registros ({UNIDADE_ALVO})")
                except Exception as e:
                    logger.warning(f"Falha ao coletar remuneração de {ano}-{indice_mes:02d}: {e}")

        browser.close()

    logger.info(f"Total de registros de remuneração coletados: {total}")
    return {"total_registros": total}


if __name__ == "__main__":
    from .utils import setup_logging
    setup_logging()
    scrape_remuneracao()
