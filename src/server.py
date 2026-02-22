from fastmcp import FastMCP
from starlette.responses import JSONResponse
from starlette.requests import Request

from .game_env import list_available_games
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

_MILESTONES = [25, 50, 75, 100]
_reached_milestones: set[int] = set()


def _check_milestones(score: int, max_score: int) -> list[int]:
    """Return any newly crossed milestone percentages."""
    if not max_score:
        return []
    current_pct = (score / max_score) * 100
    newly_reached = []
    for m in _MILESTONES:
        if current_pct >= m and m not in _reached_milestones:
            _reached_milestones.add(m)
            newly_reached.append(m)
    return newly_reached


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


@app.tool
def start_game(game_name: str = "zork1") -> dict:
    """
    Start a new game. Replaces any currently running session.

    When to call this:
        - At the very beginning, before any other tool is used.
        - When you want to switch to a different game entirely.
        - After a game over to try again from scratch.
        - If the session has entered a broken or unrecoverable state.

    How to use it:
        Pass a game_name string taken from list_games(). If you are unsure which game
        to load, call list_games() first to browse what is available and check the
        recommended picks. Calling this while a game is already running will silently
        discard the current session — there is no confirmation step.

    Args:
        game_name: Name of the game to load (default: 'zork1').
                   Call list_games() to browse all options.

    Returns:
        observation, score, max_score, moves, done, reward,
        inventory, location, progress, game, message
    """
    global _reached_milestones
    _reached_milestones = set()

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

    When to call this:
        - Every time you want to do something in the game world — moving, taking items,
          talking, examining objects, or any other in-game interaction.
        - After reviewing available_actions() or look_around() and deciding on your next step.
        - This is the only tool that advances the turn counter, so use it deliberately.

    How to use it:
        Pass a short, plain-English command using verb-noun structure (e.g. 'take lamp',
        'go north', 'open mailbox'). Read the returned observation carefully — it contains
        everything the game engine wants you to know about the result. Check revisited_state
        to detect loops and milestones_reached to track overall progress. If reward is
        non-zero, the message field will explain what changed in your score.

    Args:
        command: Natural-language command (e.g. 'open mailbox', 'go north', 'take lamp').
                 See resource 'guide://commands' for a full reference.

    Returns:
        observation: Narrative result of your action
        score, max_score, moves, done, reward, inventory, location, progress
        revisited_state: True if you have returned to a previously seen game state (loop warning)
        milestones_reached: List of completion % milestones newly crossed this turn (e.g. [25, 50])
        message: Present when reward != 0, the game ends, or a milestone is crossed
    """
    if not _game_session.is_active():
        return {"error": "No active game.", "hint": "Call start_game() first."}

    try:
        state = _game_session.env.step(command)  # type: ignore
    except Exception as e:
        return {
            "error": f"Engine error: {str(e)}",
            "hint": "This is an unexpected engine failure. Try calling start_game() to reset.",
        }

    _game_session.current_state = state
    response = _format_state(state)

    state_hash = state.state_hash
    revisited = _game_session.env.is_state_visited(state_hash) if state_hash else False #type: ignore
    response["revisited_state"] = revisited

    newly_crossed = _check_milestones(state.score, state.max_score)
    response["milestones_reached"] = newly_crossed

    messages = []

    if state.done:
        if state.score >= (state.max_score or 1):
            messages.append(f"You WON! Final score: {state.score}/{state.max_score}.")
        else:
            messages.append(
                f"Game over. Score: {state.score}/{state.max_score}. "
                "Call start_game() to try again."
            )
    elif state.reward > 0:
        messages.append(f"+{state.reward} points. Score: {state.score}/{state.max_score}.")
    elif state.reward < 0:
        messages.append(f"{state.reward} points. Score: {state.score}/{state.max_score}.")

    if revisited:
        messages.append(
            "⚠ You have returned to a previously visited state — "
            "you may be going in circles. Consider a different approach."
        )

    for m in newly_crossed:
        messages.append(f"🏆 Milestone reached: {m}% completion!")

    if messages:
        response["message"] = " | ".join(messages)

    return response


@app.tool
def current_state() -> dict:
    """
    Return current game state without advancing the turn counter.

    When to call this:
        - When you need to re-read the last observation without spending a move.
        - After a long reasoning step where you may have lost track of score, inventory,
          or location and need to reorient quickly.
        - To confirm the session is active and check basic stats before taking action.

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
def available_actions() -> dict:
    """
    Return all valid actions for the current game state.

    When to call this:
        - At the start of each turn when you are unsure what to do next.
        - After entering a new location to quickly survey your options.
        - When a command is rejected and you want to see what the parser will actually accept.
        - Any time you feel stuck or want to avoid wasting moves on invalid commands.

    How to use it:
        Call this before committing to an action. Scan the returned list for verbs and
        objects relevant to your current goal, then pass your chosen command to action().
        The list is not exhaustive — creative or composite commands may still work — but
        it is the safest starting point for deciding your next move.

    Returns:
        actions: All command strings valid in the current state
        count: Number of actions returned
    """
    if not _game_session.is_active():
        return {"error": "No active game.", "hint": "Call start_game() first."}

    try:
        all_actions = _game_session.env.get_valid_actions()  # type: ignore
        return {"actions": all_actions, "count": len(all_actions)}
    except Exception as e:
        return {"error": str(e), "fallback": ["look", "inventory", "wait"]}


@app.tool
def look_around() -> dict:
    """
    Inspect objects in the current location via the internal Z-machine object tree.

    When to call this:
        - When the narrative description of a room feels vague or incomplete and you
          suspect there are interactable objects the story text did not mention.
        - Before deciding what to pick up or examine, to get a reliable object inventory
          for the current room rather than relying on narrative alone.
        - When you want structured object data (numbers, parent/child relationships)
          rather than prose descriptions.

    How to use it:
        this tool gives you the raw object tree.
        Cross-reference both to build a complete picture of what is in the room and
        what can be interacted with. Object names here map directly to words the parser
        will accept in action() commands.

    Returns:
        location_name: Current location name
        current_location_objects: Objects here (name, num, parent, child, sibling)
        object_count_here: Number of objects in this room
    """
    if not _game_session.is_active():
        return {"error": "No active game.", "hint": "Call start_game() first."}

    try:
        current_objects = _game_session.env.get_objects_in_location(None)  # type: ignore
        location_obj = _game_session.env.env.get_player_location()  # type: ignore
        location_name = str(location_obj) if location_obj else "Unknown"

        return {
            "location_name": location_name,
            "current_location_objects": current_objects,
            "object_count_here": len(current_objects),
        }
    except Exception as e:
        return {"error": str(e)}


@app.tool
def recent_history(count: int = 5) -> dict:
    """
    Return recent action/observation pairs from this session.

    When to call this:
        - When you have lost track of what you have already tried in a location and
          want to avoid repeating failed commands.
        - After a long chain of reasoning to reconstruct what happened in recent turns.
        - When revisited_state fires and you need to trace back how you arrived at
          the current state to figure out where you diverged.

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

    When to call this:
        - Before calling start_game() if you are unsure what game name to pass.
        - When the user asks what games are available or wants a recommendation.
        - If start_game() returns an error about an unknown game name, call this
          to verify the correct spelling of the game you intended to load.

    How to use it:
        Browse the returned games list and pick a name to pass directly to start_game().
        Check the recommended field for curated suggestions grouped by category —
        classic_series for the Zork trilogy, shorter_games for quicker completions,
        and other_popular for well-known titles. Pass limit=0 to see the full library.

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

    When to call this:
        - When a command is rejected by the parser and you are unsure if the word
          you used is in the game's vocabulary at all.
        - Before trying creative or unusual commands, to verify the parser will
          recognise the key verb or noun you intend to use.
        - When exploring a new game for the first time to understand what kinds
          of actions and objects the parser supports.

    How to use it:
        Look up your intended verb in the verbs list and your target object in the
        nouns list. If either is missing, the parser will reject the command regardless
        of phrasing. Note that Z-machine parsers typically read only the first 6–9
        characters of each word, so 'examine' and 'examinee' are treated identically.
        Use the directions list to confirm valid movement words for this specific game.

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
def end_game() -> dict:
    """
    End the current session and release resources.

    When to call this:
        - When you have finished playing and want to cleanly shut down the session.
        - When the user explicitly asks to quit or stop the game.
        - After a game over or win condition, if you do not intend to start a new game
          immediately — though calling start_game() directly also replaces the session.

    How to use it:
        Simply call it with no arguments. It returns a final summary of your performance
        including score, move count, and a percentage rating. No confirmation is required
        and the action is immediate — the session cannot be resumed after this call.

    Returns:
        message: Confirmation of which game session ended
        final_score, max_score, total_moves, performance
    """
    global _reached_milestones

    if not _game_session.is_active():
        return {"message": "No active game running."}

    game_name   = _game_session.game_name
    state       = _game_session.current_state
    final_score = state.score     if state else 0
    max_score   = state.max_score if state else 0
    total_moves = state.moves     if state else 0
    performance = f"{round((final_score / max_score) * 100)}%" if max_score else "N/A"

    _game_session.clear()
    _reached_milestones = set()

    return {
        "message":     f"Session ended: {game_name}",
        "final_score": final_score,
        "max_score":   max_score,
        "total_moves": total_moves,
        "performance": performance,
    }


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