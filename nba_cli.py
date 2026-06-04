#!/usr/bin/env python3
"""NBA live scoreboard and box score CLI.

Data source: https://cdn.nba.com/static/json/liveData/
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "https://cdn.nba.com/static/json/liveData"
SCOREBOARD_URL = f"{BASE_URL}/scoreboard/todaysScoreboard_00.json"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.nba.com/",
}


@dataclass(frozen=True)
class Column:
    name: str
    align: str = "left"  # left | right


def fetch_json(url: str) -> dict[str, Any]:
    request = Request(url, headers=HEADERS)
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 - public NBA JSON endpoint
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise SystemExit(f"NBA API HTTP error: {exc.code} {exc.reason}") from exc
    except URLError as exc:
        raise SystemExit(f"Network error: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit("NBA API returned invalid JSON") from exc


def scoreboard() -> dict[str, Any]:
    return fetch_json(SCOREBOARD_URL).get("scoreboard", {})


def boxscore(game_id: str) -> dict[str, Any]:
    url = f"{BASE_URL}/boxscore/boxscore_{game_id}.json"
    return fetch_json(url).get("game", {})


def iso_clock(clock: str | None) -> str:
    """Convert NBA clock like PT04M05.00S to 4:05."""
    if not clock or not clock.startswith("PT"):
        return ""
    value = clock.removeprefix("PT").removesuffix("S")
    minutes = "0"
    seconds = "00"
    if "M" in value:
        minutes, seconds = value.split("M", 1)
    else:
        seconds = value
    seconds = seconds.split(".", 1)[0].zfill(2)
    return f"{int(float(minutes))}:{seconds}"


def minutes(value: str | None) -> str:
    if not value:
        return "0"
    return iso_clock(value) or value


def pct(made: Any, attempted: Any) -> str:
    try:
        attempted_int = int(attempted)
        made_int = int(made)
    except (TypeError, ValueError):
        return "-"
    return f"{made_int}-{attempted_int}"


def team_label(team: dict[str, Any]) -> str:
    city = team.get("teamCity", "")
    name = team.get("teamName", "")
    tri = team.get("teamTricode", "")
    return f"{tri} {city} {name}".strip()


def format_game_line(game: dict[str, Any]) -> str:
    away = game.get("awayTeam", {})
    home = game.get("homeTeam", {})
    status = game.get("gameStatusText") or "Scheduled"
    if game.get("gameStatus") == 1:
        status = local_start_time(game) or status
    return (
        f"{game.get('gameId')}  "
        f"{away.get('teamTricode')} {away.get('score', 0)} @ "
        f"{home.get('teamTricode')} {home.get('score', 0)}  "
        f"{status}"
    )


def local_start_time(game: dict[str, Any]) -> str:
    raw = game.get("gameTimeUTC")
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw
    local = dt.astimezone()
    return local.strftime("%Y-%m-%d %H:%M %Z")


def print_table(columns: list[Column], rows: list[list[Any]]) -> None:
    text_rows = [[str(cell) for cell in row] for row in rows]
    widths = [len(column.name) for column in columns]
    for row in text_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt_row(values: list[str]) -> str:
        parts: list[str] = []
        for column, width, value in zip(columns, widths, values, strict=True):
            parts.append(value.rjust(width) if column.align == "right" else value.ljust(width))
        return "  ".join(parts)

    print(fmt_row([column.name for column in columns]))
    print(fmt_row(["-" * width for width in widths]))
    for row in text_rows:
        print(fmt_row(row))


def print_games(games: list[dict[str, Any]]) -> None:
    if not games:
        print("No NBA games today.")
        return
    rows = []
    for game in games:
        away = game.get("awayTeam", {})
        home = game.get("homeTeam", {})
        rows.append(
            [
                game.get("gameId", ""),
                game.get("gameLabel") or game.get("seriesGameNumber") or "",
                away.get("teamTricode", ""),
                away.get("score", 0),
                home.get("teamTricode", ""),
                home.get("score", 0),
                game.get("gameStatusText") or local_start_time(game),
            ]
        )
    print_table(
        [
            Column("Game ID"),
            Column("Label"),
            Column("Away"),
            Column("PTS", "right"),
            Column("Home"),
            Column("PTS", "right"),
            Column("Status"),
        ],
        rows,
    )


def player_rows(team: dict[str, Any], include_dnp: bool) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for player in team.get("players", []):
        played = player.get("played") == "1"
        if not played and not include_dnp:
            continue
        stats = player.get("statistics", {})
        rows.append(
            [
                "*" if player.get("oncourt") == "1" else "",
                player.get("name", ""),
                player.get("position", ""),
                minutes(stats.get("minutes")),
                stats.get("points", 0) if played else "DNP",
                stats.get("reboundsTotal", 0) if played else "",
                stats.get("assists", 0) if played else "",
                pct(stats.get("fieldGoalsMade"), stats.get("fieldGoalsAttempted")) if played else "",
                pct(stats.get("threePointersMade"), stats.get("threePointersAttempted")) if played else "",
                pct(stats.get("freeThrowsMade"), stats.get("freeThrowsAttempted")) if played else "",
                stats.get("steals", 0) if played else "",
                stats.get("blocks", 0) if played else "",
                stats.get("turnovers", 0) if played else "",
                f"{stats.get('plusMinusPoints', 0):+g}" if played else "",
            ]
        )
    return rows


def print_boxscore(game: dict[str, Any], include_dnp: bool = False) -> None:
    if not game:
        print("Box score not found for this game.")
        return
    away = game.get("awayTeam", {})
    home = game.get("homeTeam", {})
    print(
        f"\n{game.get('gameId')}  "
        f"{team_label(away)} {away.get('score', 0)} @ "
        f"{team_label(home)} {home.get('score', 0)}  "
        f"{game.get('gameStatusText', '')}"
    )
    print(f"Arena: {game.get('arena', {}).get('arenaName', '')}\n")
    columns = [
        Column("On"),
        Column("Player"),
        Column("Pos"),
        Column("MIN", "right"),
        Column("PTS", "right"),
        Column("REB", "right"),
        Column("AST", "right"),
        Column("FG", "right"),
        Column("3PT", "right"),
        Column("FT", "right"),
        Column("STL", "right"),
        Column("BLK", "right"),
        Column("TO", "right"),
        Column("+/-", "right"),
    ]
    for team in (away, home):
        print(team_label(team))
        rows = player_rows(team, include_dnp)
        print_table(columns, rows)
        print()


def find_game(games: list[dict[str, Any]], query: str | None) -> dict[str, Any] | None:
    if not games:
        return None
    if not query:
        return games[0]
    query_upper = query.upper()
    for game in games:
        if game.get("gameId") == query:
            return game
        teams = (game.get("awayTeam", {}), game.get("homeTeam", {}))
        if any(team.get("teamTricode") == query_upper for team in teams):
            return game
    return None


def show(args: argparse.Namespace) -> None:
    board = scoreboard()
    games = board.get("games", [])
    print(f"NBA games for {board.get('gameDate', 'today')}\n")
    print_games(games)
    if args.scores_only or not games:
        return

    selected_games = games
    if args.game:
        game = find_game(games, args.game)
        if not game:
            raise SystemExit(f"Game not found: {args.game}. Use a Game ID or team abbreviation, such as LAL.")
        selected_games = [game]

    for game in selected_games:
        print_boxscore(boxscore(game["gameId"]), include_dnp=args.include_dnp)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="View today's NBA scores and player box scores. By default, shows all games and stats for players who have appeared."
    )
    parser.add_argument("game", nargs="?", help="Optional Game ID or team abbreviation, such as 0042500401 / LAL")
    parser.add_argument("--scores-only", action="store_true", help="Show only today's scores; do not fetch player stats")
    parser.add_argument("--include-dnp", action="store_true", help="Show players who did not play")
    parser.add_argument("--watch", type=int, metavar="SECONDS", help="Refresh every N seconds, such as --watch 30")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.watch is not None and args.watch < 5:
        parser.error("--watch must be at least 5 seconds to avoid requesting the NBA CDN too frequently")

    while True:
        if args.watch:
            print("\033c", end="")
            print(f"Auto refresh every {args.watch}s. Ctrl-C to stop.\n")
        show(args)
        if not args.watch:
            return 0
        try:
            time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\nStopped.")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
