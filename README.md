# Jericho FastMCP Server

[Jericho](https://github.com/microsoft/jericho) is a Microsoft research library that wraps the Frotz Z-machine emulator, giving programmatic access to 50+ classic text adventure games (Zork, Adventure, etc.) — including the game's internal object tree, parser vocabulary, valid action generation, and state hashing. This server exposes that interface over MCP so AI agents can play and reason about these games through a clean, tool-based API.

---

## Features

- 🎮 Play 50+ classic text adventure games
- 💾 Single Game Session (Can only handle one Player at a time)
- 📚 Built-in guides as MCP Resources — agent-readable how-to-play and command reference

---

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

3. Set environment variables (see `.env.example`)

4. Run the server:
```bash
uv run main.py
```

### Docker

```bash
docker build -t jericho-fastmcp-server .
docker run -p 8000:8000 jericho-fastmcp-server
```

Server available at `http://localhost:8000`

---

## Use with Claude Code

```bash
claude mcp add jericho --transport http http://localhost:8000/mcp
```

Claude Code can then call all tools directly — start games, inspect world state, generate actions — with no additional configuration.

---

## MCP Interface

### Resources (read before playing)
| URI | Description |
|-----|-------------|
| `guide://how-to-play` | Full game loop, scoring mechanics, and exploration strategy |
| `guide://commands` | Z-machine command reference card |
| `game://info` | Live session status — score, location, inventory |

### Tools
| Tool | Description |
|------|-------------|
| `start_game(game_name)` | Load a game and begin a session |
| `action(command)` | Send a command — your main play tool |
| `current_state()` | Review state without using a move |
| `available_actions(limit)` | Get valid commands for the current state |
| `look_around()` | Inspect nearby objects via the object tree |
| `recent_history(count)` | Review past actions and results |
| `game_vocabulary()` | Get parser-recognised words by part of speech |
| `list_games(limit)` | Browse available games |
| `end_game()` | End the session and get a final summary |