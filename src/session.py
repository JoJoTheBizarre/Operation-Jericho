from .game_env import TextAdventureEnv, GameState
from typing import Optional
from datetime import datetime


class SingleGameSession:
    """Manages a single active game session."""

    def __init__(self):
        self.env: Optional[TextAdventureEnv] = None
        self.game_name: Optional[str] = None
        self.current_state: Optional[GameState] = None
        self.started_at: Optional[datetime] = None

    def is_active(self) -> bool:
        return self.env is not None

    def start_new_game(self, game_name: str) -> GameState:
        """Start a new game, replacing any existing session."""
        if self.env is not None:
            self.clear()
        self.env = TextAdventureEnv(game_name)
        self.game_name = game_name
        self.current_state = self.env.reset()
        self.started_at = datetime.now()
        return self.current_state

    def clear(self):
        self.env = None
        self.game_name = None
        self.current_state = None
        self.started_at = None


def _format_state(state: GameState) -> dict:
    """Format a GameState into a clean, agent-readable dictionary."""
    result = {
        "observation": state.observation,
        "score": state.score,
        "max_score": state.max_score,
        "moves": state.moves,
        "done": state.done,
        "reward": state.reward,
        "inventory": state.inventory,
        "location": state.location,
    }

    # Add a progress summary to help the agent track how well it's doing
    if state.max_score and state.max_score > 0:
        pct = round((state.score / state.max_score) * 100)
        result["progress"] = f"{state.score}/{state.max_score} ({pct}%)"
    else:
        result["progress"] = f"{state.score} points"

    return result