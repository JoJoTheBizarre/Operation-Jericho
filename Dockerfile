FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./

RUN uv pip install --target /app/deps .

RUN git clone https://github.com/BYU-PCCL/z-machine-games.git /tmp/z-machine-games && \
    mkdir -p /app/games/z-machine-games && \
    cp -r /tmp/z-machine-games/jericho-game-suite /app/games/z-machine-games/ && \
    rm -rf /tmp/z-machine-games

FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/deps /app/deps

ENV PYTHONPATH="/app/deps:/app"
ENV PATH="/app/deps/bin:${PATH}"

COPY src/ ./src/
COPY fastmcp_server.py ./

COPY --from=builder /app/games ./games

RUN useradd -m -u 1000 -s /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

ENV PYTHONUNBUFFERED=1
ENV HOME=/home/appuser
ENV HOST=0.0.0.0
ENV PORT=8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

EXPOSE ${PORT}

ENTRYPOINT ["jericho-http-server"]
