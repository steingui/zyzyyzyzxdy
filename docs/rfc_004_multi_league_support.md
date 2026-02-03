# RFC 004: Suporte a Scraping Multi-Liga

## 1. Contexto
O projeto atualmente faz scraping de dados do "Brasileirão" do site `ogol.com.br`. O objetivo é expandir a cobertura para outras grandes ligas:
- **Premier League** (Inglaterra)
- **La Liga** (Espanha)
- **Ligue 1** (França)

A hipótese do usuário é que, dado que a estrutura DOM do `ogol.com.br` é consistente entre competições, o pipeline de scraping existente deve funcionar para estas ligas simplesmente parametrizando as requisições.

## 2. Análise da Arquitetura Atual

O pipeline de scraping consiste em quatro componentes principais:
1.  **Camada de API (`app/routes/scrape.py`)**: Aceita `league` (slug), `year` e `round`. Valida a existência na tabela `ligas`. Dispara o job em background.
2.  **Orquestrador (`scripts/run_batch.py`)**: Recebe argumentos e coordena o processo.
3.  **Crawler (`scripts/crawl_round.py`)**: Gera URLs baseadas em `https://www.ogol.com.br/competicao/{league_slug}?jornada_in={round}`.
4.  **Scraper (`scripts/scraper.py`)**: Faz o parse do HTML da partida.
5.  **Importador (`scripts/db_importer.py`)**: Insere dados no PostgreSQL, resolvendo liga e temporada via `ogol_slug`.

### 2.1 Verificação da Base de Código
- **Construção de URL Genérica**: Verificada em `scripts/crawl_round.py`. Usa interpolação de string com o argumento `league_slug`.
- **Parsing Genérico**: `scripts/scraper.py` busca IDs padrão (`#fixture_games`, `#game_report`) que representam o template central da plataforma Ogol.
- **Esquema do Banco de Dados**: A tabela `ligas` contém `ogol_slug`, que faz a ponte entre o parâmetro da API, a URL externa e o ID interno.

## 3. Resultados & Validação

O sistema **JÁ É CAPAZ** de suportar estas ligas sem alterações estruturais de código, sujeito aos seguintes passos de configuração:

### 3.1 Simulação de Caso de Uso
Requisição:
```bash
POST /api/scrape
{
  "league": "premier-league",
  "year": 2026,
  "round": 1
}
```
**Fluxo:**
1. API busca na tabela `ligas` por `ogol_slug="premier-league"`.
2. Se encontrado, cria o job `scrape_premier-league_2026_1_...`.
3. `crawl_round.py` acessa `https://www.ogol.com.br/competicao/premier-league?jornada_in=1`.
4. `run_batch.py` alimenta URLs para o `scraper.py`.
5. `db_importer.py` insere partidas vinculando ao ID da `premier-league`.

### 3.2 Pré-requisitos
O único bloqueio para execução imediata é a **ausência destas ligas no banco de dados**. A API explicitamente rejeita validação de ligas desconhecidas.

## 4. Plano de Implementação

Para habilitar esta funcionalidade, devemos popular o banco de dados com as ligas alvo.

### 4.1 Seeding SQL
Execute o seguinte SQL para registrar as ligas:

```sql
INSERT INTO ligas (nome, slug, ogol_slug, pais, confederacao, num_times, num_rodadas) 
VALUES 
('Premier League', 'premier-league', 'premier-league', 'Inglaterra', 'UEFA', 20, 38),
('La Liga', 'la-liga', 'campeonato-espanhol', 'Espanha', 'UEFA', 20, 38),
('Ligue 1', 'ligue-1', 'campeonato-frances', 'França', 'UEFA', 18, 34)
ON CONFLICT (slug) DO NOTHING;
```

*Nota: Verifique `num_times` e `num_rodadas` para o ano específico da temporada caso variem (ex: Ligue 1 reduzida a 18 times).*

## 5. Conclusão
A hipótese do usuário está **CONFIRMADA**. Os resultados funcionais para o endpoint serão idênticos em estrutura, diferindo apenas nos dados de domínio (`league_id`, `season_id`) armazenados no banco. Nenhuma refatoração é necessária, apenas população de dados.
