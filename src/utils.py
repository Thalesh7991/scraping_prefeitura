import logging
import time
import sys
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from typing import Any, Dict, List
import json

from .config import config

def setup_logging(level: int = logging.INFO):
    """Configura sistema de logging"""
    
    # Criar diretório de logs se não existir
    log_dir = Path(config.logs_dir)
    log_dir.mkdir(exist_ok=True)
    
    # Nome do arquivo de log com timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"scraping_{timestamp}.log"
    
    # Configurar formatação
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Handler para arquivo
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Handler para console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    
    # Configurar logger root
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Silenciar logs de bibliotecas externas
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    
    logging.info(f"Sistema de logging configurado. Arquivo: {log_file}")

@contextmanager
def measure_time(operation_name: str):
    """Context manager para medir tempo de execução"""
    logger = logging.getLogger(__name__)
    start_time = time.time()
    
    logger.info(f"Iniciando operação: {operation_name}")
    
    try:
        yield
    finally:
        duration = time.time() - start_time
        logger.info(f"Operação '{operation_name}' concluída em {duration:.2f}s")

class MetricsCollector:
    """Coletor de métricas de performance"""
    
    def __init__(self):
        self.metrics: Dict[str, Any] = {
            'start_time': None,
            'end_time': None,
            'operations': [],
            'errors': [],
            'requests_count': 0,
            'data_collected': {}
        }
    
    def start_session(self):
        """Inicia uma sessão de métricas"""
        self.metrics['start_time'] = datetime.now()
    
    def end_session(self):
        """Finaliza uma sessão de métricas"""
        self.metrics['end_time'] = datetime.now()
    
    def record_operation(self, name: str, duration: float, success: bool = True):
        """Registra uma operação"""
        self.metrics['operations'].append({
            'name': name,
            'duration': duration,
            'success': success,
            'timestamp': datetime.now()
        })
    
    def record_error(self, error: str, context: str = None):
        """Registra um erro"""
        self.metrics['errors'].append({
            'error': error,
            'context': context,
            'timestamp': datetime.now()
        })
    
    def increment_requests(self):
        """Incrementa contador de requisições"""
        self.metrics['requests_count'] += 1
    
    def set_data_collected(self, key: str, count: int):
        """Define quantidade de dados coletados"""
        self.metrics['data_collected'][key] = count
    
    def get_summary(self) -> Dict[str, Any]:
        """Retorna resumo das métricas"""
        if not self.metrics['start_time']:
            return {}
        
        total_duration = None
        if self.metrics['end_time']:
            total_duration = (self.metrics['end_time'] - self.metrics['start_time']).total_seconds()
        
        successful_ops = [op for op in self.metrics['operations'] if op['success']]
        failed_ops = [op for op in self.metrics['operations'] if not op['success']]
        
        return {
            'session_duration': total_duration,
            'total_operations': len(self.metrics['operations']),
            'successful_operations': len(successful_ops),
            'failed_operations': len(failed_ops),
            'total_requests': self.metrics['requests_count'],
            'total_errors': len(self.metrics['errors']),
            'data_collected': self.metrics['data_collected'],
            'avg_operation_time': sum(op['duration'] for op in successful_ops) / len(successful_ops) if successful_ops else 0
        }
    
    def save_to_file(self, filename: str = None):
        """Salva métricas em arquivo JSON"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"metrics_{timestamp}.json"
        
        filepath = Path(config.data_dir) / filename
        
        # Converter datetime para string para serialização JSON
        metrics_copy = self.metrics.copy()
        for key in ['start_time', 'end_time']:
            if metrics_copy[key]:
                metrics_copy[key] = metrics_copy[key].isoformat()
        
        for op in metrics_copy['operations']:
            op['timestamp'] = op['timestamp'].isoformat()
        
        for error in metrics_copy['errors']:
            error['timestamp'] = error['timestamp'].isoformat()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(metrics_copy, f, indent=2, ensure_ascii=False)
        
        logging.info(f"Métricas salvas em: {filepath}")

def clean_text(text: str) -> str:
    """Limpa e normaliza texto"""
    if not text:
        return ""
    
    # Remover quebras de linha e espaços extras
    cleaned = ' '.join(text.split())
    
    # Remover caracteres especiais problemáticos
    cleaned = cleaned.replace('\xa0', ' ')  # Non-breaking space
    cleaned = cleaned.replace('\u200b', '')  # Zero-width space
    
    return cleaned.strip()

def safe_get_text(element, default: str = "") -> str:
    """Extrai texto de elemento HTML de forma segura"""
    if not element:
        return default
    
    try:
        return clean_text(element.get_text())
    except:
        return default

def parse_date_br(date_str: str) -> datetime:
    """Parse de data no formato brasileiro dd/mm/yyyy"""
    try:
        return datetime.strptime(date_str.strip(), '%d/%m/%Y')
    except ValueError:
        raise ValueError(f"Data inválida: {date_str}")

def normalize_vereador_name(name: str) -> str:
    """Normaliza nome de vereador"""
    if not name:
        return ""
    
    # Remover prefixos comuns
    name = name.strip()
    
    # Extrair nome após hífen se existir
    if ' - ' in name:
        name = name.split(' - ')[-1].strip()
    
    return clean_text(name)

def extract_number_from_text(text: str) -> int:
    """Extrai número de texto, retornando 0 se não encontrar"""
    if not text:
        return 0
    
    text = text.strip()
    
    if text == '-' or text == '':
        return 0
    
    try:
        return int(text)
    except ValueError:
        # Tentar extrair apenas os dígitos
        import re
        numbers = re.findall(r'\d+', text)
        if numbers:
            return int(numbers[0])
        return 0

def create_backup_filename(base_name: str, extension: str = "json") -> str:
    """Cria nome de arquivo de backup com timestamp"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}_backup_{timestamp}.{extension}"

def ensure_directory_exists(path: str):
    """Garante que um diretório existe"""
    Path(path).mkdir(parents=True, exist_ok=True)

def format_duration(seconds: float) -> str:
    """Formata duração em formato legível"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{int(minutes)}m {secs:.1f}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{int(hours)}h {int(minutes)}m {secs:.1f}s"

def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """Divide lista em chunks menores"""
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

# Instância global do coletor de métricas
metrics = MetricsCollector() 