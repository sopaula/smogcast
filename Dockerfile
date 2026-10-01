# Etap budowania zależności.
FROM python:3.12-slim AS builder

WORKDIR /app

# Instaluje uv.
RUN pip install --no-cache-dir uv

# Kopiuje pliki zależności.
COPY pyproject.toml uv.lock ./

# Tworzy środowisko bez zależności developerskich.
RUN uv sync \
    --frozen \
    --no-dev \
    --no-install-project


# Finalny obraz aplikacji.
FROM python:3.12-slim AS runtime

WORKDIR /app

# Kopiuje gotowe środowisko z etapu builder.
COPY --from=builder /app/.venv /app/.venv

# Kopiuje kod projektu.
COPY src ./src
COPY scripts ./scripts
COPY models ./models

# Tworzy katalogi na dane i model.
RUN mkdir -p /app/data /app/models /data

# Ustawia środowisko aplikacji.
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Domyślna komenda uruchamia API.
CMD ["uvicorn", "smogcast.api.main:app", "--host", "0.0.0.0", "--port", "8000"]