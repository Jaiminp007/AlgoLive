# Python Backend
FROM python:3.11-slim

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

# Run with Python directly (Flask-SocketIO requires this for WebSocket support)
CMD ["python", "backend/app.py"]
