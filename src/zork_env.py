from jericho import FrotzEnv
from dataclasses import dataclass
from typing import Optional, Any
from pathlib import Path
import os


class GameError(Exception):
    """Base exception for game-related errors."""

    pass


class GameNotFoundError(GameError):
    """Raised when a game file cannot be found."""

    pass


class GameLoadError(GameError):
    """Raised when a game fails to load."""

    pass


class InvalidActionError(GameError):
    """Raised when an invalid action is attempted."""

    pass


class StateError(GameError):
    """Raised when state save/load operations fail."""

    pass


@dataclass
class GameState:
    """Represents the current state of the game."""

    observation: str
    score: int
    max_score: int
    moves: int
    done: bool
    reward: int  # Points gained from last action
    inventory: list[str]
    location: str


def get_default_games_dir() -> Path:
    """Get the default directory containing game files.

    Checks ZORK_GAMES_DIR environment variable first.
    """
    env_dir = os.getenv("ZORK_GAMES_DIR")
    if env_dir:
        path = Path(env_dir).expanduser().resolve()
        if path.exists():
            return path
        # Fall through with warning

    project_root = Path(__file__).parent.parent
    default_path = project_root / "games" / "z-machine-games" / "jericho-game-suite"
    return default_path


def discover_games(games_dir: Optional[Path] = None) -> dict[str, Path]:
    """
    Discover all available Z-machine games in the games directory.

    Args:
        games_dir: Directory to search for games (default: jericho-game-suite)

    Returns:
        Dictionary mapping game name (without extension) to full path
    """
    if games_dir is None:
        games_dir = get_default_games_dir()

    games_dir = Path(games_dir)
    if not games_dir.exists():
        return {}

    games = {}
    # Find all Z-machine game files (.z3, .z4, .z5, .z8)
    for ext in ["*.z3", "*.z4", "*.z5", "*.z8"]:
        for game_path in games_dir.glob(ext):
            # Use stem (filename without extension) as game name
            game_name = game_path.stem.lower()
            games[game_name] = game_path

    return dict(sorted(games.items()))


def list_available_games(games_dir: Optional[Path] = None) -> list[str]:
    """Return a sorted list of available game names."""
    return list(discover_games(games_dir).keys())


class TextAdventureEnv:
    """Wrapper around Jericho's FrotzEnv for text adventure games."""

    def __init__(self, game: str = "zork1", games_dir: Optional[str] = None):
        """
        Initialize the text adventure environment.

        Args:
            game: Game name (e.g., 'zork1', 'advent', 'enchanter')
                  Can also be a full path to a .z* file
            games_dir: Directory containing game files (optional)
        """
        # Check if game is a full path
        if os.path.isfile(game):
            game_path = Path(game)
            self.game = game_path.stem
        else:
            # Look up game by name
            games_path = Path(games_dir) if games_dir else None
            available_games = discover_games(games_path)

            if not available_games:
                raise GameNotFoundError(
                    f"No games found in directory: {games_path or get_default_games_dir()}"
                )

            if game.lower() not in available_games:
                available = list(available_games.keys())[:20]
                raise GameNotFoundError(
                    f"Unknown game: {game}. "
                    f"Available: {', '.join(available)}... "
                    f"({len(available_games)} total)"
                )

            game_path = available_games[game.lower()]
            self.game = game.lower()

        try:
            self.env = FrotzEnv(str(game_path))
        except Exception as e:
            raise GameLoadError(f"Failed to load game '{game_path}': {e}") from e

        self.game_path = game_path
        self._last_score = 0
        self._history: list[tuple[str, str]] = []  # (action, observation) pairs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close the environment and release resources."""
        # FrotzEnv doesn't have a close method, but we keep this for consistency
        pass

    def __repr__(self) -> str:
        return f"TextAdventureEnv(game='{self.game}', path={self.game_path})"

    def reset(self) -> GameState:
        """Reset the game to the beginning."""
        try:
            observation, info = self.env.reset()
        except Exception as e:
            raise GameLoadError(f"Failed to reset game: {e}") from e

        self._last_score = 0
        self._history = []
        return self._make_game_state(observation, info, done=False, reward=0)

    def step(self, action: str) -> GameState:
        """
        Take an action in the game.

        Args:
            action: The text command to execute (e.g., "go north", "take lamp")

        Returns:
            GameState with the result of the action
        """
        if not action or not isinstance(action, str):
            raise InvalidActionError(
                f"Action must be a non-empty string, got: {action!r}"
            )

        try:
            observation, reward, done, info = self.env.step(action)
        except Exception as e:
            raise InvalidActionError(f"Invalid action '{action}': {e}") from e

        # Track reward as score change
        current_score = info.get("score", 0)
        reward = current_score - self._last_score
        self._last_score = current_score

        # Record history
        self._history.append((action, observation))

        return self._make_game_state(observation, info, done, reward)

    def _make_game_state(
        self, observation: str, info: dict, done: bool, reward: int
    ) -> GameState:
        """Create a GameState from the environment info."""
        # Try to get inventory and location (may fail without spacy)
        try:
            inventory = [str(obj) for obj in self.env.get_inventory()]
        except Exception:
            inventory = []

        try:
            location = str(self.env.get_player_location())
        except Exception:
            location = "Unknown"

        return GameState(
            observation=observation,
            score=info.get("score", 0),
            max_score=self.env.get_max_score(),
            moves=info.get("moves", 0),
            done=done,
            reward=reward,
            inventory=inventory,
            location=location,
        )

    def get_history(self) -> list[tuple[str, str]]:
        """Get the history of (action, observation) pairs."""
        return self._history.copy()

    def get_valid_actions(self) -> list[str]:
        """
        Get a list of valid actions for the current state.
        Note: This requires spacy to be properly installed.
        """
        try:
            return self.env.get_valid_actions()
        except Exception:
            # Return common actions if spacy isn't available
            return [
                "north",
                "south",
                "east",
                "west",
                "up",
                "down",
                "look",
                "inventory",
                "take all",
                "open mailbox",
                "read",
            ]

    def save_state(self) -> Any:
        """Save the current game state."""
        try:
            return self.env.get_state()
        except Exception as e:
            raise StateError(f"Failed to save game state: {e}") from e

    def load_state(self, state: Any) -> None:
        """Load a previously saved game state."""
        try:
            self.env.set_state(state)
        except Exception as e:
            raise StateError(f"Failed to load game state: {e}") from e

    def get_walkthrough(self) -> list[str]:
        """Get the walkthrough for the game (for debugging/comparison only)."""
        try:
            return self.env.get_walkthrough()
        except Exception as e:
            raise GameError(f"Failed to get walkthrough: {e}") from e


# Alias for backwards compatibility
ZorkEnvironment = TextAdventureEnv


# Example usage
if __name__ == "__main__":
    import sys

    # List available games
    games = list_available_games()
    print(f"Available games ({len(games)} total):")
    print(f"  {', '.join(games[:15])}...")
    print()

    # Use command line arg or default to zork1
    game = sys.argv[1] if len(sys.argv) > 1 else "zork1"

    env = TextAdventureEnv(game)
    state = env.reset()

    print(f"=== {env.game.upper()} ===")
    print(f"Max Score: {state.max_score}")
    print(f"\n{state.observation}")
    print(f"\nValid actions: {env.get_valid_actions()[:10]}...")

    # Try a few actions
    for action in ["look", "inventory"]:
        print(f"\n> {action}")
        state = env.step(action)
        print(state.observation)
        print(f"Score: {state.score}, Reward: {state.reward}")
