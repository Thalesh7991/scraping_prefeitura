import asyncio
import aiohttp
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import logging
import time
import re
import os
from pathlib import Path

from .config import config
from .database import db_manager, Vereador, Propositura

logger = logging.getLogger(__name__)

class RateLimiter:
    """Controla a taxa de requisições"""
    
    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self.last_request = 0
    
    async def wait(self):
        """Espera o tempo necessário antes da próxima requisição"""
        now = time.time()
        elapsed = now - self.last_request
        if elapsed < self.delay:
            await asyncio.sleep(self.delay - elapsed)
        self.last_request = time.time()

class CamaraScraper:
    """Scraper principal da Câmara de Vereadores"""
    
    def __init__(self):
        self.config = config.scraping
        self.rate_limiter = RateLimiter(self.config.request_delay)
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Context manager async entry"""
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(
            headers=self.config.headers,
            timeout=timeout
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager async exit"""
        if self.session:
            await self.session.close()
    
    async def _make_request(self, url: str, retries: int = None) -> Optional[BeautifulSoup]:
        """Faz requisição HTTP com retry e rate limiting"""
        if retries is None:
            retries = self.config.max_retries
        
        await self.rate_limiter.wait()
        
        for attempt in range(retries + 1):
            try:
                logger.debug(f"Fazendo requisição para: {url} (tentativa {attempt + 1})")
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        content = await response.text()
                        return BeautifulSoup(content, 'html.parser')
                    else:
                        logger.warning(f"Status {response.status} para URL: {url}")
                        
            except Exception as e:
                logger.warning(f"Erro na tentativa {attempt + 1} para {url}: {e}")
                
                if attempt < retries:
                    wait_time = self.config.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(f"Aguardando {wait_time}s antes da próxima tentativa")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Falha após {retries + 1} tentativas para {url}")
                    
        return None
    
    def _make_sync_request(self, url: str) -> Optional[BeautifulSoup]:
        """Versão síncrona para compatibilidade"""
        try:
            time.sleep(self.config.request_delay)
            response = requests.get(url, headers=self.config.headers, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            logger.error(f"Erro na requisição síncrona para {url}: {e}")
            return None
    
    async def scrape_vereadores_info(self) -> List[Vereador]:
        """Coleta informações básicas dos vereadores"""
        logger.info("Iniciando coleta de informações dos vereadores")
        
        soup = await self._make_request(self.config.vereadores_url)
        if not soup:
            raise Exception("Não foi possível acessar a página dos vereadores")
        
        vereadores = []
        
        # Extrair nomes e links
        lista_vereadores = soup.find_all('h2')
        for h2 in lista_vereadores:
            if h2.a:
                link = h2.a.get('href')
                nome_completo = h2.a.text
                # Extrair apenas o nome político (após o hífen)
                if ' - ' in nome_completo:
                    nome = nome_completo.split(' - ')[1].strip()
                else:
                    nome = nome_completo.strip()
                
                vereadores.append({'nome': nome, 'link': link})
        
        # Extrair partidos
        tags_span = soup.find_all('span')
        partidos = []
        for span in tags_span:
            if span.find_all(['li']) and span.find_all('a'):
                partido = span.text.replace('\n', '').strip()
                if partido:
                    partidos.append(partido)
        
        # Combinar nomes, partidos e links
        vereadores_completos = []
        min_len = min(len(vereadores), len(partidos))
        
        for i in range(min_len):
            vereador = Vereador(
                nome=vereadores[i]['nome'],
                partido=partidos[i],
                link=vereadores[i]['link']
            )
            vereadores_completos.append(vereador)
        
        logger.info(f"Coletados dados de {len(vereadores_completos)} vereadores")
        return vereadores_completos
    
    async def download_image(self, img_url: str, filename: str) -> bool:
        """Download de imagem de vereador"""
        try:
            await self.rate_limiter.wait()
            
            async with self.session.get(img_url) as response:
                if response.status == 200:
                    content = await response.read()
                    
                    filepath = Path(config.img_dir) / filename
                    filepath.parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(filepath, 'wb') as f:
                        f.write(content)
                    
                    logger.debug(f"Imagem salva: {filename}")
                    return True
                    
        except Exception as e:
            logger.error(f"Erro ao baixar imagem {filename}: {e}")
            
        return False
    
    async def scrape_vereadores_images(self) -> int:
        """Coleta imagens dos vereadores"""
        logger.info("Iniciando download das imagens dos vereadores")
        
        soup = await self._make_request(self.config.vereadores_url)
        if not soup:
            logger.error("Não foi possível acessar a página para imagens")
            return 0
        
        images_downloaded = 0
        
        # Encontrar divs com imagens
        divs_col = soup.find_all('div', {'class': 'col-md-3'})
        
        for div in divs_col:
            img_div = div.find('div', {'class': 'img'})
            if img_div and img_div.find('img'):
                img_tag = img_div.find('img')
                src = img_tag.get('src')
                alt = img_tag.get('alt', '')
                
                if src and alt:
                    # Extrair nome do vereador do alt
                    if ' - ' in alt:
                        nome = alt.split(' - ')[1].strip()
                    else:
                        nome = alt.strip()
                    
                    img_url = f"{self.config.base_url}/{src}"
                    filename = f"{nome}.jpg"
                    
                    if await self.download_image(img_url, filename):
                        images_downloaded += 1
        
        logger.info(f"Download concluído: {images_downloaded} imagens")
        return images_downloaded
    
    async def scrape_proposituras_summary(self, vereador: Vereador) -> List[Dict]:
        """Coleta resumo das proposituras de um vereador"""
        if not vereador.link:
            logger.warning(f"Vereador {vereador.nome} não possui link")
            return []
        
        soup = await self._make_request(vereador.link)
        if not soup:
            logger.error(f"Não foi possível acessar dados de {vereador.nome}")
            return []
        
        proposituras = []
        
        # Encontrar tabela de documentos
        tabelas = soup.find_all('table')
        tabela_documentos = None
        
        for tabela in tabelas:
            caption = tabela.find('caption')
            if caption and 'Documentos' in caption.text:
                tabela_documentos = tabela
                break
        
        if not tabela_documentos:
            logger.warning(f"Tabela de documentos não encontrada para {vereador.nome}")
            return []
        
        # Extrair anos
        anos_headers = tabela_documentos.find_all('th', {'class': 'text-right'})
        anos = []
        for th in anos_headers:
            if th.text and th.text.strip() != 'Total':
                anos.append(th.text.strip())
        
        anos = sorted(list(set(anos)))
        
        # Extrair dados das linhas
        tbody = tabela_documentos.find('tbody')
        if tbody:
            rows = tbody.find_all('tr')
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    tipo = cells[0].text.strip()
                    if tipo == 'Total':
                        continue
                    
                    # Pegar quantidades por ano
                    quantidades = []
                    for i in range(1, len(cells) - 1):  # Excluir primeira e última coluna
                        qty_text = cells[i].text.strip()
                        qty = 0 if qty_text == '-' else int(qty_text) if qty_text.isdigit() else 0
                        quantidades.append(qty)
                    
                    # Criar registros por ano
                    for i, ano in enumerate(anos):
                        if i < len(quantidades):
                            proposituras.append({
                                'vereador': vereador.nome,
                                'tipo': tipo,
                                'quantidade': quantidades[i],
                                'ano': ano
                            })
        
        logger.info(f"Coletadas {len(proposituras)} proposituras resumidas de {vereador.nome}")
        return proposituras
    
    async def scrape_proposituras_detalhadas(self, vereador_nome: str, link_proposituras: str) -> List[Propositura]:
        """Coleta proposituras detalhadas de um vereador"""
        logger.info(f"Coletando proposituras detalhadas de {vereador_nome}")
        
        soup = await self._make_request(f"{self.config.base_url}{link_proposituras}")
        if not soup:
            return []
        
        proposituras = []
        
        # Encontrar seções de proposituras
        sections = soup.find_all('div', {'class': 'data-list-item data-list-striped data-list-hover'})
        
        for section in sections:
            h3 = section.find('h3')
            if not h3:
                continue
            
            tipo = h3.text.strip()
            links_propostas = section.find_all('p')
            
            # Processar cada proposta individual
            for p in links_propostas:
                a_tag = p.find('a')
                if not a_tag:
                    continue
                
                link_proposta = a_tag.get('href')
                if not link_proposta:
                    continue
                
                full_link = f"{self.config.base_url}{link_proposta}"
                
                # Verificar se já foi processado
                if db_manager.link_exists(full_link, vereador_nome):
                    logger.debug(f"Link já processado: {full_link}")
                    continue
                
                # Processar proposta individual
                proposta = await self._process_individual_proposta(
                    full_link, vereador_nome, tipo
                )
                
                if proposta:
                    proposituras.append(proposta)
                    # Marcar como processado
                    db_manager.insert_link(full_link, vereador_nome)
                
                # Rate limiting entre propostas
                await asyncio.sleep(0.5)
        
        logger.info(f"Processadas {len(proposituras)} proposituras detalhadas de {vereador_nome}")
        return proposituras
    
    async def _process_individual_proposta(self, url: str, vereador: str, tipo: str) -> Optional[Propositura]:
        """Processa uma proposta individual"""
        soup = await self._make_request(url)
        if not soup:
            return None
        
        # Extrair situação
        situacao_tag = soup.find('strong', text='Situação:')
        if not situacao_tag:
            return None
        
        situacao = situacao_tag.find_next_sibling(text=True)
        if situacao:
            situacao = situacao.strip()
        else:
            return None
        
        # Extrair data
        data_tag = soup.find('strong', text='Data:')
        if not data_tag:
            return None
        
        data_text = data_tag.find_next_sibling(text=True)
        if not data_text:
            return None
        
        try:
            data = datetime.strptime(data_text.strip(), '%d/%m/%Y')
        except ValueError:
            logger.warning(f"Data inválida: {data_text}")
            return None
        
        # Filtrar por ano mínimo
        if data.year < self.config.min_year:
            return None
        
        return Propositura(
            vereador=vereador,
            tipo=tipo,
            situacao=situacao,
            data=data
        )
    
    async def get_vereadores_proposituras_links(self) -> List[Dict[str, str]]:
        """Obtém links para proposituras detalhadas de todos os vereadores"""
        soup = await self._make_request(self.config.consulta_url)
        if not soup:
            return []
        
        links = []
        items = soup.find_all('div', {'class': 'data-list-item data-list-striped data-list-hover'})
        
        for item in items:
            # Encontrar nome do vereador
            nome_element = item.find('h4') or item.find('h3') or item.find('strong')
            if not nome_element:
                continue
            
            nome = nome_element.text.strip()
            if ' - ' in nome:
                nome = nome.split(' - ')[1].strip()
            
            # Encontrar link "Detalhadas"
            links_item = item.find_all('a')
            for a in links_item:
                if 'Detalhadas' in a.text:
                    link = a.get('href')
                    if link:
                        links.append({
                            'vereador': nome,
                            'link': link
                        })
                    break
        
        # Filtrar vereadores licenciados
        links_filtered = [
            item for item in links 
            if 'Licenciad' not in item['vereador']
        ]
        
        logger.info(f"Encontrados links para {len(links_filtered)} vereadores ativos")
        return links_filtered

# Funções de conveniência para usar sem async/await
def scrape_vereadores_sync() -> List[Vereador]:
    """Versão síncrona para coletar vereadores"""
    scraper = CamaraScraper()
    soup = scraper._make_sync_request(config.scraping.vereadores_url)
    
    if not soup:
        return []
    
    vereadores = []
    lista_vereadores = soup.find_all('h2')
    
    # Extrair nomes e links
    nomes_links = []
    for h2 in lista_vereadores:
        if h2.a:
            link = h2.a.get('href')
            nome_completo = h2.a.text
            if ' - ' in nome_completo:
                nome = nome_completo.split(' - ')[1].strip()
            else:
                nome = nome_completo.strip()
            nomes_links.append({'nome': nome, 'link': link})
    
    # Extrair partidos
    tags_span = soup.find_all('span')
    partidos = []
    for span in tags_span:
        if span.find_all(['li']) and span.find_all('a'):
            partido = span.text.replace('\n', '').strip()
            if partido:
                partidos.append(partido)
    
    # Combinar dados
    min_len = min(len(nomes_links), len(partidos))
    for i in range(min_len):
        vereador = Vereador(
            nome=nomes_links[i]['nome'],
            partido=partidos[i],
            link=nomes_links[i]['link']
        )
        vereadores.append(vereador)
    
    return vereadores 