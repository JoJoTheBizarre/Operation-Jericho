# Jericho FastMCP Server Dockerfile
# Multi-stage build for optimized image size and faster rebuilds
#
# Build:
#   docker build -t jericho-fastmcp-server .
#
# Run HTTP server:
#   docker run -p 8000:8000 --rm jericho-fastmcp-server
#
# Run with custom host/port:
#   docker run -p 8080:8000 -e PORT=8000 -e HOST=0.0.0.0 --rm jericho-fastmcp-server
#
# For Claude Desktop integration, you would need to configure the HTTP endpoint.

# Stage 1: Builder - install dependencies and clone games
FROM python:3.12-slim AS builder

# Install system dependencies needed for building and git
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv (Python package manager) via pip
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies into a target directory (not system-wide)
RUN uv pip install --target /app/deps .

# Clone game files from GitHub
RUN git clone https://github.com/BYU-PCCL/z-machine-games.git /tmp/z-machine-games && \
    mkdir -p /app/games/z-machine-games && \
    cp -r /tmp/z-machine-games/jericho-game-suite /app/games/z-machine-games/ && \
    rm -rf /tmp/z-machine-games

# Stage 2: Runtime - minimal image with only necessary files
FROM python:3.12-slim AS runtime

# Install curl for health check (optional)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependencies from builder stage
COPY --from=builder /app/deps /app/deps

# Add dependencies to Python path and ensure scripts are in PATH
ENV PYTHONPATH="/app/deps:/app"
ENV PATH="/app/deps/bin:${PATH}"

# Copy application source code
COPY src/ ./src/
COPY fastmcp_server.py ./
COPY jericho_mcp_server.py ./

# Copy game files from builder
COPY --from=builder /app/games ./games

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV HOME=/home/appuser
ENV HOST=0.0.0.0
ENV PORT=8000

# Health check (HTTP endpoint)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose the HTTP port
EXPOSE ${PORT}

# Run the FastMCP HTTP server using the installed script
ENTRYPOINT ["jericho-http-server"]