FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application source
COPY src/ src/

# Create data directory
RUN mkdir -p /data

ENV AGENTSYNC_DB_PATH=/data/agentsync.db
ENV PORT=8080

EXPOSE 8080

CMD ["python", "-m", "agentsync_mcp"]
