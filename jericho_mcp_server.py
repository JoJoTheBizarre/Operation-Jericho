#!/usr/bin/env python3
"""
Jericho MCP Server - A Model Context Protocol server for playing text adventure games.
Provides tools to interact with classic Z-machine games (Zork, Adventure, etc.)
using the Jericho library.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Import our jericho wrapper
from src.zork_env import (
    TextAdventureEnv,
    GameState,
    list_available_games,
    discover_games,
)


# Initialize the MCP server
server = Server("jericho-mcp-server")


# Session management
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


@server.list_tools()
async def list_tools() -> List[Tool]:
    """
    List all available tools that this MCP server provides.
    Each tool enables interaction with text adventure games.
    """
    return [
        Tool(
            name="list_available_games",
            description="List all available text adventure games",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of games to return (0 for all)",
                        "default": 0,
                    }
                },
            },
        ),
        Tool(
            name="create_game_session",
            description="Start a new game session with a specific game",
            inputSchema={
                "type": "object",
                "properties": {
                    "game_name": {
                        "type": "string",
                        "description": "Name of the game to start (e.g., 'zork1', 'advent')",
                    }
                },
                "required": ["game_name"],
            },
        ),
        Tool(
            name="game_step",
            description="Take an action in the game (move, take item, use object, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID returned by create_game_session",
                    },
                    "action": {
                        "type": "string",
                        "description": "Action to perform (e.g., 'go north', 'take lamp', 'look')",
                    },
                },
                "required": ["session_id", "action"],
            },
        ),
        Tool(
            name="get_game_state",
            description="Get the current state of a game session",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID returned by create_game_session",
                    }
                },
                "required": ["session_id"],
            },
        ),
        Tool(
            name="get_valid_actions",
            description="Get a list of valid actions for the current game state",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID returned by create_game_session",
                    }
                },
                "required": ["session_id"],
            },
        ),
        Tool(
            name="reset_game",
            description="Reset a game session to the beginning",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID returned by create_game_session",
                    }
                },
                "required": ["session_id"],
            },
        ),
        Tool(
            name="close_game_session",
            description="Close a game session and free resources",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID returned by create_game_session",
                    }
                },
                "required": ["session_id"],
            },
        ),
        Tool(
            name="save_game_state",
            description="Save the current game state for later restoration",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID returned by create_game_session",
                    }
                },
                "required": ["session_id"],
            },
        ),
        Tool(
            name="load_game_state",
            description="Load a previously saved game state",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID returned by create_game_session",
                    },
                    "state_data": {
                        "type": "string",
                        "description": "Saved state data from save_game_state",
                    },
                },
                "required": ["session_id", "state_data"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    """
    Handle tool calls from the MCP client.
    Routes to appropriate game interaction handler.
    """
    # Clean up expired sessions periodically
    _cleanup_expired_sessions()

    # Route to appropriate handler
    if name == "list_available_games":
        return await handle_list_games(arguments)
    elif name == "create_game_session":
        return await handle_create_session(arguments)
    elif name == "game_step":
        return await handle_game_step(arguments)
    elif name == "get_game_state":
        return await handle_get_game_state(arguments)
    elif name == "get_valid_actions":
        return await handle_get_valid_actions(arguments)
    elif name == "reset_game":
        return await handle_reset_game(arguments)
    elif name == "close_game_session":
        return await handle_close_session(arguments)
    elif name == "save_game_state":
        return await handle_save_state(arguments)
    elif name == "load_game_state":
        return await handle_load_state(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def handle_list_games(arguments: dict) -> List[TextContent]:
    """Handle list_available_games tool call."""
    limit = arguments.get("limit", 0)

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

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": f"Failed to list games: {str(e)}"}, indent=2),
            )
        ]


async def handle_create_session(arguments: dict) -> List[TextContent]:
    """Handle create_game_session tool call."""
    game_name = arguments.get("game_name")

    if not game_name:
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": "game_name is required"}, indent=2),
            )
        ]

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

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": f"Failed to create game session: {str(e)}"}, indent=2
                ),
            )
        ]


async def handle_game_step(arguments: dict) -> List[TextContent]:
    """Handle game_step tool call."""
    session_id = arguments.get("session_id")
    action = arguments.get("action")

    if not session_id or not action:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": "session_id and action are required"}, indent=2
                ),
            )
        ]

    session = _get_session(session_id)
    if not session:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": f"Session not found: {session_id}"}, indent=2
                ),
            )
        ]

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

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": f"Failed to execute action '{action}': {str(e)}"},
                    indent=2,
                ),
            )
        ]


async def handle_get_game_state(arguments: dict) -> List[TextContent]:
    """Handle get_game_state tool call."""
    session_id = arguments.get("session_id")

    if not session_id:
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": "session_id is required"}, indent=2),
            )
        ]

    session = _get_session(session_id)
    if not session:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": f"Session not found: {session_id}"}, indent=2
                ),
            )
        ]

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

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def handle_get_valid_actions(arguments: dict) -> List[TextContent]:
    """Handle get_valid_actions tool call."""
    session_id = arguments.get("session_id")

    if not session_id:
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": "session_id is required"}, indent=2),
            )
        ]

    session = _get_session(session_id)
    if not session:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": f"Session not found: {session_id}"}, indent=2
                ),
            )
        ]

    try:
        valid_actions = session.env.get_valid_actions()

        result = {
            "session_id": session_id,
            "valid_actions": valid_actions,
            "count": len(valid_actions),
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": f"Failed to get valid actions: {str(e)}"}, indent=2
                ),
            )
        ]


async def handle_reset_game(arguments: dict) -> List[TextContent]:
    """Handle reset_game tool call."""
    session_id = arguments.get("session_id")

    if not session_id:
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": "session_id is required"}, indent=2),
            )
        ]

    session = _get_session(session_id)
    if not session:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": f"Session not found: {session_id}"}, indent=2
                ),
            )
        ]

    try:
        state = session.env.reset()
        session.current_state = state

        result = {
            "session_id": session_id,
            "game_name": session.game_name,
            "reset_state": _format_game_state(state),
            "message": "Game reset to beginning",
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": f"Failed to reset game: {str(e)}"}, indent=2),
            )
        ]


async def handle_close_session(arguments: dict) -> List[TextContent]:
    """Handle close_game_session tool call."""
    session_id = arguments.get("session_id")

    if not session_id:
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": "session_id is required"}, indent=2),
            )
        ]

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

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def handle_save_state(arguments: dict) -> List[TextContent]:
    """Handle save_game_state tool call."""
    session_id = arguments.get("session_id")

    if not session_id:
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": "session_id is required"}, indent=2),
            )
        ]

    session = _get_session(session_id)
    if not session:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": f"Session not found: {session_id}"}, indent=2
                ),
            )
        ]

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

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": f"Failed to save game state: {str(e)}"}, indent=2
                ),
            )
        ]


async def handle_load_state(arguments: dict) -> List[TextContent]:
    """Handle load_game_state tool call."""
    session_id = arguments.get("session_id")
    state_data = arguments.get("state_data")

    if not session_id or not state_data:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": "session_id and state_data are required"}, indent=2
                ),
            )
        ]

    session = _get_session(session_id)
    if not session:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": f"Session not found: {session_id}"}, indent=2
                ),
            )
        ]

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

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": f"Failed to load game state: {str(e)}"}, indent=2
                ),
            )
        ]


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


async def main():
    """Main entry point to run the MCP server over stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
