import os
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from jericho import FrotzEnv
from jericho.template_action_generator import TemplateActionGenerator

logger = logging.getLogger(__name__)


class GameError(Exception):
    """Base exception for game-related errors."""

    pass


class GameNotFoundError(GameError):
    """Raised when a game cannot be found."""

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
    reward: int
    inventory: list[str]
    location: str
    state_hash: Optional[str] = None


def get_default_games_dir() -> Path:
    """Get the default directory containing game files."""
    env_dir = os.getenv("ZORK_GAMES_DIR")
    if env_dir:
        path = Path(env_dir).expanduser().resolve()
        if path.exists():
            return path

    project_root = Path(__file__).parent.parent
    default_path = project_root / "games" / "z-machine-games" / "jericho-game-suite"
    return default_path


def discover_games(games_dir: Optional[Path] = None) -> dict[str, Path]:
    """Discover all available Z-machine games in the games directory."""
    if games_dir is None:
        games_dir = get_default_games_dir()

    games_dir = Path(games_dir)
    if not games_dir.exists():
        return {}

    games = {}
    for ext in ["*.z3", "*.z4", "*.z5", "*.z8"]:
        for game_path in games_dir.glob(ext):
            game_name = game_path.stem.lower()
            games[game_name] = game_path

    return dict(sorted(games.items()))


def list_available_games(games_dir: Optional[Path] = None) -> list[str]:
    """Return a sorted list of available game names."""
    return list(discover_games(games_dir).keys())


class TextAdventureEnv:
    """
    Wrapper around Jericho's FrotzEnv for text adventure games.

    This class provides a clean API that properly uses the official Jericho
    FrotzEnv methods according to the documentation at:
    https://jericho-py.readthedocs.io/

    Key Jericho API Methods Used:
    - reset() -> str (returns observation only in most versions)
    - step(action) -> (observation, score, done, info)
    - get_valid_actions() -> List[str]
    - get_inventory() -> List[ZObject]
    - get_player_location() -> ZObject
    - get_world_objects() -> List[ZObject]
    - get_dictionary() -> List[DictionaryWord]
    - get_walkthrough() -> List[str]
    - get_state() / set_state(state) for save/load
    """

    def __init__(self, game: str = "zork1", games_dir: Optional[str] = None):
        """
        Initialize the text adventure environment.

        Args:
            game: Either a game name (e.g., 'zork1') or path to .z3/.z4/.z5/.z8 file
            games_dir: Optional directory containing game files
        """
        if os.path.isfile(game):
            game_path = Path(game)
            self.game = game_path.stem
        else:
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
        self._history: list[tuple[str, str]] = []
        self._state_hashes: set[str] = set()
        self._template_generator: Optional[TemplateActionGenerator] = None

        # Detect Jericho version for compatibility
        try:
            import jericho

            self._jericho_version = getattr(jericho, "__version__", "unknown")
        except Exception:
            self._jericho_version = "unknown"

        logger.info(
            f"Loaded game: {self.game} (Jericho version: {self._jericho_version})"
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close the environment and release resources."""
        pass

    def __repr__(self) -> str:
        return f"TextAdventureEnv(game='{self.game}', path={self.game_path})"

    def reset(self) -> GameState:
        """
        Reset the game to the beginning.

        According to Jericho docs, reset() returns just the observation string.
        Some versions may return (observation, info) tuple.
        """
        try:
            result = self.env.reset()

            # Handle both API formats for compatibility
            if isinstance(result, tuple):
                observation, info = result
            else:
                # Standard Jericho API: reset() returns just observation string
                observation = result
                info = {}

        except Exception as e:
            raise GameLoadError(f"Failed to reset game: {e}") from e

        self._last_score = 0
        self._history = []
        self._state_hashes = set()

        try:
            initial_score = self.env.get_score()
        except Exception:
            initial_score = 0

        return self._make_game_state(
            observation=observation, score=initial_score, moves=0, done=False, reward=0
        )

    def step(self, action: str) -> GameState:
        """
        Take an action in the game.

        According to Jericho docs, step() returns:
        (observation, score, done, info)

        Where:
        - observation: str - The game's narrative response
        - score: int - Current game score
        - done: bool - Whether the game has ended
        - info: dict - Additional information
        """
        if not action or not isinstance(action, str):
            raise InvalidActionError(
                f"Action must be a non-empty string, got: {action!r}"
            )

        try:
            observation, score, done, info = self.env.step(action)
        except Exception as e:
            raise InvalidActionError(f"Invalid action '{action}': {e}") from e

        reward = score - self._last_score
        self._last_score = score

        self._history.append((action, observation))

        moves = info.get("moves", len(self._history))

        return self._make_game_state(
            observation=observation, score=score, moves=moves, done=done, reward=reward
        )

    def _make_game_state(
        self, observation: str, score: int, moves: int, done: bool, reward: int
    ) -> GameState:
        """Create a GameState from the environment info."""

        try:
            inventory = [str(obj) for obj in self.env.get_inventory()]
        except Exception as e:
            logger.debug(f"Could not get inventory: {e}")
            inventory = []

        try:
            location = str(self.env.get_player_location())
        except Exception as e:
            logger.debug(f"Could not get location: {e}")
            location = "Unknown"

        try:
            state_hash = self.env.get_world_state_hash()
            self._state_hashes.add(state_hash)
        except Exception as e:
            logger.debug(f"Could not get state hash: {e}")
            state_hash = None

        try:
            max_score = self.env.get_max_score()
        except Exception as e:
            logger.debug(f"Could not get max score: {e}")
            max_score = 0

        return GameState(
            observation=observation,
            score=score,
            max_score=max_score,
            moves=moves,
            done=done,
            reward=reward,
            inventory=inventory,
            location=location,
            state_hash=state_hash,
        )

    def get_history(self) -> list[tuple[str, str]]:
        """Get the history of (action, observation) pairs."""
        return self._history.copy()

    def get_valid_actions(self) -> list[str]:
        """
        Get a list of valid actions for the current state.

        Uses Jericho's get_valid_actions() which analyzes the current
        game state and returns likely valid commands.
        """
        try:
            return self.env.get_valid_actions()
        except Exception as e:
            logger.warning(
                f"Could not get valid actions: {e}. Returning minimal fallback."
            )
            # Return minimal safe actions as fallback
            return ["look", "inventory", "wait"]

    def save_state(self) -> Any:
        """
        Save the current game state.

        Returns an opaque state object that can be restored with load_state().
        """
        try:
            return self.env.get_state()
        except Exception as e:
            raise StateError(f"Failed to save game state: {e}") from e

    def load_state(self, state: Any) -> None:
        """
        Load a previously saved game state.

        Args:
            state: State object returned by save_state()
        """
        try:
            self.env.set_state(state)
        except Exception as e:
            raise StateError(f"Failed to load game state: {e}") from e

    def get_walkthrough(self) -> list[str]:
        """
        Get the walkthrough for the game.

        Note: Walkthroughs are only available for supported games.
        To replay a walkthrough properly, reset with use_walkthrough_seed=True.
        """
        try:
            return self.env.get_walkthrough()
        except Exception as e:
            raise GameError(f"Walkthrough not available: {e}") from e

    def get_world_objects(self) -> list[dict]:
        """
        Get all objects in the game world with their relationships.

        Note: Object tree support varies by game. Some games may return
        empty or incomplete object information.
        """
        try:
            objects = self.env.get_world_objects()
            return [self._zobject_to_dict(obj) for obj in objects]
        except Exception as e:
            logger.warning(f"Object tree not available: {e}")
            return []

    def _zobject_to_dict(self, obj) -> dict:
        """Convert a ZObject to a dictionary."""
        try:
            return {
                "num": obj.num,
                "name": str(obj),
                "parent": obj.parent if hasattr(obj, "parent") else None,
                "child": obj.child if hasattr(obj, "child") else None,
                "sibling": obj.sibling if hasattr(obj, "sibling") else None,
                "attributes": self._get_object_attributes(obj),
            }
        except Exception:
            return {"num": getattr(obj, "num", 0), "name": str(obj)}

    def _get_object_attributes(self, obj) -> list[str]:
        """Extract attribute flags from a ZObject."""
        attributes = []
        attribute_names = [
            "is_container",
            "is_open",
            "is_locked",
            "is_takeable",
            "is_wearable",
            "is_worn",
            "is_edible",
            "is_drinkable",
        ]
        for attr in attribute_names:
            try:
                if hasattr(obj, attr) and getattr(obj, attr):
                    attributes.append(attr.replace("is_", ""))
            except Exception:
                pass
        return attributes

    def get_objects_in_location(
        self, location_name: Optional[str] = None
    ) -> list[dict]:
        """
        Get all objects in a specific location or current location.

        Args:
            location_name: Name of location, or None for current location
        """
        try:
            if location_name is None:
                location = self.env.get_player_location()
            else:
                all_objects = self.env.get_world_objects()
                location = next(
                    (
                        obj
                        for obj in all_objects
                        if str(obj).lower() == location_name.lower()
                    ),
                    None,
                )
                if not location:
                    return []

            objects = []
            if hasattr(location, "child"):
                child = location.child #type: ignore
                while child:
                    objects.append(self._zobject_to_dict(child))
                    child = child.sibling if hasattr(child, "sibling") else None

            return objects
        except Exception as e:
            logger.warning(f"Could not get objects in location: {e}")
            return []

    def get_world_state_hash(self) -> Optional[str]:
        """Get MD5 hash of current world state."""
        try:
            return self.env.get_world_state_hash()
        except Exception as e:
            logger.debug(f"Could not get world state hash: {e}")
            return None

    def is_state_visited(self, state_hash: Optional[str] = None) -> bool:
        """Check if a state has been visited before."""
        if state_hash is None:
            state_hash = self.get_world_state_hash()
        return state_hash in self._state_hashes if state_hash else False

    def get_visited_states_count(self) -> int:
        """Get the number of unique states visited."""
        return len(self._state_hashes)

    def get_game_dictionary(self) -> list[str]:
        """
        Get all words recognized by the game parser.

        Returns list of vocabulary words. Note that most games
        recognize only the first 6 or 9 characters of each word.
        """
        try:
            return [str(word) for word in self.env.get_dictionary()]
        except Exception as e:
            logger.warning(f"Could not get game dictionary: {e}")
            return []

    def get_game_info(self) -> dict:
        """Get comprehensive game metadata."""
        info = {
            "game_name": self.game,
            "game_path": str(self.game_path),
            "jericho_version": self._jericho_version,
        }

        try:
            info["max_score"] = self.env.get_max_score()
        except Exception:
            info["max_score"] = 0

        try:
            walkthrough = self.get_walkthrough()
            info["walkthrough_length"] = len(walkthrough)
            info["has_walkthrough"] = True
        except Exception:
            info["walkthrough_length"] = 0
            info["has_walkthrough"] = False

        return info

    def get_location_graph(self) -> dict:
        """
        Get a graph of all discovered locations and their connections.

        Note: This is a best-effort implementation. Not all games
        provide complete location information.
        """
        graph = {}

        try:
            all_objects = self.env.get_world_objects()
            locations = [obj for obj in all_objects if self._is_location(obj)]

            for loc in locations:
                loc_name = str(loc)
                graph[loc_name] = {
                    "num": loc.num,
                    "objects": [str(child) for child in self._get_children(loc)],
                }
        except Exception as e:
            logger.warning(f"Could not build location graph: {e}")

        return graph

    def _is_location(self, obj) -> bool:
        """Check if an object is a location/room."""
        try:
            # Locations typically have children but no parent (or parent is 0)
            return hasattr(obj, "child") and obj.parent in [None, 0]
        except Exception:
            return False

    def _get_children(self, obj) -> list:
        """Get all child objects of a ZObject."""
        children = []
        try:
            child = obj.child if hasattr(obj, "child") else None
            while child:
                children.append(child)
                child = child.sibling if hasattr(child, "sibling") else None
        except Exception:
            pass
        return children

    def get_object_details(self, object_name: str) -> Optional[dict]:
        """Get detailed information about a specific object."""
        try:
            all_objects = self.env.get_world_objects()
            obj = next(
                (o for o in all_objects if str(o).lower() == object_name.lower()), None
            )

            if obj:
                return self._zobject_to_dict(obj)
        except Exception as e:
            logger.warning(f"Could not get object details: {e}")
        return None


ZorkEnvironment = TextAdventureEnv
