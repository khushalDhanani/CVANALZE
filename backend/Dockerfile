FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache --no-dev --no-install-project

FROM python:3.12-slim-bookworm

ARG INSTALL_MSSQL_ODBC=true

WORKDIR /app

# Keep only PDF/OCR and ODBC runtime libraries. Local Apple Silicon builds set
# INSTALL_MSSQL_ODBC=false and omit the Microsoft driver entirely.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libgl1 libglib2.0-0 unixodbc \
    && if [ "$INSTALL_MSSQL_ODBC" = "true" ]; then \
        apt-get install -y --no-install-recommends curl \
        && curl -sSL https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb -o /tmp/packages-microsoft-prod.deb \
        && dpkg -i /tmp/packages-microsoft-prod.deb \
        && rm /tmp/packages-microsoft-prod.deb \
        && apt-get update \
        && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
        && apt-get purge -y curl \
        && apt-get autoremove -y; \
    fi \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
