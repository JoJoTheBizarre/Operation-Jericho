# Jericho MCP Server

MCP server for playing classic text adventure games (Zork, Adventure, etc.) via Jericho.

## MCP Tools Exposed

- `list_available_games` - List all available text adventure games
- `create_game_session` - Start a new game session with a specific game
- `game_step` - Take an action in the game (move, take item, use object, etc.)
- `get_game_state` - Get the current state of a game session
- `get_valid_actions` - Get a list of valid actions for the current game state
- `reset_game` - Reset a game session to the beginning
- `save_game_state` - Save the current game state for later restoration
- `load_game_state` - Load a previously saved game state
- `close_game_session` - Close a game session and free resources

## Docker

```bash
docker build -t jericho-mcp-server .
docker run -it --rm jericho-mcp-server
```

## Games

Games are cloned from https://github.com/BYU-PCCL/z-machine-games during Docker build.