from typing import Optional
from fastmcp import FastMCP
from starlette.responses import JSONResponse
from starlette.requests import Request
from datetime import datetime

from .zork_env import TextAdventureEnv, list_available_games, GameState

app = FastMCP(
    name="jericho-simple",
    instructions="Play text adventure games with a simple interface. Only one game at a time - no session management needed!",
)


class SingleGameSession:
    """Manages a single active game session."""
    
    def __init__(self):
        self.env: Optional[TextAdventureEnv] = None
        self.game_name: Optional[str] = None
        self.current_state: Optional[GameState] = None
        self.started_at: Optional[datetime] = None
    
    def is_active(self) -> bool:
        """Check if there's an active game."""
        return self.env is not None
    
    def start_new_game(self, game_name: str) -> GameState:
        """Start a new game, replacing any existing session."""
        self.env = TextAdventureEnv(game_name)
        self.game_name = game_name
        self.current_state = self.env.reset()
        self.started_at = datetime.now()
        return self.current_state
    
    def clear(self):
        """Clear the current session."""
        self.env = None
        self.game_name = None
        self.current_state = None
        self.started_at = None


# Global single session
_game_session = SingleGameSession()


def _format_state(state: GameState) -> dict:
    """Format game state into a clean dictionary."""
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


@app.tool
def start_game(game_name: str = "zork1") -> dict:
    """
    Start a new text adventure game.
    
    This will END any currently active game and start fresh.    
    Args:
        game_name: Name of the game (default: 'zork1'). Use list_games() to see options.
    
    Returns:
        observation: What you see in the game
        score: Current score (usually 0)
        moves: Number of moves taken
        game: Which game is running
    """
    try:
        state = _game_session.start_new_game(game_name)
        
        response = _format_state(state)
        response["game"] = game_name
        response["message"] = f"Started {game_name}! Ready to play."
        
        return response
        
    except Exception as e:
        return {"error": f"Failed to start game: {str(e)}"}


@app.tool
def action(command: str) -> dict:
    """
    Take an action in the game. This is your main interaction tool.
    
    Args:
        command: What you want to do (e.g., 'north', 'take lamp', 'open mailbox', 'inventory')
    
    Returns:
        observation: What happened
        score: Current score
        moves: Move count
        done: Whether the game ended
        reward: Points gained this turn
    """
    if not _game_session.is_active():
        return {"error": "No active game. Use start_game() first!"}
    
    try:
        state = _game_session.env.step(command) #type: ignore
        _game_session.current_state = state
        
        response = _format_state(state)
        
        if state.done:
            response["message"] = "Game Over!"
        elif state.reward > 0:
            response["message"] = f"Good move! +{state.reward} points"
        
        return response
        
    except Exception as e:
        return {"error": f"Action failed: {str(e)}"}


@app.tool
def current_state() -> dict:
    """
    Get your current game state without taking an action.
    Useful to remember where you are and what you have.
    
    Returns:
        observation: Current location description
        score: Current score
        moves: Move count
        inventory: What you're carrying
        location: Current location name
        game: Which game you're playing
    """
    if not _game_session.is_active():
        return {"error": "No active game. Use start_game() first!"}
    
    if not _game_session.current_state:
        return {"error": "No state available. Something went wrong."}
    
    response = _format_state(_game_session.current_state)
    response["game"] = _game_session.game_name
    
    return response


@app.tool
def available_actions(limit: int = 20) -> dict:
    """
    Get a list of actions you can take right now.
    The game engine analyzes the current state to suggest valid commands.
    
    Args:
        limit: Maximum actions to return (default: 20, use 0 for all)
    
    Returns:
        actions: List of valid commands
        count: Total number available
    """
    if not _game_session.is_active():
        return {"error": "No active game. Use start_game() first!"}
    
    try:
        actions = _game_session.env.get_valid_actions() #type: ignore
        
        if limit > 0:
            actions = actions[:limit]
        
        return {
            "actions": actions,
            "count": len(actions),
            "tip": "Try these commands, or experiment with your own!"
        }
    except Exception as e:
        return {"error": str(e)}


@app.tool
def look_around() -> dict:
    """
    See what objects and locations are nearby.
    Helps you understand your environment better.
    
    Returns:
        current_location: Objects in your current room
        discovered_objects: Total objects found so far
        tips: Helpful exploration hints
    """
    if not _game_session.is_active():
        return {"error": "No active game. Use start_game() first!"}
    
    try:
        current_objects = _game_session.env.get_objects_in_location(None) #type: ignore
        all_objects = _game_session.env.get_world_objects() #type: ignore
        
        return {
            "current_location": current_objects,
            "discovered_objects": len(all_objects),
            "tips": [
                "Try examining objects you see",
                "Look for items you can take or interact with",
                "Check all exits (north, south, east, west, up, down)"
            ]
        }
    except Exception as e:
        return {"error": str(e)}


@app.tool
def recent_history(count: int = 5) -> dict:
    """
    Review your recent actions and what happened.
    Helps track your progress and avoid repeating mistakes.
    
    Args:
        count: Number of recent turns to show (default: 5)
    """
    if not _game_session.is_active():
        return {"error": "No active game. Use start_game() first!"}
    
    try:
        history = _game_session.env.get_history() #type: ignore
        recent = history[-count:] if count > 0 else history
        
        formatted = [
            {
                "action": action,
                "result": observation[:100] + "..." if len(observation) > 100 else observation
            }
            for action, observation in recent
        ]
        
        return {
            "recent_history": formatted,
            "total_moves": len(history),
        }
    except Exception as e:
        return {"error": str(e)}


@app.tool
def list_games(limit: int = 10) -> dict:
    """
    See all available text adventure games.
    
    Args:
        limit: Number of games to show (0 for all)
    """
    games = list_available_games()
    
    if limit > 0:
        games = games[:limit]
    
    return {
        "games": games,
        "total_available": len(list_available_games()),
        "showing": len(games),
        "popular": ["zork1", "zork2", "zork3", "advent", "detective"]
    }


@app.tool
def game_vocabulary() -> dict:
    """
    Get all words the game understands.
    Useful for figuring out what commands work.
    
    Returns vocabulary the game parser recognizes.
    """
    if not _game_session.is_active():
        return {"error": "No active game. Use start_game() first!"}
    
    try:
        vocab = _game_session.env.get_game_dictionary() #type: ignore
        
        # Organize by type
        verbs = [w for w in vocab if w in ['take', 'drop', 'open', 'close', 'go', 'look', 'examine', 'read', 'enter', 'exit', 'push', 'pull', 'turn', 'climb']]
        directions = [w for w in vocab if w in ['north', 'south', 'east', 'west', 'up', 'down', 'n', 's', 'e', 'w', 'u', 'd', 'northeast', 'northwest', 'southeast', 'southwest']]
        
        return {
            "total_words": len(vocab),
            "common_verbs": verbs,
            "directions": directions,
            "sample_words": vocab[:30] if len(vocab) > 30 else vocab,
        }
    except Exception as e:
        return {"error": str(e)}


@app.tool
def end_game() -> dict:
    """
    End the current game session.
    Use this when you're done playing or want to start a different game.
    """
    if not _game_session.is_active():
        return {"message": "No active game to end."}
    
    game_name = _game_session.game_name
    final_score = _game_session.current_state.score if _game_session.current_state else 0
    final_moves = _game_session.current_state.moves if _game_session.current_state else 0
    
    _game_session.clear()
    
    return {
        "message": f"Game ended: {game_name}",
        "final_score": final_score,
        "total_moves": final_moves,
    }


@app.tool
def explore_map() -> dict:
    """
    Get a map of discovered locations and their connections.
    Useful for navigation planning.
    """
    if not _game_session.is_active():
        return {"error": "No active game. Use start_game() first!"}
    
    try:
        graph = _game_session.env.get_location_graph() #type: ignore
        return {
            "location_graph": graph,
            "locations_discovered": len(graph),
            "tip": "Use this to plan your route through the game"
        }
    except Exception as e:
        return {"error": str(e)}


@app.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({
        "status": "healthy",
        "service": "jericho-simple-server",
        "game_active": _game_session.is_active(),
        "current_game": _game_session.game_name if _game_session.is_active() else None,
    })


@app.custom_route("/status", methods=["GET"])
async def game_status(request: Request) -> JSONResponse:
    """Get current game status."""
    if not _game_session.is_active():
        return JSONResponse({
            "active": False,
            "message": "No game currently active"
        })
    
    state = _game_session.current_state
    return JSONResponse({
        "active": True,
        "game": _game_session.game_name,
        "score": state.score if state else 0,
        "moves": state.moves if state else 0,
        "done": state.done if state else False,
        "started_at": _game_session.started_at.isoformat() if _game_session.started_at else None,
    })