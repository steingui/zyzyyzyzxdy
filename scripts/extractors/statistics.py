"""
statistics.py - Extrai estatísticas da partida
"""

import json
import logging
from typing import Any, Dict
from playwright.sync_api import Page

from ..utils.browser import safe_eval
from ..utils.parsing import parse_value
from ..config import STATS_FIELD_MAPPING

logger = logging.getLogger(__name__)


def extract_statistics(page: Page) -> Dict[str, Dict[str, Any]]:
    """
    Extrai estatísticas usando .zz-container como fonte primária.
    
    Prioridade:
    1. Tabela inline dentro de .zz-container
    2. Fallback para .graph-bar (layout antigo)
    
    Args:
        page: Página do Playwright com o jogo carregado
        
    Returns:
        Dicionário com stats_home e stats_away
    """
    # Serializar o mapeamento para usar no JS
    field_mapping_json = json.dumps(STATS_FIELD_MAPPING)
    
    result = safe_eval(page, f'''
        (() => {{
            const stats = {{ home: {{}}, away: {{}} }};
            const seen = new Set();
            
            const fieldMapping = {field_mapping_json};
            
            // PRIORIDADE 1: Tabela inline dentro de .zz-container
            const container = document.querySelector('.zz-container');
            if (container) {{
                const table = container.querySelector('table');
                if (table) {{
                    const rows = table.querySelectorAll('tr');
                    if (rows.length >= 2) {{
                        const headerCells = rows[0].querySelectorAll('td, th');
                        const valueCells = rows[1].querySelectorAll('td, th');
                        
                        headerCells.forEach((cell, idx) => {{
                            const label = cell.textContent.trim().toLowerCase();
                            const field = fieldMapping[label];
                            
                            if (field && !seen.has(field) && valueCells[idx]) {{
                                seen.add(field);
                                const valueText = valueCells[idx].textContent.trim();
                                
                                // Regex para extrair números/percentuais separados
                                const parts = valueText.split(/[●○]|\\s{{2,}}/).map(s => s.trim()).filter(s => s);
                                
                                if (parts.length >= 2) {{
                                    stats.home[field] = parts[0];
                                    stats.away[field] = parts[parts.length - 1];
                                }} else {{
                                    const nums = valueText.match(/[\\d.,]+%?/g);
                                    if (nums && nums.length >= 2) {{
                                        stats.home[field] = nums[0];
                                        stats.away[field] = nums[nums.length - 1];
                                    }}
                                }}
                            }}
                        }});
                    }}
                }}
            }}
            
            // PRIORIDADE 2: Fallback para .graph-bar (layout antigo)
            if (Object.keys(stats.home).length === 0) {{
                document.querySelectorAll('.graph-bar').forEach(bar => {{
                    const titleEl = bar.querySelector('.bars-title');
                    const values = bar.querySelectorAll('.bar-header .num');
                    
                    if (titleEl && values.length >= 2) {{
                        const name = titleEl.textContent.trim().toLowerCase();
                        const field = fieldMapping[name];
                        
                        if (field && !seen.has(field)) {{
                            seen.add(field);
                            stats.home[field] = values[0].textContent.trim();
                            stats.away[field] = values[values.length - 1].textContent.trim();
                        }}
                    }}
                }});
            }}
            
            return stats;
        }})()
    ''', {'home': {}, 'away': {}})
    
    # Converter valores para números
    stats_home: Dict[str, Any] = {}
    stats_away: Dict[str, Any] = {}
    
    for field, val in result.get('home', {}).items():
        parsed = parse_value(val, field)
        if parsed is not None:
            stats_home[field] = parsed
            
    for field, val in result.get('away', {}).items():
        parsed = parse_value(val, field)
        if parsed is not None:
            stats_away[field] = parsed
    
    return {'stats_home': stats_home, 'stats_away': stats_away}
