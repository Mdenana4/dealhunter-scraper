# DealHunter API - Cloud Run Optimized
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy ALL source first (including modified requirements.txt)
COPY . .

# Install ALL dependencies (now includes gunicorn)
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

RUN chmod +x start.sh

EXPOSE 8080

CMD ["sh", "start.sh"]
