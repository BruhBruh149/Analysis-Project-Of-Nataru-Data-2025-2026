# ==============================================================================
# Dockerfile - Sistem Analitik Transportasi Nataru (Streamlit & Python 3.11)
# ==============================================================================
FROM python:3.11-slim

# Set environment variables for Python & Streamlit
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    DEFAULT_DB_ENGINE=SQLITE

# Install lightweight system dependencies for build & healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency definition first for Docker layer caching
COPY requirements.txt .

# Upgrade pip and install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project source code and assets
COPY . .

# Ensure storage directories exist
RUN mkdir -p data_cache grafik_analisis_nataru exported_analytics_csv

# Expose Streamlit default port
EXPOSE 8501

# Healthcheck to verify dashboard responsiveness
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Default command to start the Streamlit Analytics Dashboard
CMD ["streamlit", "run", "Main.py", "--server.port=8501", "--server.address=0.0.0.0"]
