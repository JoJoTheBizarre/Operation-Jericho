from fastmcp import FastMCP
from starlette.responses import JSONResponse
from starlette.requests import Request

from .zork_env import list_available_games
from .session import SingleGameSession, _format_state
from .resources import HOW_TO_PLAY, GUIDE_COMMANDS

app = FastMCP(
    name="jericho-text-adventure",
    instructions=(
        "You are playing Z-machine text adventure games via the Jericho engine. "
        "Read 'guide://how-to-play' before starting and 'guide://commands' whenever "
        "you need a command reference. Use 'game://info' to inspect the current session."
    ),
)

_game_session = SingleGameSession()


# ── Resources ────────────────────────────────────────────────────────────────

@app.resource("guide://how-to-play")
def guide_how_to_play() -> str:
    """
    Complete guide to playing text adventure games through this MCP server.
    Read this once before starting. Covers the game loop, scoring, parser errors,
    and recommended tool call order.
    """
    return HOW_TO_PLAY


@app.resource("guide://commands")
def guide_commands() -> str:
    """
    Quick-reference card for all standard Z-machine parser commands.
    Consult this when you are unsure what to type or when commands are being rejected.
    """
    return GUIDE_COMMANDS


@app.resource("game://info")
def game_info() -> dict:
    """
    Live metadata about the currently loaded game session.
    Returns game name, score, moves, inventory, location, and session status.
    Read this at any point to orient yourself without consuming a move.
    """
    if not _game_session.is_active():
        return {
            "active": False,
            "message": "No game is currently running.",
            "available_games_sample": list_available_games()[:20],
            "hint": "Call start_game(game_name) to begin.",
        }

    state = _game_session.current_state
    score    = state.score     if state else 0
    max_score = state.max_score if state else 0
    moves    = state.moves     if state else 0
    progress_pct = round((score / max_score) * 100) if max_score else 0

    return {
        "active": True,
        "game": _game_session.game_name,
        "score": score,
        "max_score": max_score,
        "progress": f"{score}/{max_score} ({progress_pct}%)",
        "moves": moves,
        "done": state.done if state else False,
        "inventory": state.inventory if state else [],
        "location": state.location if state else "Unknown",
        "started_at": _game_session.started_at.isoformat() if _game_session.started_at else None,
    }


# ── Tools ─────────────────────────────────────────────────────────────────────

@app.tool
def start_game(game_name: str = "zork1") -> dict:
    """
    Start a new game. Replaces any currently running session.

    Args:
        game_name: Name of the game to load (default: 'zork1').
                   Call list_games() to browse all options.

    Returns:
        observation, score, max_score, moves, done, reward,
        inventory, location, progress, game, message
    """
    try:
        state = _game_session.start_new_game(game_name)
        response = _format_state(state)
        response["game"] = game_name
        response["message"] = (
            f"'{game_name}' loaded. Max score: {state.max_score}. "
            "Read 'guide://how-to-play' if this is your first game."
        )
        return response
    except Exception as e:
        return {
            "error": f"Failed to start game: {str(e)}",
            "hint": "Call list_games() to see valid game names.",
        }


@app.tool
def action(command: str) -> dict:
    """
    Send a command to the game. Primary interaction tool — one call = one move.

    Args:
        command: Natural-language command (e.g. 'open mailbox', 'go north', 'take lamp').
                 See resource 'guide://commands' for a full reference.

    Returns:
        observation: Narrative result of your action
        score, max_score, moves, done, reward, inventory, location, progress
        message: Present when reward != 0 or the game ends
    """
    if not _game_session.is_active():
        return {"error": "No active game.", "hint": "Call start_game() first."}

    try:
        state = _game_session.env.step(command)  # type: ignore
        _game_session.current_state = state
        response = _format_state(state)

        if state.done:
            if state.score >= (state.max_score or 1):
                response["message"] = f"You WON! Final score: {state.score}/{state.max_score}."
            else:
                response["message"] = (
                    f"Game over. Score: {state.score}/{state.max_score}. "
                    "Call start_game() to try again."
                )
        elif state.reward > 0:
            response["message"] = f"+{state.reward} points. Score: {state.score}/{state.max_score}."
        elif state.reward < 0:
            response["message"] = f"{state.reward} points. Score: {state.score}/{state.max_score}."

        return response

    except Exception as e:
        return {
            "error": f"Action failed: {str(e)}",
            "hint": "Try a simpler command or call available_actions() for valid options.",
        }


@app.tool
def current_state() -> dict:
    """
    Return current game state without advancing the turn counter.

    Returns the last observation plus score, moves, inventory, and location.
    Use action('look') instead if you want a fresh room description from the game.

    Returns:
        observation, score, max_score, moves, done, reward,
        inventory, location, progress, game
    """
    if not _game_session.is_active():
        return {"error": "No active game.", "hint": "Call start_game() first."}

    if not _game_session.current_state:
        return {"error": "No state available. Try calling start_game() again."}

    response = _format_state(_game_session.current_state)
    response["game"] = _game_session.game_name
    return response


@app.tool
def available_actions(limit: int = 20) -> dict:
    """
    Return valid actions for the current game state.

    The engine analyses surroundings and inventory to produce this list.
    Not exhaustive — creative commands may also work — but a reliable starting point.

    Args:
        limit: Max actions to return (0 = all, default 20).

    Returns:
        actions: List of command strings valid right now
        count: Number returned
        total_available: Total before the limit was applied
    """
    if not _game_session.is_active():
        return {"error": "No active game.", "hint": "Call start_game() first."}

    try:
        all_actions = _game_session.env.get_valid_actions()  # type: ignore
        total = len(all_actions)
        actions = all_actions[:limit] if limit > 0 else all_actions
        return {"actions": actions, "count": len(actions), "total_available": total}
    except Exception as e:
        return {"error": str(e), "fallback": ["look", "inventory", "wait"]}


@app.tool
def look_around() -> dict:
    """
    Inspect objects in the current location via the internal Z-machine object tree.

    More thorough than the narrative 'look' command — reveals objects the story text
    may not explicitly mention.

    Returns:
        location_name: Current location name
        current_location_objects: Objects here (name, num, parent, child, sibling)
        object_count_here: Number of objects in this room
        total_world_objects: Total objects tracked across the whole game world
    """
    if not _game_session.is_active():
        return {"error": "No active game.", "hint": "Call start_game() first."}

    try:
        current_objects = _game_session.env.get_objects_in_location(None)  # type: ignore
        all_objects = _game_session.env.get_world_objects()  # type: ignore
        location_obj = _game_session.env.env.get_player_location()  # type: ignore
        location_name = str(location_obj) if location_obj else "Unknown"

        return {
            "location_name": location_name,
            "current_location_objects": current_objects,
            "object_count_here": len(current_objects),
            "total_world_objects": len(all_objects),
        }
    except Exception as e:
        return {"error": str(e)}


@app.tool
def recent_history(count: int = 5) -> dict:
    """
    Return recent action/observation pairs from this session.

    Args:
        count: Number of recent turns to return (0 = full history, default 5).

    Returns:
        recent_history: List of {turn, action, result} — oldest first, newest last
        showing: Number of entries returned
        total_moves: Total moves taken this session
    """
    if not _game_session.is_active():
        return {"error": "No active game.", "hint": "Call start_game() first."}

    try:
        history = _game_session.env.get_history()  # type: ignore
        total = len(history)
        recent = history[-count:] if count > 0 else history

        formatted = [
            {
                "turn": total - len(recent) + i + 1,
                "action": act,
                "result": obs[:200] + "..." if len(obs) > 200 else obs,
            }
            for i, (act, obs) in enumerate(recent)
        ]

        return {
            "recent_history": formatted,
            "showing": len(formatted),
            "total_moves": total,
        }
    except Exception as e:
        return {"error": str(e)}


@app.tool
def list_games(limit: int = 10) -> dict:
    """
    List available Z-machine games in the library.

    Args:
        limit: How many to return (0 = all, default 10).

    Returns:
        games: Game name strings — pass any of these to start_game()
        total_available: Total games in the library
        showing: How many are in this response
        recommended: Curated picks by category
    """
    all_games = list_available_games()
    games = all_games[:limit] if limit > 0 else all_games

    return {
        "games": games,
        "total_available": len(all_games),
        "showing": len(games),
        "recommended": {
            "classic_series": ["zork1", "zork2", "zork3"],
            "shorter_games":  ["detective", "advent"],
            "other_popular":  ["lgop", "hitchhiker"],
        },
    }


@app.tool
def game_vocabulary() -> dict:
    """
    Return all words the game's parser recognises, grouped by part of speech.

    Call this when commands are rejected to verify your words are in the dictionary.
    Note: parsers typically read only the first 6–9 characters of each word.

    Returns:
        total_words: Full vocabulary size
        verbs, nouns, adjectives, directions, prepositions, meta, special, unclassified
    """
    if not _game_session.is_active():
        return {"error": "No active game.", "hint": "Call start_game() first."}

    try:
        vocab = _game_session.env.get_game_dictionary()  # type: ignore

        return {
            "total_words":  len(vocab),
            "verbs":        [str(w) for w in vocab if w.is_verb],
            "nouns":        [str(w) for w in vocab if w.is_noun],
            "adjectives":   [str(w) for w in vocab if w.is_adj],
            "directions":   [str(w) for w in vocab if w.is_dir],
            "prepositions": [str(w) for w in vocab if w.is_prep],
            "meta":         [str(w) for w in vocab if w.is_meta],
            "special":      [str(w) for w in vocab if w.is_special],
            "unclassified": [str(w) for w in vocab if not any([
                w.is_verb, w.is_noun, w.is_adj, w.is_dir,
                w.is_prep, w.is_meta, w.is_special,
            ])],
        }
    except Exception as e:
        return {"error": str(e)}


@app.tool
def explore_map() -> dict:
    """
    Return a structural map of the game world from the internal object tree.

    Shows all locations and their contained objects — including unvisited ones.
    Useful for spatial planning and finding areas to explore.

    Returns:
        location_graph: Dict of {location_name: {num, objects[]}}
        locations_discovered: Number of locations in the graph
    """
    if not _game_session.is_active():
        return {"error": "No active game.", "hint": "Call start_game() first."}

    try:
        graph = _game_session.env.get_location_graph()  # type: ignore
        return {
            "location_graph": graph,
            "locations_discovered": len(graph),
        }
    except Exception as e:
        return {"error": str(e)}


@app.tool
def end_game() -> dict:
    """
    End the current session and release resources.

    Returns a final summary with score, moves, and performance percentage.
    Note: calling start_game() also replaces the session, so this is optional.
    """
    if not _game_session.is_active():
        return {"message": "No active game running."}

    game_name  = _game_session.game_name
    state      = _game_session.current_state
    final_score = state.score     if state else 0
    max_score   = state.max_score if state else 0
    total_moves = state.moves     if state else 0
    performance = f"{round((final_score / max_score) * 100)}%" if max_score else "N/A"

    _game_session.clear()

    return {
        "message":     f"Session ended: {game_name}",
        "final_score": final_score,
        "max_score":   max_score,
        "total_moves": total_moves,
        "performance": performance,
    }


# ── HTTP endpoints ─────────────────────────────────────────────────────────────

@app.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({
        "status": "healthy",
        "service": "jericho-text-adventure-server",
        "game_active": _game_session.is_active(),
        "current_game": _game_session.game_name if _game_session.is_active() else None,
    })


@app.custom_route("/status", methods=["GET"])
async def game_status(request: Request) -> JSONResponse:
    if not _game_session.is_active():
        return JSONResponse({"active": False, "message": "No game currently active"})

    state = _game_session.current_state
    return JSONResponse({
        "active":      True,
        "game":        _game_session.game_name,
        "score":       state.score      if state else 0,
        "max_score":   state.max_score  if state else 0,
        "moves":       state.moves      if state else 0,
        "done":        state.done       if state else False,
        "started_at":  _game_session.started_at.isoformat() if _game_session.started_at else None,
    })