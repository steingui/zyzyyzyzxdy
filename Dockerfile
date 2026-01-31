# Dockerfile para o scraper do Brasileirão 2026
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Copiar requirements e instalar dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar navegadores Playwright
RUN playwright install chromium

# Copiar código
COPY scripts/ ./scripts/
COPY data/ ./data/

# Criar diretório de logs
RUN mkdir -p logs

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=""

# Comando padrão
CMD ["python3", "scripts/main.py"]
