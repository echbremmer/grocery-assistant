# Build stage: install dependencies and the app into /app/.venv with uv.
FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

# Runtime stage: just Python, the venv and the query config.
FROM python:3.13-slim
COPY --from=build /app/.venv /app/.venv
COPY config /app/config
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    GA_CONFIG=/app/config/queries.yaml
WORKDIR /app
USER 568:568
ENTRYPOINT ["grocery-assistant"]
CMD ["serve"]
