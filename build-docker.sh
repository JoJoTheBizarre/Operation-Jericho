#!/bin/bash
# Build script for Jericho MCP Server Docker image

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="jericho-mcp-server"
TAG="${1:-latest}"

echo "Building $IMAGE_NAME:$TAG ..."
echo "Context directory: $SCRIPT_DIR"

# Check Docker availability
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not in PATH"
    exit 1
fi

# Build the image
docker build \
    -t "$IMAGE_NAME:$TAG" \
    -t "$IMAGE_NAME:latest" \
    "$SCRIPT_DIR"

echo ""
echo "Build successful!"
echo "Image: $IMAGE_NAME:$TAG"
echo "Image: $IMAGE_NAME:latest"
echo ""
echo "To run the container interactively:"
echo "  docker run -it --rm $IMAGE_NAME:latest"
echo ""
echo "To run the MCP server (for testing stdio):"
echo "  docker run -i --rm $IMAGE_NAME:latest"
echo ""
echo "To use with an MCP client, you would need to set up stdio forwarding."
echo "For Claude Desktop, consider using a wrapper script that runs docker run."