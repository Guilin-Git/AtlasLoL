FROM ghcr.io/astral-sh/uv:0.13.1 AS uv

FROM python:3.12.3-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/api \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=uv /uv /uvx /bin/

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin atlas

WORKDIR /app

# Dependencias sao instaladas antes do codigo para aproveitar o cache de build.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY api ./api

USER atlas

EXPOSE 8000

CMD ["/app/.venv/bin/uvicorn", "atlas_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
