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