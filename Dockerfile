# syntax=docker/dockerfile:1.4
# ── Builder stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv once — cached as its own layer
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy ONLY the dependency manifest first.
# This layer is only invalidated when pyproject.toml changes,
# so rebuilt source code doesn't re-trigger the 4-minute install.
COPY pyproject.toml ./

# uv cache mount: compiled wheels are cached on the host across builds.
# --no-sources: don't install the local package itself yet (no src/ needed here)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --no-sources .

# Download games — separate layer so it's also independently cached
RUN git clone --depth=1 https://github.com/BYU-PCCL/z-machine-games.git /tmp/z-machine-games && \
    mkdir -p /app/games && \
    cp -r /tmp/z-machine-games/jericho-game-suite /app/games/jericho-game-suite && \
    rm -rf /tmp/z-machine-games

# Copy source last — most frequently changed, isolated to its own layer
COPY src/ ./src/
COPY main.py ./


# ── Runtime stage ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY --from=builder /app/src ./src
COPY --from=builder /app/main.py ./

# Games at the exact path get_default_games_dir() expects:
#   Path(__file__).parent.parent / "games" / "jericho-game-suite"
#   = /app/games/jericho-game-suite
COPY --from=builder /app/games/jericho-game-suite ./games/jericho-game-suite

# Non-root user
RUN useradd -m -u 1000 -s /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

ENV PYTHONUNBUFFERED=1
ENV HOME=/home/appuser

ENV HOST=${HOST}
ENV PORT=${PORT}

EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["python", "main.py"]