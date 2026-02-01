# RFC 002: Strict League & Season Association

## Status
**Draft**

## Context
Currently, the relationship between a match (`Partida`) and its championship (`Liga`/`Temporada`) is determined implicitly by the arguments passed to the scraping script (`run_batch.py --league X --year Y`). The scraper extracts match details (teams, score, events) but relies on these external arguments to link the match to a season in the database.

**Problem:**
- **Data Integrity Risk:** If `run_batch.py` is executed with incorrect arguments (e.g., scraping Premier League URLs but passing `--league brasileirao`), the database will incorrectly incorrect match data under the wrong league.
- **No Verification:** There is no mechanism to verify that the scraped match actually belongs to the intended championship. "Everton x Brighton" could be saved as a "Brasileirão" match if the command is run incorrectly.

## Objectives
1.  **Extract Context:** Modify the scraper to extract explicit League and Season information directly from the match page.
2.  **Validate Integrity:** Ensure the scraped context matches the target storage context.
3.  **Strict Persistence:** Refuse to save data if there is a mismatch, or automatically route to the correct league/season (Auto-Discovery).

## Proposed Changes

### 1. Scraper Update (`scripts/extractors.py` & `scripts/scraper.py`)
Enhance `extract_match_info` to parse the competition header and season year from the `ogol.com.br` page.

**Target Elements:**
- Breadcrumbs or `div.competition-name` usually contain "Premier League 2025/26".
- Parse this string to extract:
    - `competition_name` (e.g., "Premier League")
    - `season_year` (e.g., "2025/26" -> 2026)

### 2. Normalization (`scripts/utils/normalization.py`)
- Map the extracted `competition_name` to our internal `league_slug` (e.g., "Premier League" -> "premier-league").
- Normalize `season_year` to an integer (end year convention, e.g., 2025/26 -> 2026).

### 3. Ingestion Logic (`scripts/db_importer.py`)
Modify `process_input` to accept the extracted context and perform validation.

**New Logic:**
```python
def process_input(data: dict, target_league_slug: str, target_year: int):
    # 1. Validation
    scraped_league = data.get('league_slug')
    scraped_year = data.get('season_year')
    
    if scraped_league != target_league_slug:
        raise ValueError(f"League Mismatch! Target: {target_league_slug}, Scraped: {scraped_league}")
        
    if scraped_year != target_year:
        raise ValueError(f"Season Mismatch! Target: {target_year}, Scraped: {scraped_year}")
        
    # 2. Persistence (Existing logic)
    ...
```

### 4. Database verification
- Ensure `Refactor v2.1` changes (Foreign Keys) are being respected.

## Implementation Steps
1.  **Exploration**: Inspect Ogol match pages HTML to find reliable selectors for League/Season.
2.  **Scraper**: Implement `extract_championship_context` function.
3.  **Importer**: Update `db_importer.py` to enforce strict validation.
4.  **Testing**: Run a batch with intentional mismatch to verify failure/safety.
