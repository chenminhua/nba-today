# NBA CLI

A zero-dependency Python CLI for viewing today's NBA scores and player box scores from the official NBA `liveData` JSON endpoints.

## Installation

```bash
uv tool install git+https://github.com/chenminhua/nba-today.git
```

## Usage

```bash
# Show all of today's games and player stats for players who have appeared
nba-today

# Show only the score list
nba-today --scores-only

# Show one game by Game ID or team abbreviation
nba-today 0042500401
nba-today LAL

# Include players who did not play
nba-today --include-dnp

# Refresh every 30 seconds
nba-today --watch 30
```

During development, you can also run the CLI without installing it:

```bash
uv run nba-today
# or
uv run python nba_cli.py
```

In the player table, `*` in the `On` column means the player is currently on the court. Stat columns include minutes, points, rebounds, assists, field goals, three-pointers, free throws, steals, blocks, turnovers, and plus/minus.

## Data sources

- Scoreboard: `https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json`
- Box score: `https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{gameId}.json`
