FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml ./

RUN uv pip install --system --no-cache .

RUN git clone https://github.com/BYU-PCCL/z-machine-games.git /tmp/z-machine-games && \
    mkdir -p /app/games/z-machine-games && \
    cp -r /tmp/z-machine-games/jericho-game-suite /app/games/z-machine-games/ && \
    rm -rf /tmp/z-machine-games

FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY src/ ./src/
COPY main.py ./

COPY --from=builder /app/games ./games

RUN useradd -m -u 1000 -s /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

ENV PYTHONUNBUFFERED=1
ENV HOME=/home/appuser
ARG HOST=0.0.0.0
ARG PORT=8000
ENV HOST=${HOST}
ENV PORT=${PORT}

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

EXPOSE ${PORT}

ENTRYPOINT ["python", "-m", "main"]