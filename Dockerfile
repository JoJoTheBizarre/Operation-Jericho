# Jericho MCP Server Dockerfile
# Provides a containerized MCP server for playing classic text adventure games
#
# Build:
#   docker build -t jericho-mcp-server .
#
# Run interactively (for testing):
#   docker run -it --rm jericho-mcp-server
#
# Run in stdio mode (for MCP clients):
#   docker run -i --rm jericho-mcp-server
#
# For Claude Desktop integration, you would need a wrapper script that
# runs 'docker run' with appropriate stdio forwarding.

FROM python:3.12-slim

LABEL maintainer="Operation Jericho"
LABEL description="MCP server for playing classic text adventure games (Zork, Adventure, etc.)"
LABEL version="0.1.0"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv (Python package manager) via pip
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy dependency files and source code first
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY jericho_mcp_server.py ./

# Install dependencies and package using uv
RUN uv pip install --system -e .

# Clone game files from GitHub
RUN git clone https://github.com/BYU-PCCL/z-machine-games.git /tmp/z-machine-games && \
    mkdir -p /app/games && \
    cp -r /tmp/z-machine-games/jericho-game-suite /app/games/ && \
    rm -rf /tmp/z-machine-games

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV HOME=/home/appuser

# Run the MCP server using the installed script
ENTRYPOINT ["jericho-mcp-server"]