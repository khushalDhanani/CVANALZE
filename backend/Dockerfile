FROM python:3.12-slim-bookworm

WORKDIR /app

# Install the supported PDF/OCR runtime libraries, build tools, and Microsoft ODBC 18.
# Uploads support PDF/DOCX only; legacy .doc converters are intentionally excluded.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    unixodbc-dev \
    gcc \
    g++ \
    libgl1 \
    libglib2.0-0 \
    && curl -sSL https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb -o /tmp/packages-microsoft-prod.deb \
    && dpkg -i /tmp/packages-microsoft-prod.deb \
    && rm /tmp/packages-microsoft-prod.deb \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache

COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
