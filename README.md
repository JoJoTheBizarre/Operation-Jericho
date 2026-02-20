# Jericho FastMCP Server

A FastMCP HTTP server for playing classic text adventure games (Zork, Adventure, etc.) using the Jericho library with rich introspection capabilities.

## Features

- 🎮 Play 50+ classic text adventure games
- 💾 Session management with save/load states
- 🔄 Automatic session cleanup
- 🌍 **World object tree inspection** - See all objects and their relationships
- 🔍 **State hash tracking** - Detect revisited states
- 📖 **Game dictionary** - Access complete parser vocabulary
- 🎯 **Template action generator** - Smart action generation
- 🗺️ **Location graph** - Map discovered areas
- 📊 **Walkthrough comparison** - Compare progress to optimal path

## Quick Start

### Local Development

1. Install dependencies:
```bash
uv sync
```

2. Download game files:
```bash
chmod +x download_games.sh
./download_games.sh
```

3. Run the HTTP server:
```bash
uv run main.py
```

### Docker

Build and run:
```bash
docker build -t jericho-fastmcp-server .
docker run -p 8000:8000 jericho-fastmcp-server
```

The server will be available at `http://localhost:8000`

## Available Tools

### Core Gameplay
- `list_available_games_tool` - List all available games
- `start_game` - Start a new game session
- `take_action` - Execute a command in the game
- `get_game_state` - Get current game state
- `get_game_history` - View action history
- `end_game` - End a game session

### World Inspection (NEW!)
- `get_world_objects` - Get ALL objects in the game with relationships
- `get_objects_in_location` - See objects in specific or current location
- `get_object_details` - Get detailed object attributes (container, takeable, etc.)
- `get_location_graph` - Map of all discovered locations

### Action Generation (NEW!)
- `get_valid_actions` - Basic valid actions
- `get_valid_actions_advanced` - Advanced filtering and template-based generation
- `get_action_templates` - Get command templates (e.g., "take [object]")
- `generate_template_actions` - Generate actions from templates
- `get_game_dictionary` - All words the parser recognizes

### State Management
- `save_game_state` - Save current progress
- `load_game_state` - Load saved progress
- `check_state_visited` - Check if current state was visited before
- `get_world_state_hash` - Get MD5 hash of current state

### Analysis & Learning (NEW!)
- `get_game_info` - Comprehensive game metadata
- `compare_to_walkthrough` - Compare your progress to optimal solution

## Environment Variables

- `HOST` - Server host (default: 0.0.0.0)
- `PORT` - Server port (default: 8000)
- `ZORK_GAMES_DIR` - Custom games directory path


## Agent-Friendly Features

This server is designed to help AI agents play text adventure games effectively:

1. **X-Ray Vision**: See ALL objects in the game, not just current room
2. **Loop Detection**: Track state hashes to avoid infinite loops
3. **Smart Actions**: Template-based action generation reduces search space
4. **Progress Tracking**: Compare to walkthrough to know if on right track
5. **Object Understanding**: Know which objects are containers, takeable, etc.
6. **Vocabulary Access**: Know exactly what words the parser understands

## Example Usage

```python
# Start a game
response = start_game("zork1")
session_id = response["session_id"]

# Get game info and vocabulary
info = get_game_info(session_id)
vocab = get_game_dictionary(session_id)

# See all objects in the game
objects = get_world_objects(session_id)

# Generate smart actions
actions = generate_template_actions(session_id, filter_type=["take", "open"])

# Take action and check if state was visited
result = take_action(session_id, "go north")
visited = check_state_visited(session_id)

# Compare progress
comparison = compare_to_walkthrough(session_id)
```

## License

MIT
