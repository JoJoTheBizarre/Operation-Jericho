HOW_TO_PLAY = """
# Text Adventure Agent Guide

## Game Loop (every turn)
1. Read `observation` — what happened and where you are
2. Check `inventory`, `score`, `reward`, `location`
3. Choose an action; use `available_actions()` if unsure
4. Call `action(command)` → repeat until `done=True`

## Session Setup
1. `start_game(game_name)` — default: 'zork1'
2. Read opening observation carefully
3. `end_game()` when finished

## Response Fields
| Field | Meaning |
|-------|---------|
| `observation` | Game's reply to your command |
| `reward` | Points gained THIS turn (can be negative) |
| `score / max_score` | Current vs. maximum possible score |
| `done` | True = game over (win or loss) |
| `inventory` | Items you're carrying |
| `location` | Current room name |

## Scoring — Your Primary Signal
- `reward > 0` → meaningful action — remember what caused it
- `reward < 0` → mistake — don't repeat similar actions
- `reward == 0` → neutral — may still progress the story
- `done=True, score == max_score` → you won
- `done=True, score < max_score` → death or dead-end

## Maximizing Score
- Score is sparse — most moves give zero reward. Think ahead, not greedily.
- Track causality: actions now (grabbing a lamp) enable rewards later (dark area exploration)
- When reward increases, note exactly what triggered it and generalize from it
- Collect valuables and treasures whenever you find them — they are often the primary score source
- Deposit treasures in the correct location (e.g. Trophy Case in Zork1) to actually score points
- Solve puzzles correctly rather than forcing them — some items score more if handled the right way
- Examine everything, open containers, read all written objects
- Try all exits from every room to build a complete map
- Use `recent_history()` to avoid repeating failed approaches

## Parser Tips
- Use simple commands: `take lamp`, `go north`, `open door`
- If rejected: try simpler phrasing or call `game_vocabulary()`
- Parsers read only the first 6–9 characters per word

## Useful Tools
- `available_actions()` — guaranteed valid commands right now
- `look_around()` — reveals items the narrative may not mention
- `explore_map()` — world layout from the engine
- `recent_history()` — review past actions to avoid repeating failures
- `current_state()` — snapshot of situation without using a move
"""

GUIDE_COMMANDS = """
# Z-Machine Command Reference

## Movement
north/n, south/s, east/e, west/w, northeast/ne, northwest/nw,
southeast/se, southwest/sw, up/u, down/d, enter/in, exit/out, climb X

## Looking & Examining
look/l — redescribe current room
examine X / x X — inspect object in detail
look in/under/behind X — check specific areas of an object
search X — find hidden items on or in X
read X — read written objects (signs, books, notes)

## Inventory
inventory/i — list carried items
take X / get X — pick up item X
take all — pick up everything in the room
take X from Y — extract X from container Y
drop X — drop item X
put X in Y / put X on Y — place X inside or on top of Y
wear X / remove X — equip or unequip wearable items

## Object Interaction
open/close X — open or close door or container X
lock/unlock X with Y — use key Y on X
push/pull/move X — reposition object X
turn X / turn X on/off — rotate or toggle device X
light X / extinguish X — ignite or put out a light source
attack X with Y / kill X with Y — combat
throw X at Y — hurl item X at target Y
tie X to Y — bind X to object Y
cut X with Y — cut X using tool Y
eat X / drink X — consume item X
smell X / listen — gather sensory clues
press X — press button or switch X
dig X with Y — excavate area X with tool Y
pour X into Y — transfer liquid X into Y
wave X / rub X / wind X — interact with special objects

## NPC Interaction
talk to X — initiate conversation
ask X about Y — query character X on topic Y
tell X about Y — inform character X about Y
show X to Y — present item X to character Y
give X to Y — hand item X to character Y
say "phrase" — speak something aloud

## Meta
again/g — repeat last command
wait/z — pass one turn
score — show current score
verbose — always show full room descriptions
brief — show short room descriptions
save / restore — save or reload game state
restart — restart from beginning
quit/q — quit the game

## Parser Tips
- Only the first 6-9 characters of each word are read: 'examin' = 'examine'
- Adjectives work as shorthand if unambiguous: "take rusty" picks up the rusty knife
- 'x' is shorthand for examine — use it freely
- Some puzzles require unusual verbs: pray, sleep, jump, sing, dance — try them if stuck
- Descriptions can change after world state changes — re-examine objects after key events
- If rejected, simplify your phrasing or call game_vocabulary() for valid words
- NPC progress often requires give, show, or ask about — not just talk to
"""