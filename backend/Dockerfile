FROM python:3.12-slim AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Re-sync so uv registers the project itself
RUN uv sync --frozen --no-dev

# Create non-root user and give it ownership of the venv
RUN useradd --create-home appuser && chown -R appuser:appuser /app/.venv
USER appuser

ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["/app/.venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--timeout-keep-alive", "600"]
