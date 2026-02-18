import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from jericho import FrotzEnv
from jericho.template_action_generator import TemplateActionGenerator


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
    """Wrapper around Jericho's FrotzEnv for text adventure games."""

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
        """Reset the game to the beginning."""
        try:
            observation, info = self.env.reset()
        except Exception as e:
            raise GameLoadError(f"Failed to reset game: {e}") from e

        self._last_score = 0
        self._history = []
        self._state_hashes = set()
        return self._make_game_state(observation, info, done=False, reward=0)

    def step(self, action: str) -> GameState:
        """Take an action in the game."""
        if not action or not isinstance(action, str):
            raise InvalidActionError(
                f"Action must be a non-empty string, got: {action!r}"
            )

        try:
            observation, reward, done, info = self.env.step(action)
        except Exception as e:
            raise InvalidActionError(f"Invalid action '{action}': {e}") from e

        current_score = info.get("score", 0)
        reward = current_score - self._last_score
        self._last_score = current_score

        self._history.append((action, observation))

        return self._make_game_state(observation, info, done, reward)

    def _make_game_state(
        self, observation: str, info: dict, done: bool, reward: int
    ) -> GameState:
        """Create a GameState from the environment info."""
        try:
            inventory = [str(obj) for obj in self.env.get_inventory()]
        except Exception:
            inventory = []

        try:
            location = str(self.env.get_player_location())
        except Exception:
            location = "Unknown"

        try:
            state_hash = self.env.get_world_state_hash()
            self._state_hashes.add(state_hash)
        except Exception:
            state_hash = None

        return GameState(
            observation=observation,
            score=info.get("score", 0),
            max_score=self.env.get_max_score(),
            moves=info.get("moves", 0),
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
        """Get a list of valid actions for the current state."""
        try:
            return self.env.get_valid_actions()
        except Exception:
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
        """Get the walkthrough for the game."""
        try:
            return self.env.get_walkthrough()
        except Exception as e:
            raise GameError(f"Failed to get walkthrough: {e}") from e

    def get_world_objects(self) -> list[dict]:
        """Get all objects in the game world with their relationships."""
        try:
            objects = self.env.get_world_objects()
            return [self._zobject_to_dict(obj) for obj in objects]
        except Exception:
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
        """Get all objects in a specific location or current location."""
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
                child = location.child
                while child:
                    objects.append(self._zobject_to_dict(child))
                    child = child.sibling if hasattr(child, "sibling") else None

            return objects
        except Exception:
            return []

    def get_world_state_hash(self) -> Optional[str]:
        """Get MD5 hash of current world state."""
        try:
            return self.env.get_world_state_hash()
        except Exception:
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
        """Get all words recognized by the game parser."""
        try:
            return list(self.env.get_dictionary())
        except Exception:
            return []

    def get_game_info(self) -> dict:
        """Get comprehensive game metadata."""
        info = {
            "game_name": self.game,
            "game_path": str(self.game_path),
            "max_score": self.env.get_max_score(),
        }

        try:
            if hasattr(self.env, "bindings"):
                bindings = self.env.bindings
                info.update(
                    {
                        "rom_path": getattr(bindings, "rom_path", None),
                        "seed": getattr(bindings, "seed", None),
                        "max_word_length": getattr(bindings, "max_word_length", None),
                    }
                )
        except Exception:
            pass

        try:
            walkthrough = self.get_walkthrough()
            info["walkthrough_length"] = len(walkthrough)
            info["has_walkthrough"] = True
        except Exception:
            info["walkthrough_length"] = 0
            info["has_walkthrough"] = False

        return info

    def get_action_templates(self) -> list[str]:
        """Get action templates supported by the game."""
        if self._template_generator is None:
            try:
                self._template_generator = TemplateActionGenerator(self.env)
            except Exception:
                return []

        try:
            return self._template_generator.templates
        except Exception:
            return []

    def generate_template_actions(
        self, filter_by_type: Optional[list[str]] = None
    ) -> list[str]:
        """Generate valid actions using templates and current game state."""
        if self._template_generator is None:
            try:
                self._template_generator = TemplateActionGenerator(self.env)
            except Exception:
                return []

        try:
            actions = self._template_generator.generate_actions(self.env)

            if filter_by_type:
                filtered = []
                for action in actions:
                    action_lower = action.lower()
                    if any(t in action_lower for t in filter_by_type):
                        filtered.append(action)
                return filtered

            return actions
        except Exception:
            return []

    def get_valid_actions_advanced(
        self,
        use_templates: bool = False,
        filter_type: Optional[list[str]] = None,
        max_actions: int = 0,
    ) -> list[str]:
        """Get valid actions with advanced filtering options."""
        if use_templates:
            actions = self.generate_template_actions(filter_type)
        else:
            try:
                actions = self.env.get_valid_actions()
            except Exception:
                actions = [
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

        if max_actions > 0:
            actions = actions[:max_actions]

        return actions

    def get_location_graph(self) -> dict:
        """Get a graph of all discovered locations and their connections."""
        graph = {}

        try:
            all_objects = self.env.get_world_objects()
            locations = [obj for obj in all_objects if self._is_location(obj)]

            for loc in locations:
                loc_name = str(loc)
                graph[loc_name] = {
                    "num": loc.num,
                    "objects": [str(child) for child in self._get_children(loc)],
                    "exits": self._get_exits_from_location(loc),
                }
        except Exception:
            pass

        return graph

    def _is_location(self, obj) -> bool:
        """Check if an object is a location/room."""
        try:
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

    def _get_exits_from_location(self, location) -> list[str]:
        """Extract possible exits from a location."""
        exits = []
        directions = [
            "north",
            "south",
            "east",
            "west",
            "up",
            "down",
            "northeast",
            "northwest",
            "southeast",
            "southwest",
        ]

        for direction in directions:
            exits.append(direction)

        return exits

    def get_object_details(self, object_name: str) -> Optional[dict]:
        """Get detailed information about a specific object."""
        try:
            all_objects = self.env.get_world_objects()
            obj = next(
                (o for o in all_objects if str(o).lower() == object_name.lower()), None
            )

            if obj:
                return self._zobject_to_dict(obj)
        except Exception:
            pass
        return None

    def compare_to_walkthrough(self) -> dict:
        """Compare current progress to walkthrough."""
        try:
            walkthrough = self.get_walkthrough()
            current_moves = len(self._history)

            return {
                "current_moves": current_moves,
                "walkthrough_moves": len(walkthrough),
                "efficiency": round(len(walkthrough) / current_moves * 100, 2)
                if current_moves > 0
                else 0,
                "on_track": current_moves <= len(walkthrough) * 1.5,
            }
        except Exception:
            return {
                "current_moves": len(self._history),
                "error": "Walkthrough not available",
            }


ZorkEnvironment = TextAdventureEnv
