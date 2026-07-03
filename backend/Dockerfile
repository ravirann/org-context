FROM python:3.12-slim

RUN pip install --no-cache-dir uv

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

# Install dependencies first (cached layer), then the project itself.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev && chmod +x scripts/*.sh

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

CMD ["/app/scripts/start-api.sh"]
