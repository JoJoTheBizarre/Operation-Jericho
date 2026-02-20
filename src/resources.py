HOW_TO_PLAY = """
# How to Play Text Adventure Games

## What is a text adventure?
A text adventure (interactive fiction) is a parser-based game. You type short natural-language
commands, and the game responds with a narrative description of what happened. The world is made
of locations connected by exits. You carry an inventory and solve puzzles by combining items,
exploring, and interacting with the environment.

## The game loop — follow this every turn
1. Read `observation` in the response — it tells you what just happened and where you are
2. Check `inventory` to know what you're carrying
3. Check `score` and `moves` to track progress
4. Decide your next action; if unsure, call `available_actions()` to see valid commands
5. Call `action(command)` with your chosen command
6. Repeat until `done=True`

## Starting a session (recommended order)
1. (Optional) Call `list_games()` to browse available games
2. Call `start_game(game_name)` — default is 'zork1'
3. Read the opening `observation` carefully — it sets the scene
4. Begin issuing commands with `action()`
5. Call `end_game()` when finished

## Understanding the response fields
- `observation`  — the game's narrative reply to your last command
- `score`        — your current score
- `max_score`    — the highest possible score in this game
- `moves`        — total commands issued so far
- `done`         — True means the game ended (win or lose)
- `reward`       — points gained THIS turn only (can be negative)
- `inventory`    — list of items you are currently carrying
- `location`     — name of your current location
- `progress`     — score/max_score as a quick percentage summary

## How scoring works
- `reward > 0`  : You did something meaningful — note what triggered it
- `reward < 0`  : You made a costly mistake — consider a different approach
- `reward == 0` : Neutral move — may still advance the story
- `done=True` with `score >= max_score`: You won!
- `done=True` with `score < max_score` : You died or hit a dead-end

## When the parser doesn't understand you
Responses like "I don't know the word X" or "That's not a verb I recognise" mean the
game rejected your phrasing. Try:
1. Simpler phrasing — "take lamp" instead of "pick up the lamp"
2. Call `game_vocabulary()` to check what words the parser accepts
3. Call `available_actions()` to get commands guaranteed to work right now
4. Remember: most parsers only read the first 6–9 characters of each word

## Exploration strategy
- Always `examine` objects you see — they may contain clues or hidden items
- Open containers (mailboxes, chests, bags) — they usually hold important items
- Read written objects (leaflets, signs, notes, books)
- Try all cardinal directions from every location to build a mental map
- Use `look_around()` to inspect the object tree for items the narrative may not mention
- Use `explore_map()` to see the world layout from the game engine's perspective
- Use `recent_history()` to review what you've tried and avoid repeating failures

## One session at a time
This server holds one game session. Progress is lost if `start_game()` is called again.
Use `current_state()` anytime to review your situation without consuming a move.
"""

GUIDE_COMMANDS = """
# Z-Machine Command Reference

## Movement
| Command          | Effect                              |
|------------------|-------------------------------------|
| north / n        | Move north                          |
| south / s        | Move south                          |
| east / e         | Move east                           |
| west / w         | Move west                           |
| northeast / ne   | Move northeast                      |
| northwest / nw   | Move northwest                      |
| southeast / se   | Move southeast                      |
| southwest / sw   | Move southwest                      |
| up / u           | Move up (stairs, climb, etc.)       |
| down / d         | Move down                           |
| enter / in       | Enter a structure or passage        |
| exit / out       | Leave a structure                   |

## Looking & Examining
| Command          | Effect                              |
|------------------|-------------------------------------|
| look / l         | Describe current location freshly   |
| examine X / x X  | Examine object X in detail          |
| look in X        | Look inside container X             |
| read X           | Read text on object X               |

## Inventory
| Command          | Effect                              |
|------------------|-------------------------------------|
| inventory / i    | List what you're carrying           |
| take X / get X   | Pick up item X                      |
| take all         | Pick up everything in the room      |
| drop X           | Drop item X                         |
| put X in Y       | Place X inside container Y          |
| put X on Y       | Place X on surface Y                |
| wear X           | Wear a wearable item                |
| remove X         | Remove a worn item                  |

## Object Interaction
| Command          | Effect                              |
|------------------|-------------------------------------|
| open X           | Open door or container X            |
| close X          | Close door or container X           |
| lock X with Y    | Lock X using key Y                  |
| unlock X with Y  | Unlock X using key Y                |
| push X / pull X  | Push or pull object X               |
| turn X on/off    | Toggle or activate X                |
| attack X with Y  | Attack X using weapon Y             |
| eat X / drink X  | Consume item X                      |

## Communication
| Command          | Effect                              |
|------------------|-------------------------------------|
| talk to X        | Start a conversation                |
| ask X about Y    | Ask character X about topic Y       |
| tell X about Y   | Tell character X about Y            |
| say "phrase"     | Say something aloud                 |

## Meta / System
| Command          | Effect                              |
|------------------|-------------------------------------|
| again / g        | Repeat your last command            |
| wait / z         | Pass one turn without acting        |
| score            | Display current score               |
| verbose          | Always show full room descriptions  |
| brief            | Show short room descriptions        |
| quit / q         | Quit the game                       |

## Parser Quirks
- Most parsers recognise only the first **6–9 characters** of each word.
  'northw' = 'northwest', 'examin' = 'examine', 'invent' = 'inventory'
- Adjectives can stand in for full object names: "take rusty" works if only
  one rusty object exists in the room
- 'x' is shorthand for 'examine' — use it freely
- If a command is rejected, check `game_vocabulary()` for valid words
"""