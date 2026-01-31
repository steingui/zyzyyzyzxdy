#!/usr/bin/env python3
"""Teste de carregamento de escalações."""

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # Opções anti-detecção
    browser = p.chromium.launch(
        headless=True,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-dev-shm-usage'
        ]
    )
    context = browser.new_context(
        user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        viewport={'width': 1920, 'height': 1080}
    )
    page = context.new_page()
    
    print("Carregando página...")
    page.goto("https://www.ogol.com.br/jogo/2026-01-28-atletico-mineiro-palmeiras/11860784", 
              wait_until="domcontentloaded", timeout=60000)
    print("Página carregada")
    
    page.wait_for_timeout(2000)
    
    # Scroll até o final
    print("Scrollando...")
    for y in range(0, 8000, 500):
        page.evaluate(f'window.scrollTo(0, {y})')
        page.wait_for_timeout(200)
    
    page.wait_for_timeout(2000)
    
    # Encontrar todos os jogadores com número E seu container pai
    js_code = '''
        (() => {
            const players = [];
            
            document.querySelectorAll('.player').forEach((p, idx) => {
                const nameEl = p.querySelector('a[href*="/jogador/"]');
                const numEl = p.querySelector('.number');
                
                if (!nameEl || !numEl) return;
                
                const number = parseInt(numEl.textContent.trim());
                if (isNaN(number)) return;
                
                const name = nameEl.textContent.trim();
                const isInactive = p.className.includes('inactive');
                
                // Encontrar container pai com classes relevantes
                let parent = p.parentElement;
                let parentInfo = '';
                for (let i = 0; i < 10 && parent; i++) {
                    const classes = parent.className || '';
                    if (classes.includes('home') || classes.includes('away') || 
                        classes.includes('left') || classes.includes('right') ||
                        classes.includes('team-') || classes.includes('lineup')) {
                        parentInfo = classes;
                        break;
                    }
                    // Também verificar atributos data-
                    if (parent.dataset && (parent.dataset.team || parent.dataset.side)) {
                        parentInfo = parent.dataset.team || parent.dataset.side;
                        break;
                    }
                    parent = parent.parentElement;
                }
                
                players.push({
                    idx: idx,
                    nome: name,
                    numero: number,
                    isInactive: isInactive,
                    parentInfo: parentInfo || 'no-parent-found'
                });
            });
            
            // Agrupar por parentInfo
            const groups = {};
            players.forEach(p => {
                if (!groups[p.parentInfo]) {
                    groups[p.parentInfo] = [];
                }
                groups[p.parentInfo].push(p);
            });
            
            return { players: players.slice(0, 30), groups: Object.keys(groups).map(k => ({
                key: k,
                count: groups[k].length,
                sample: groups[k].slice(0, 3).map(p => p.nome)
            })) };
        })()
    '''
    
    result = page.evaluate(js_code)
    
    print("\n=== GRUPOS DE JOGADORES ===")
    for g in result['groups']:
        print(f"  [{g['key']}] count={g['count']} sample={g['sample']}")
    
    print("\n=== PRIMEIROS 30 JOGADORES ===")
    for p in result['players']:
        print(f"  [{p['idx']:2d}] {p['nome']:25s} #{p['numero']:2d} inactive={p['isInactive']} parent='{p['parentInfo']}'")
    
    browser.close()
