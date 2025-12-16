# Python Builder stage
FROM python:3.11-slim as backend

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy all source code
COPY . .

# Create agents directory if missing
RUN mkdir -p /app/market_simulation/agents

# Expose port
EXPOSE 5000

# Start with gunicorn + gevent for WebSocket support
CMD ["gunicorn", "--worker-class", "gevent", "-w", "1", "--bind", "0.0.0.0:5000", "backend.app:app"]
