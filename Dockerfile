# Dockerfile for Render Deployment
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium only to save size)
RUN playwright install chromium

# Copy application code
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY migrations/ ./migrations/
COPY api_app.py .
COPY .env.example .env

# Create logs directory
RUN mkdir -p logs && chmod 777 logs

# Environment variables
ENV PYTHONUNBUFFERED=1

# Expose port (Render sets PORT env var)
EXPOSE 8000

# Start Gunicorn
CMD ["gunicorn", "api_app:app", "--bind", "0.0.0.0:8000", "--timeout", "120", "--workers", "2"]
