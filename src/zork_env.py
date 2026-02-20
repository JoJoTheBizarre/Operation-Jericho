import os
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from jericho import FrotzEnv, DictionaryWord
from jericho.template_action_generator import TemplateActionGenerator
from .exceptions import GameError, GameNotFoundError, GameLoadError, InvalidActionError, StateError

logger = logging.getLogger(__name__)


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
    project_root = Path(__file__).parent.parent
    default_path = project_root / "games" / "jericho-game-suite"
    print(default_path)
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

    Provides a clean, stable API over the Jericho interface. All Jericho
    exceptions are caught and re-raised as domain-specific errors.

    Key Jericho API Methods Used:
    - reset() -> (observation, info) or observation
    - step(action) -> (observation, score, done, info)
    - get_valid_actions() -> List[str]
    - get_inventory() -> List[ZObject]
    - get_player_location() -> ZObject
    - get_world_objects() -> List[ZObject]
    - get_dictionary() -> List[DictionaryWord]
    - get_walkthrough() -> List[str]
    - get_state() / set_state(state)
    - get_world_state_hash() -> str
    - get_max_score() -> int
    - get_score() -> int
    """

    def __init__(self, game: str = "zork1", games_dir: Optional[str] = None):
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
                    f"Unknown game: '{game}'. "
                    f"Available: {', '.join(available)}... ({len(available_games)} total)"
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

        try:
            import jericho
            self._jericho_version = getattr(jericho, "__version__", "unknown")
        except Exception:
            self._jericho_version = "unknown"

        logger.info(f"Loaded game: {self.game} (Jericho version: {self._jericho_version})")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        pass

    def __repr__(self) -> str:
        return f"TextAdventureEnv(game='{self.game}', path={self.game_path})"

    def reset(self) -> GameState:
        """Reset the game to the beginning."""
        try:
            result = self.env.reset()
            if isinstance(result, tuple):
                observation, info = result
            else:
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

        Returns a GameState with the updated observation, score, done flag,
        and reward (score delta since last step).
        """
        if not action or not isinstance(action, str):
            raise InvalidActionError(f"Action must be a non-empty string, got: {action!r}")

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
        """Build a GameState by querying the environment for supplementary data."""
        try:
            inventory = [str(obj) for obj in self.env.get_inventory()]
        except Exception as e:
            logger.debug(f"Could not get inventory: {e}")
            inventory = []

        try:
            location_obj = self.env.get_player_location()
            # ZObject's string representation is its name
            location = str(location_obj) if location_obj else "Unknown"
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
        """Return a copy of the (action, observation) history."""
        return self._history.copy()

    def get_valid_actions(self) -> list[str]:
        """Get valid actions for the current state via Jericho's action analysis."""
        try:
            return self.env.get_valid_actions()
        except Exception as e:
            logger.warning(f"Could not get valid actions: {e}. Returning minimal fallback.")
            return ["look", "inventory", "wait"]

    def save_state(self) -> Any:
        """Save current game state. Returns an opaque tuple for later restoration."""
        try:
            return self.env.get_state()
        except Exception as e:
            raise StateError(f"Failed to save game state: {e}") from e

    def load_state(self, state: Any) -> None:
        """Restore a previously saved game state."""
        try:
            self.env.set_state(state)
        except Exception as e:
            raise StateError(f"Failed to load game state: {e}") from e

    def get_walkthrough(self) -> list[str]:
        """Get the walkthrough action sequence. Only available for supported games."""
        try:
            return self.env.get_walkthrough()
        except Exception as e:
            raise GameError(f"Walkthrough not available: {e}") from e

    def get_world_objects(self) -> list[dict]:
        """Return all game-world objects as dictionaries."""
        try:
            objects = self.env.get_world_objects()
            return [self._zobject_to_dict(obj) for obj in objects]
        except Exception as e:
            logger.warning(f"Object tree not available: {e}")
            return []

    def _zobject_to_dict(self, obj) -> dict:
        """Convert a ZObject to a serialisable dictionary."""
        try:
            return {
                "num": obj.num,
                "name": str(obj),
                "parent": getattr(obj, "parent", None),
                "child": getattr(obj, "child", None),
                "sibling": getattr(obj, "sibling", None),
                "attributes": list(obj.attr) if hasattr(obj, "attr") else [],
            }
        except Exception:
            return {"num": getattr(obj, "num", 0), "name": str(obj)}

    def get_objects_in_location(self, location_name: Optional[str] = None) -> list[dict]:
        """
        Get objects in the current or specified location.

        Walks the ZObject child/sibling chain starting from the location object.
        If location_name is None, uses the player's current location.
        """
        try:
            if location_name is None:
                location_obj = self.env.get_player_location()
            else:
                all_objects = self.env.get_world_objects()
                location_obj = next(
                    (obj for obj in all_objects
                     if str(obj).lower() == location_name.lower()),
                    None,
                )

            if location_obj is None:
                return []

            # Walk child → sibling chain to enumerate direct children
            result = []
            try:
                child_num = location_obj.child
                if child_num:
                    child = self.env.get_object(child_num)
                    while child is not None:
                        result.append(self._zobject_to_dict(child))
                        sibling_num = getattr(child, "sibling", None)
                        child = self.env.get_object(sibling_num) if sibling_num else None
            except Exception as e:
                logger.debug(f"Error walking child/sibling chain: {e}")

            return result

        except Exception as e:
            logger.warning(f"Could not get objects in location: {e}")
            return []

    def get_world_state_hash(self) -> Optional[str]:
        """Get MD5 hash of the current clean world object tree."""
        try:
            return self.env.get_world_state_hash()
        except Exception as e:
            logger.debug(f"Could not get world state hash: {e}")
            return None

    def is_state_visited(self, state_hash: Optional[str] = None) -> bool:
        """Check if this game state has been reached before in this session."""
        if state_hash is None:
            state_hash = self.get_world_state_hash()
        return state_hash in self._state_hashes if state_hash else False

    def get_visited_states_count(self) -> int:
        """Number of unique game states visited this session."""
        return len(self._state_hashes)

    def get_game_dictionary(self) -> list[DictionaryWord]:
        """Return all DictionaryWord objects recognised by this game's parser."""
        try:
            return self.env.get_dictionary()
        except Exception as e:
            logger.warning(f"Could not get game dictionary: {e}")
            return []

    def get_game_info(self) -> dict:
        """Return comprehensive metadata about the loaded game."""
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
        Build a structural map of the game world from the object tree.

        Locations are identified as objects whose parent is 0 (top-level)
        or that have the structure of a room (no meaningful parent).
        Returns a dict of location_name → {num, objects[]}.
        """
        graph = {}
        try:
            all_objects = self.env.get_world_objects()
            for obj in all_objects:
                if self._is_location(obj):
                    loc_name = str(obj)
                    children = self._get_children_from_raw(obj, all_objects)
                    graph[loc_name] = {
                        "num": obj.num,
                        "objects": [str(c) for c in children],
                    }
        except Exception as e:
            logger.warning(f"Could not build location graph: {e}")
        return graph

    def _is_location(self, obj) -> bool:
        """Heuristic: objects with no meaningful parent are likely room objects."""
        try:
            return hasattr(obj, "child") and obj.parent in (None, 0)
        except Exception:
            return False

    def _get_children_from_raw(self, obj, all_objects) -> list:
        """Walk child/sibling relationships to return direct children."""
        children = []
        try:
            obj_map = {o.num: o for o in all_objects if hasattr(o, "num")}
            child_num = getattr(obj, "child", None)
            while child_num:
                child = obj_map.get(child_num)
                if child is None:
                    break
                children.append(child)
                child_num = getattr(child, "sibling", None)
        except Exception:
            pass
        return children

    def get_object_details(self, object_name: str) -> Optional[dict]:
        """Get detailed information about a specific object by name."""
        try:
            all_objects = self.env.get_world_objects()
            obj = next(
                (o for o in all_objects if str(o).lower() == object_name.lower()), None
            )
            return self._zobject_to_dict(obj) if obj else None
        except Exception as e:
            logger.warning(f"Could not get object details: {e}")
            return None


ZorkEnvironment = TextAdventureEnv