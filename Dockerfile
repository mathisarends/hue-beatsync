# Build with:
#   docker compose build
# or:
#   docker build .
FROM python:3.13-slim

# sounddevice (the hue-beatsync[sounddevice] extra) loads PortAudio at
# import time via ctypes, so the shared library must be present. git is for
# uv to fetch hueify, which hue-beatsync pins to a commit rather than a release.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    libportaudio2 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /usr/local/bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock README.md ./
COPY hue_beatsync/ hue_beatsync/

RUN uv sync --frozen --no-dev --extra sounddevice

EXPOSE 8765

CMD ["uvicorn", "hue_beatsync.server.main:app", "--host", "0.0.0.0", "--port", "8765"]
