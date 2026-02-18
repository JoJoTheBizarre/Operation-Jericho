#!/usr/bin/env python3
"""
Jericho FastMCP Server - A FastMCP HTTP server for playing text adventure games.
Provides tools to interact with classic Z-machine games (Zork, Adventure, etc.)
using the Jericho library via HTTP transport.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List
from pathlib import Path

from fastmcp import FastMCP, Context
from starlette.responses import JSONResponse

# Import our jericho wrapper
from src.zork_env import (
    TextAdventureEnv,
    GameState,
    list_available_games,
    discover_games,
)


# Initialize the FastMCP server
mcp = FastMCP("jericho-fastmcp-server")


# Session management (same as before)
class GameSession:
    """Represents an active game session."""

    def __init__(self, env: TextAdventureEnv, game_name: str):
        self.env = env
        self.game_name = game_name
        self.created_at = datetime.now()
        self.last_accessed = datetime.now()
        self.current_state: Optional[GameState] = None

    def update_access_time(self):
        self.last_accessed = datetime.now()

    def is_expired(self, timeout_minutes: int = 60) -> bool:
        """Check if session has been inactive for too long."""
        return datetime.now() - self.last_accessed > timedelta(minutes=timeout_minutes)


# Global session storage
_sessions: Dict[str, GameSession] = {}


def _generate_session_id() -> str:
    """Generate a unique session ID."""
    return str(uuid.uuid4())


def _get_session(session_id: str) -> Optional[GameSession]:
    """Get a session by ID, updating its access time."""
    session = _sessions.get(session_id)
    if session:
        session.update_access_time()
    return session


def _cleanup_expired_sessions(timeout_minutes: int = 60):
    """Remove expired sessions."""
    expired_ids = [
        session_id
        for session_id, session in _sessions.items()
        if session.is_expired(timeout_minutes)
    ]
    for session_id in expired_ids:
        del _sessions[session_id]
    return len(expired_ids)


def _format_game_state(state: GameState) -> dict:
    """Format a GameState object for JSON serialization."""
    return {
        "observation": state.observation,
        "score": state.score,
        "max_score": state.max_score,
        "moves": state.moves,
        "done": state.done,
        "reward": state.reward,
        "inventory": state.inventory,
        "location": state.location,
    }


# Clean up expired sessions periodically (maybe on each request)
# We'll add a simple cleanup before each tool call via middleware or just call in each tool


# Define FastMCP tools
@mcp.tool
async def list_available_games_tool(limit: int = 0) -> dict:
    """List all available text adventure games.

    Args:
        limit: Maximum number of games to return (0 for all)
    """
    _cleanup_expired_sessions()
    try:
        games = list_available_games()
        if limit > 0:
            games = games[:limit]

        result = {
            "total_games": len(games),
            "games": games,
            "default_games_dir": str(
                Path(__file__).parent
                / "games"
                / "z-machine-games"
                / "jericho-game-suite"
            ),
        }
        return result
    except Exception as e:
        return {"error": f"Failed to list games: {str(e)}"}


@mcp.tool
async def create_game_session(game_name: str) -> dict:
    """Start a new game session with a specific game.

    Args:
        game_name: Name of the game to start (e.g., 'zork1', 'advent')
    """
    _cleanup_expired_sessions()
    if not game_name:
        return {"error": "game_name is required"}

    try:
        # Create game environment
        env = TextAdventureEnv(game_name)
        state = env.reset()

        # Create session
        session_id = _generate_session_id()
        session = GameSession(env, game_name)
        session.current_state = state
        _sessions[session_id] = session

        result = {
            "session_id": session_id,
            "game_name": game_name,
            "initial_state": _format_game_state(state),
            "message": f"Started game '{game_name}'. Use session_id for future interactions.",
        }
        return result
    except Exception as e:
        return {"error": f"Failed to create game session: {str(e)}"}


@mcp.tool
async def game_step(session_id: str, action: str) -> dict:
    """Take an action in the game (move, take item, use object, etc.).

    Args:
        session_id: Session ID returned by create_game_session
        action: Action to perform (e.g., 'go north', 'take lamp', 'look')
    """
    _cleanup_expired_sessions()
    if not session_id or not action:
        return {"error": "session_id and action are required"}

    session = _get_session(session_id)
    if not session:
        return {"error": f"Session not found: {session_id}"}

    try:
        # Take the action
        state = session.env.step(action)
        session.current_state = state

        result = {
            "session_id": session_id,
            "action": action,
            "new_state": _format_game_state(state),
            "action_result": state.observation,
        }
        return result
    except Exception as e:
        return {"error": f"Failed to execute action '{action}': {str(e)}"}


@mcp.tool
async def get_game_state(session_id: str) -> dict:
    """Get the current state of a game session.

    Args:
        session_id: Session ID returned by create_game_session
    """
    _cleanup_expired_sessions()
    if not session_id:
        return {"error": "session_id is required"}

    session = _get_session(session_id)
    if not session:
        return {"error": f"Session not found: {session_id}"}

    # If we don't have a current state, get it
    if not session.current_state:
        try:
            # This is a fallback - normally we should always have current_state
            session.current_state = session.env.reset()
        except:
            pass

    result = {
        "session_id": session_id,
        "game_name": session.game_name,
        "state": _format_game_state(session.current_state)
        if session.current_state
        else None,
    }
    return result


@mcp.tool
async def get_valid_actions(session_id: str) -> dict:
    """Get a list of valid actions for the current game state.

    Args:
        session_id: Session ID returned by create_game_session
    """
    _cleanup_expired_sessions()
    if not session_id:
        return {"error": "session_id is required"}

    session = _get_session(session_id)
    if not session:
        return {"error": f"Session not found: {session_id}"}

    try:
        valid_actions = session.env.get_valid_actions()

        result = {
            "session_id": session_id,
            "valid_actions": valid_actions,
            "count": len(valid_actions),
        }
        return result
    except Exception as e:
        return {"error": f"Failed to get valid actions: {str(e)}"}


@mcp.tool
async def reset_game(session_id: str) -> dict:
    """Reset a game session to the beginning.

    Args:
        session_id: Session ID returned by create_game_session
    """
    _cleanup_expired_sessions()
    if not session_id:
        return {"error": "session_id is required"}

    session = _get_session(session_id)
    if not session:
        return {"error": f"Session not found: {session_id}"}

    try:
        state = session.env.reset()
        session.current_state = state

        result = {
            "session_id": session_id,
            "game_name": session.game_name,
            "reset_state": _format_game_state(state),
            "message": "Game reset to beginning",
        }
        return result
    except Exception as e:
        return {"error": f"Failed to reset game: {str(e)}"}


@mcp.tool
async def close_game_session(session_id: str) -> dict:
    """Close a game session and free resources.

    Args:
        session_id: Session ID returned by create_game_session
    """
    _cleanup_expired_sessions()
    if not session_id:
        return {"error": "session_id is required"}

    if session_id in _sessions:
        # Clean up resources if needed
        session = _sessions[session_id]
        if hasattr(session.env, "close"):
            session.env.close()
        del _sessions[session_id]

        result = {
            "session_id": session_id,
            "closed": True,
            "message": "Game session closed",
        }
    else:
        result = {
            "session_id": session_id,
            "closed": False,
            "message": "Session not found (may have already been closed)",
        }
    return result


@mcp.tool
async def save_game_state(session_id: str) -> dict:
    """Save the current game state for later restoration.

    Args:
        session_id: Session ID returned by create_game_session
    """
    _cleanup_expired_sessions()
    if not session_id:
        return {"error": "session_id is required"}

    session = _get_session(session_id)
    if not session:
        return {"error": f"Session not found: {session_id}"}

    try:
        saved_state = session.env.save_state()
        # Convert to JSON-serializable format if needed
        state_str = (
            json.dumps(saved_state)
            if isinstance(saved_state, (dict, list))
            else str(saved_state)
        )

        result = {
            "session_id": session_id,
            "state_data": state_str,
            "message": "Game state saved",
        }
        return result
    except Exception as e:
        return {"error": f"Failed to save game state: {str(e)}"}


@mcp.tool
async def load_game_state(session_id: str, state_data: str) -> dict:
    """Load a previously saved game state.

    Args:
        session_id: Session ID returned by create_game_session
        state_data: Saved state data from save_game_state
    """
    _cleanup_expired_sessions()
    if not session_id or not state_data:
        return {"error": "session_id and state_data are required"}

    session = _get_session(session_id)
    if not session:
        return {"error": f"Session not found: {session_id}"}

    try:
        # Parse state data
        try:
            # Try to parse as JSON first
            state = json.loads(state_data)
        except json.JSONDecodeError:
            # If not JSON, use as-is (might be a string representation)
            state = state_data

        session.env.load_state(state)

        # Get current state after loading
        # Note: load_state doesn't return state, so we need to get it differently
        # For now, we'll just acknowledge success
        result = {
            "session_id": session_id,
            "loaded": True,
            "message": "Game state loaded",
        }
        return result
    except Exception as e:
        return {"error": f"Failed to load game state: {str(e)}"}


# Add a health check endpoint
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint for monitoring."""
    return JSONResponse({"status": "healthy", "service": "jericho-mcp-server"})


# Create ASGI application for HTTP deployment
app = mcp.http_app()


def main():
    """Run the HTTP server using uvicorn."""
    import uvicorn
    import os

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    print(f"Starting Jericho FastMCP HTTP server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


# For direct HTTP server (alternative): use mcp.run(transport="http", host="0.0.0.0", port=8000)
if __name__ == "__main__":
    main()
