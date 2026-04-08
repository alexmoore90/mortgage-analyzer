# ── Base image ────────────────────────────────────────────────────
FROM python:3.12-slim

# Keeps Python from generating .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
# Keeps Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files first (layer cache friendly)
COPY pyproject.toml uv.lock* ./

# Install dependencies into the system Python (no venv inside Docker)
RUN uv sync --frozen --no-dev --no-editable

# Copy application code
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

# Run the app using uv
CMD ["uv", "run", "streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
