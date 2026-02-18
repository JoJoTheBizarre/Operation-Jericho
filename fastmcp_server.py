import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict

from fastmcp import FastMCP
from starlette.responses import JSONResponse
from starlette.requests import Request
from src.zork_env import (
    TextAdventureEnv,
    GameState,
    list_available_games,
)


mcp = FastMCP("jericho-fastmcp-server")


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
        return datetime.now() - self.last_accessed > timedelta(minutes=timeout_minutes)


_sessions: Dict[str, GameSession] = {}


def _generate_session_id() -> str:
    return str(uuid.uuid4())


def _get_session(session_id: str) -> Optional[GameSession]:
    session = _sessions.get(session_id)
    if session:
        session.update_access_time()
    return session


def _cleanup_expired_sessions(timeout_minutes: int = 60):
    expired_ids = [
        session_id
        for session_id, session in _sessions.items()
        if session.is_expired(timeout_minutes)
    ]
    for session_id in expired_ids:
        del _sessions[session_id]
    return len(expired_ids)


def _format_game_state(state: GameState) -> dict:
    return {
        "observation": state.observation,
        "score": state.score,
        "max_score": state.max_score,
        "moves": state.moves,
        "done": state.done,
        "reward": state.reward,
        "inventory": state.inventory,
        "location": state.location,
        "state_hash": state.state_hash,
    }


@mcp.tool
async def list_available_games_tool(limit: int = 0) -> dict:
    """List all available text adventure games.

    Args:
        limit: Maximum number of games to return (0 for all)
    """
    _cleanup_expired_sessions()

    games = list_available_games()

    if limit > 0:
        games = games[:limit]

    return {
        "games": games,
        "total": len(list_available_games()),
        "showing": len(games),
    }


@mcp.tool
async def start_game(game_name: str) -> dict:
    """Start a new game session.

    Args:
        game_name: Name of the game to start (e.g., 'zork1', 'advent')
    """
    _cleanup_expired_sessions()

    try:
        env = TextAdventureEnv(game_name)
        state = env.reset()

        session_id = _generate_session_id()
        session = GameSession(env, game_name)
        session.current_state = state
        _sessions[session_id] = session

        return {
            "session_id": session_id,
            "game": game_name,
            "state": _format_game_state(state),
            "message": f"Started new game: {game_name}",
        }
    except Exception as e:
        return {
            "error": str(e),
            "game": game_name,
        }


@mcp.tool
async def take_action(session_id: str, action: str) -> dict:
    """Take an action in an active game session.

    Args:
        session_id: The session ID from start_game
        action: The command to execute (e.g., 'go north', 'take lamp')
    """
    _cleanup_expired_sessions()

    session = _get_session(session_id)
    if not session:
        return {"error": "Invalid or expired session ID"}

    try:
        state = session.env.step(action)
        session.current_state = state

        return {
            "session_id": session_id,
            "action": action,
            "state": _format_game_state(state),
        }
    except Exception as e:
        return {
            "error": str(e),
            "session_id": session_id,
            "action": action,
        }


@mcp.tool
async def get_game_state(session_id: str) -> dict:
    """Get the current state of an active game session.

    Args:
        session_id: The session ID from start_game
    """
    _cleanup_expired_sessions()

    session = _get_session(session_id)
    if not session:
        return {"error": "Invalid or expired session ID"}

    if not session.current_state:
        return {"error": "No state available. Game may not have been started."}

    return {
        "session_id": session_id,
        "game": session.game_name,
        "state": _format_game_state(session.current_state),
    }


@mcp.tool
async def get_valid_actions(session_id: str) -> dict:
    """Get a list of valid actions for the current game state.

    Args:
        session_id: The session ID from start_game
    """
    _cleanup_expired_sessions()

    session = _get_session(session_id)
    if not session:
        return {"error": "Invalid or expired session ID"}

    try:
        actions = session.env.get_valid_actions()
        return {
            "session_id": session_id,
            "valid_actions": actions,
            "count": len(actions),
        }
    except Exception as e:
        return {
            "error": str(e),
            "session_id": session_id,
        }


@mcp.tool
async def get_game_history(session_id: str, last_n: int = 10) -> dict:
    """Get the history of actions and observations.

    Args:
        session_id: The session ID from start_game
        last_n: Number of recent actions to return (0 for all)
    """
    _cleanup_expired_sessions()

    session = _get_session(session_id)
    if not session:
        return {"error": "Invalid or expired session ID"}

    history = session.env.get_history()
    if last_n > 0:
        history = history[-last_n:]

    formatted_history = [
        {"action": action, "observation": obs} for action, obs in history
    ]

    return {
        "session_id": session_id,
        "history": formatted_history,
        "total_moves": len(session.env.get_history()),
    }


@mcp.tool
async def end_game(session_id: str) -> dict:
    """End a game session and free resources.

    Args:
        session_id: The session ID to end
    """
    _cleanup_expired_sessions()

    session = _sessions.pop(session_id, None)
    if not session:
        return {"error": "Invalid or expired session ID"}

    session.env.close()

    return {
        "session_id": session_id,
        "message": f"Game session ended: {session.game_name}",
        "final_score": session.current_state.score if session.current_state else 0,
    }


@mcp.tool
async def save_game_state(session_id: str) -> dict:
    """Save the current game state (returns a state token).

    Args:
        session_id: The session ID from start_game
    """
    _cleanup_expired_sessions()

    session = _get_session(session_id)
    if not session:
        return {"error": "Invalid or expired session ID"}

    try:
        state_data = session.env.save_state()
        state_token = str(uuid.uuid4())

        if not hasattr(session, "_saved_states"):
            session._saved_states = {}
        session._saved_states[state_token] = state_data

        return {
            "session_id": session_id,
            "state_token": state_token,
            "message": "Game state saved successfully",
        }
    except Exception as e:
        return {
            "error": str(e),
            "session_id": session_id,
        }


@mcp.tool
async def load_game_state(session_id: str, state_token: str) -> dict:
    """Load a previously saved game state.

    Args:
        session_id: The session ID from start_game
        state_token: The token from save_game_state
    """
    _cleanup_expired_sessions()

    session = _get_session(session_id)
    if not session:
        return {"error": "Invalid or expired session ID"}

    if (
        not hasattr(session, "_saved_states")
        or state_token not in session._saved_states
    ):
        return {"error": "Invalid state token"}

    try:
        state_data = session._saved_states[state_token]
        session.env.load_state(state_data)

        return {
            "session_id": session_id,
            "state_token": state_token,
            "message": "Game state loaded successfully",
        }
    except Exception as e:
        return {
            "error": str(e),
            "session_id": session_id,
        }


@mcp.tool
async def get_world_objects(session_id: str) -> dict:
    """Get all objects in the game world with their relationships.

    Args:
        session_id: The session ID from start_game
    """
    _cleanup_expired_sessions()

    session = _get_session(session_id)
    if not session:
        return {"error": "Invalid or expired session ID"}

    try:
        objects = session.env.get_world_objects()
        return {
            "session_id": session_id,
            "objects": objects,
            "total_objects": len(objects),
        }
    except Exception as e:
        return {
            "error": str(e),
            "session_id": session_id,
        }


@mcp.tool
async def get_objects_in_location(session_id: str, location_name: str = "") -> dict:
    """Get all objects in a specific location or current location.

    Args:
        session_id: The session ID from start_game
        location_name: Name of location (empty for current location)
    """
    _cleanup_expired_sessions()

    session = _get_session(session_id)
    if not session:
        return {"error": "Invalid or expired session ID"}

    try:
        location = location_name if location_name else None
        objects = session.env.get_objects_in_location(location)
        return {
            "session_id": session_id,
            "location": location_name or "current",
            "objects": objects,
        }
    except Exception as e:
        return {
            "error": str(e),
            "session_id": session_id,
        }


@mcp.tool
async def get_object_details(session_id: str, object_name: str) -> dict:
    """Get detailed information about a specific object.

    Args:
        session_id: The session ID from start_game
        object_name: Name of the object to inspect
    """
    _cleanup_expired_sessions()

    session = _get_session(session_id)
    if not session:
        return {"error": "Invalid or expired session ID"}

    try:
        details = session.env.get_object_details(object_name)
        if details:
            return {
                "session_id": session_id,
                "object": details,
            }
        else:
            return {
                "session_id": session_id,
                "error": f"Object not found: {object_name}",
            }
    except Exception as e:
        return {
            "error": str(e),
            "session_id": session_id,
        }


@mcp.tool
async def check_state_visited(session_id: str) -> dict:
    """Check if the current game state has been visited before.

    Args:
        session_id: The session ID from start_game
    """
    _cleanup_expired_sessions()

    session = _get_session(session_id)
    if not session:
        return {"error": "Invalid or expired session ID"}

    try:
        current_hash = session.env.get_world_state_hash()
        is_visited = session.env.is_state_visited(current_hash)
        total_states = session.env.get_visited_states_count()

        return {
            "session_id": session_id,
            "current_state_hash": current_hash,
            "is_revisited": is_visited,
            "total_unique_states": total_states,
        }
    except Exception as e:
        return {
            "error": str(e),
            "session_id": session_id,
        }


@mcp.tool
async def get_game_dictionary(session_id: str) -> dict:
    """Get all words recognized by the game parser.

    Args:
        session_id: The session ID from start_game
    """
    _cleanup_expired_sessions()

    session = _get_session(session_id)
    if not session:
        return {"error": "Invalid or expired session ID"}

    try:
        dictionary = session.env.get_game_dictionary()
        return {
            "session_id": session_id,
            "vocabulary": dictionary,
            "word_count": len(dictionary),
        }
    except Exception as e:
        return {
            "error": str(e),
            "session_id": session_id,
        }


@mcp.tool
async def get_game_info(session_id: str) -> dict:
    """Get comprehensive game metadata and information.

    Args:
        session_id: The session ID from start_game
    """
    _cleanup_expired_sessions()

    session = _get_session(session_id)
    if not session:
        return {"error": "Invalid or expired session ID"}

    try:
        info = session.env.get_game_info()
        return {
            "session_id": session_id,
            "game_info": info,
        }
    except Exception as e:
        return {
            "error": str(e),
            "session_id": session_id,
        }


@mcp.tool
async def get_action_templates(session_id: str) -> dict:
    """Get action templates supported by the game.

    Args:
        session_id: The session ID from start_game
    """
    _cleanup_expired_sessions()

    session = _get_session(session_id)
    if not session:
        return {"error": "Invalid or expired session ID"}

    try:
        templates = session.env.get_action_templates()
        return {
            "session_id": session_id,
            "templates": templates,
            "template_count": len(templates),
        }
    except Exception as e:
        return {
            "error": str(e),
            "session_id": session_id,
        }


@mcp.tool
async def generate_template_actions(
    session_id: str, filter_type: list[str] = []
) -> dict:
    """Generate valid actions using templates and current game state.

    Args:
        session_id: The session ID from start_game
        filter_type: List of keywords to filter actions (e.g., ["take", "open"])
    """
    _cleanup_expired_sessions()

    session = _get_session(session_id)
    if not session:
        return {"error": "Invalid or expired session ID"}

    try:
        filter_list = filter_type if filter_type else None
        actions = session.env.generate_template_actions(filter_list)
        return {
            "session_id": session_id,
            "actions": actions,
            "action_count": len(actions),
            "filter_applied": filter_list,
        }
    except Exception as e:
        return {
            "error": str(e),
            "session_id": session_id,
        }


@mcp.tool
async def get_valid_actions_advanced(
    session_id: str,
    use_templates: bool = False,
    filter_type: list[str] = [],
    max_actions: int = 0,
) -> dict:
    """Get valid actions with advanced filtering options.

    Args:
        session_id: The session ID from start_game
        use_templates: Use template-based action generation
        filter_type: List of keywords to filter actions
        max_actions: Maximum number of actions to return (0 for all)
    """
    _cleanup_expired_sessions()

    session = _get_session(session_id)
    if not session:
        return {"error": "Invalid or expired session ID"}

    try:
        filter_list = filter_type if filter_type else None
        actions = session.env.get_valid_actions_advanced(
            use_templates=use_templates,
            filter_type=filter_list,
            max_actions=max_actions,
        )
        return {
            "session_id": session_id,
            "actions": actions,
            "action_count": len(actions),
            "template_based": use_templates,
        }
    except Exception as e:
        return {
            "error": str(e),
            "session_id": session_id,
        }


@mcp.tool
async def get_location_graph(session_id: str) -> dict:
    """Get a graph of all discovered locations and their connections.

    Args:
        session_id: The session ID from start_game
    """
    _cleanup_expired_sessions()

    session = _get_session(session_id)
    if not session:
        return {"error": "Invalid or expired session ID"}

    try:
        graph = session.env.get_location_graph()
        return {
            "session_id": session_id,
            "location_graph": graph,
            "location_count": len(graph),
        }
    except Exception as e:
        return {
            "error": str(e),
            "session_id": session_id,
        }


@mcp.tool
async def compare_to_walkthrough(session_id: str) -> dict:
    """Compare current progress to the optimal walkthrough.

    Args:
        session_id: The session ID from start_game
    """
    _cleanup_expired_sessions()

    session = _get_session(session_id)
    if not session:
        return {"error": "Invalid or expired session ID"}

    try:
        comparison = session.env.compare_to_walkthrough()
        return {
            "session_id": session_id,
            "comparison": comparison,
        }
    except Exception as e:
        return {
            "error": str(e),
            "session_id": session_id,
        }


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for Docker."""
    return JSONResponse({"status": "healthy", "service": "jericho-fastmcp-server"})


@mcp.custom_route("/sessions", methods=["GET"])
async def list_sessions(request: Request) -> JSONResponse:
    """List all active sessions."""
    _cleanup_expired_sessions()

    sessions = {
        session_id: {
            "game": session.game_name,
            "created_at": session.created_at.isoformat(),
            "last_accessed": session.last_accessed.isoformat(),
            "score": session.current_state.score if session.current_state else 0,
        }
        for session_id, session in _sessions.items()
    }

    return JSONResponse(
        {
            "active_sessions": len(sessions),
            "sessions": sessions,
        }
    )


def main():
    """Run the FastMCP HTTP server."""
    import os

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    print(f"Starting Jericho FastMCP Server on {host}:{port}")
    mcp.run(transport="sse", host=host, port=port)


if __name__ == "__main__":
    main()
