# Smogcast

Aplikacja do analizy danych dotyczących jakości powietrza i smogu.

## Wymagania

- Python 3.12+
- uv

## Uruchomienie

### Instalacja zależności

```bash
uv sync
```

### Uruchomienie CLI

```bash
PYTHONPATH=src uv run python src/smogcast/cli.py
```

### Uruchomienie testów

```bash
uv run pytest
```