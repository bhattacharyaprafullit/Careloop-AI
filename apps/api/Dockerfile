FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    MODEL_DIR=/app/ml/artifacts \
    PYTHONPATH=/app:/app/apps/api

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY ml /app/ml
COPY apps/api /app/apps/api

WORKDIR /app/apps/api
RUN uv sync --frozen --no-dev

EXPOSE 7860

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
