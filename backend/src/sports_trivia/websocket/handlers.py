"""WebSocket event handlers."""

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from fastapi import WebSocket

from sports_trivia.models import GameMode, GamePhase, Room, Sport
from sports_trivia.services.game_manager import GameManager
from sports_trivia.services.room_manager import RoomManager
from sports_trivia.websocket.events import ClientEvent, ServerEvent, create_message

# Validation limits
MAX_PLAYER_NAME_LENGTH = 50
MAX_CLUB_NAME_LENGTH = 100
MAX_GUESS_LENGTH = 100
MAX_ROOM_CODE_LENGTH = 10

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self) -> None:
        # player_id -> WebSocket
        self._connections: dict[str, WebSocket] = {}
        # player_id -> room_code
        self._player_rooms: dict[str, str] = {}
        # Track unreachable players for potential cleanup
        self._unreachable_players: set[str] = set()

    async def connect(self, websocket: WebSocket, player_id: str) -> None:
        """Accept and store a new connection."""
        await websocket.accept()
        self._connections[player_id] = websocket
        self._unreachable_players.discard(player_id)

    def disconnect(self, player_id: str) -> str | None:
        """Remove a connection. Returns room_code if player was in a room."""
        self._connections.pop(player_id, None)
        self._unreachable_players.discard(player_id)
        return self._player_rooms.pop(player_id, None)

    def set_room(self, player_id: str, room_code: str) -> None:
        """Associate a player with a room."""
        self._player_rooms[player_id] = room_code

    def get_room(self, player_id: str) -> str | None:
        """Get the room a player is in."""
        return self._player_rooms.get(player_id)

    def get_room_players(self, room_code: str) -> list[str]:
        """Get all player IDs in a room."""
        return [pid for pid, code in self._player_rooms.items() if code == room_code]

    def is_player_unreachable(self, player_id: str) -> bool:
        """Check if a player has been marked as unreachable."""
        return player_id in self._unreachable_players

    async def send_to_player(self, player_id: str, message: dict[str, Any]) -> bool:
        """Send a message to a specific player."""
        websocket = self._connections.get(player_id)
        if websocket:
            try:
                await websocket.send_json(message)
                return True
            except Exception as e:
                logger.warning(f"Error sending to player {player_id}: {e}")
                self._unreachable_players.add(player_id)
        return False

    async def broadcast_to_room(
        self,
        room_code: str,
        message: dict[str, Any],
        exclude: str | None = None,
    ) -> None:
        """Broadcast a message to all players in a room."""
        for player_id in self.get_room_players(room_code):
            if player_id != exclude:
                await self.send_to_player(player_id, message)


class WebSocketHandler:
    """Handles WebSocket events for the game."""

    def __init__(
        self,
        room_manager: RoomManager,
        game_manager: GameManager,
        connection_manager: ConnectionManager,
    ) -> None:
        self._room_manager = room_manager
        self._game_manager = game_manager
        self._connections = connection_manager
        self._timeout_tasks: dict[str, asyncio.Task] = {}

    async def handle_connection(self, websocket: WebSocket) -> None:
        """Handle a new WebSocket connection."""
        player_id = str(uuid.uuid4())
        await self._connections.connect(websocket, player_id)

        try:
            while True:
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from {player_id}: {data[:100]}")
                    await self._send_error(player_id, "Invalid message format")
                    continue
                await self._handle_message(player_id, message)
        except Exception as e:
            logger.info(f"Connection closed for {player_id}: {e}")
        finally:
            await self._handle_disconnect(player_id)

    async def _handle_message(self, player_id: str, message: dict[str, Any]) -> None:
        """Route incoming messages to appropriate handlers."""
        event = message.get("event")
        data = message.get("data", {})

        handlers = {
            ClientEvent.CREATE_ROOM.value: self._handle_create_room,
            ClientEvent.JOIN_ROOM.value: self._handle_join_room,
            ClientEvent.SUBMIT_CLUB.value: self._handle_submit_club,
            ClientEvent.SUBMIT_GUESS.value: self._handle_submit_guess,
            ClientEvent.PLAY_AGAIN.value: self._handle_play_again,
            ClientEvent.LEAVE_ROOM.value: self._handle_leave_room,
            ClientEvent.SYNC_STATE.value: self._handle_sync_state,
            ClientEvent.PING.value: self._handle_ping,
            # Multiplayer events
            ClientEvent.START_GAME.value: self._handle_start_game,
            ClientEvent.START_ROUND.value: self._handle_start_round,
            # NBA Grid events
            ClientEvent.START_GRID_GAME.value: self._handle_start_grid_game,
            ClientEvent.SUBMIT_GRID_GUESS.value: self._handle_submit_grid_guess,
            ClientEvent.SKIP_GRID_TURN.value: self._handle_skip_grid_turn,
            ClientEvent.PROPOSE_GRID_DRAW.value: self._handle_propose_grid_draw,
            ClientEvent.RESPOND_GRID_DRAW.value: self._handle_respond_grid_draw,
        }

        handler = handlers.get(event)
        if handler:
            await handler(player_id, data)
        else:
            await self._send_error(player_id, f"Unknown event: {event}")

    async def _handle_create_room(self, player_id: str, data: dict[str, Any]) -> None:
        """Handle room creation."""
        player_name = data.get("player_name", "Player 1")
        sport_str = data.get("sport", "nba")
        mode_str = data.get("mode", "classic")
        max_players = data.get("max_players", 2)

        # Validate player name (strip first, then check)
        player_name = str(player_name).strip()[:MAX_PLAYER_NAME_LENGTH]
        if not player_name:
            await self._send_error(player_id, "Invalid player name")
            return

        try:
            sport = Sport(str(sport_str).lower())
        except ValueError:
            await self._send_error(player_id, f"Invalid sport: {sport_str}")
            return

        try:
            mode = GameMode(str(mode_str).lower())
        except ValueError:
            await self._send_error(player_id, f"Invalid mode: {mode_str}")
            return

        # Validate max_players
        try:
            max_players = int(max_players)
        except (ValueError, TypeError):
            max_players = 2

        # Leave any existing room first
        await self._leave_current_room(player_id)

        room = self._room_manager.create_room(player_id, player_name, sport, mode, max_players)
        self._connections.set_room(player_id, room.code)

        await self._connections.send_to_player(
            player_id,
            create_message(
                ServerEvent.ROOM_CREATED,
                room_code=room.code,
                sport=room.sport.value,
                mode=room.mode.value,
                max_players=room.max_players,
                host_id=room.host_id,
                player={"id": player_id, "name": player_name, "score": 0},
            ),
        )

    async def _handle_join_room(self, player_id: str, data: dict[str, Any]) -> None:
        """Handle joining a room."""
        room_code = str(data.get("room_code", "")).strip().upper()[:MAX_ROOM_CODE_LENGTH]
        player_name = data.get("player_name", "Player 2")

        # Validate room code
        if not room_code:
            await self._send_error(player_id, "Invalid room code")
            return

        # Validate player name (strip first, then check)
        player_name = str(player_name).strip()[:MAX_PLAYER_NAME_LENGTH]
        if not player_name:
            await self._send_error(player_id, "Invalid player name")
            return

        # Leave any existing room first
        await self._leave_current_room(player_id)

        room = self._room_manager.join_room(room_code, player_id, player_name)
        if room is None:
            await self._send_error(player_id, "Room not found or full")
            return

        self._connections.set_room(player_id, room_code)

        # Send room state to joining player
        await self._connections.send_to_player(
            player_id,
            create_message(
                ServerEvent.ROOM_JOINED,
                room_code=room.code,
                sport=room.sport.value,
                mode=room.mode.value,
                max_players=room.max_players,
                host_id=room.host_id,
                players=[{"id": p.id, "name": p.name, "score": p.score} for p in room.players],
                phase=room.game_state.phase.value,
                pool_size=len(room.game_state.club_pool),
            ),
        )

        # Notify other players
        new_player = room.get_player(player_id)
        if new_player:
            await self._connections.broadcast_to_room(
                room_code,
                create_message(
                    ServerEvent.PLAYER_JOINED,
                    player={"id": new_player.id, "name": new_player.name, "score": 0},
                    phase=room.game_state.phase.value,
                    player_count=len(room.players),
                ),
                exclude=player_id,
            )

    async def _handle_submit_club(self, player_id: str, data: dict[str, Any]) -> None:
        """Handle club submission."""
        result = await self._get_player_room(player_id)
        if not result:
            return
        room_code, room = result

        club_name = data.get("club_name", "")

        # Validate club name (strip first, then check)
        club_name = str(club_name).strip()[:MAX_CLUB_NAME_LENGTH]
        if not club_name:
            await self._send_error(player_id, "Invalid club name")
            return

        # Update room activity
        self._room_manager.touch_room(room_code)

        # Serialize all state mutations with per-room lock
        async with room.get_lock():
            result = self._game_manager.submit_club(room, player_id, club_name)

            if not result["success"]:
                await self._send_error(player_id, result["error"])
                return

            # Route broadcast by mode
            if room.mode == GameMode.MULTIPLAYER:
                # Get player name for better UI feedback
                player = room.get_player(player_id)
                player_name = player.name if player else None

                # Multiplayer: broadcast POOL_UPDATED
                await self._connections.broadcast_to_room(
                    room_code,
                    create_message(
                        ServerEvent.POOL_UPDATED,
                        player_id=player_id,
                        player_name=player_name,
                        club=result.get("club"),
                        pool_size=result.get("pool_size", len(room.game_state.club_pool)),
                    ),
                )
            else:
                # Classic: broadcast CLUB_SUBMITTED
                await self._connections.broadcast_to_room(
                    room_code,
                    create_message(ServerEvent.CLUB_SUBMITTED, player_id=player_id),
                )

                # Check if both players have submitted and start guessing (classic only)
                if self._game_manager.check_clubs_ready(room):
                    guessing_result = self._game_manager.start_guessing_phase(room)

                    if guessing_result["success"]:
                        await self._connections.broadcast_to_room(
                            room_code,
                            create_message(
                                ServerEvent.GUESSING_STARTED,
                                clubs=guessing_result["clubs"],
                                club_info=guessing_result.get("club_info"),
                                deadline=guessing_result["deadline"],
                                valid_count=guessing_result["valid_count"],
                            ),
                        )
                        # Start timeout task
                        self._start_timeout_task(room_code, guessing_result["deadline"])
                    else:
                        # No common players, notify and reset
                        await self._connections.broadcast_to_room(
                            room_code,
                            create_message(
                                ServerEvent.CLUBS_INVALID, error=guessing_result["error"]
                            ),
                        )

    async def _handle_submit_guess(self, player_id: str, data: dict[str, Any]) -> None:
        """Handle player name guess."""
        result = await self._get_player_room(player_id)
        if not result:
            return
        room_code, room = result

        guess = data.get("player_name", "")

        # Validate guess (strip first, then check)
        guess = str(guess).strip()[:MAX_GUESS_LENGTH]
        if not guess:
            await self._send_error(player_id, "Invalid guess")
            return

        # Update room activity
        self._room_manager.touch_room(room_code)

        # Serialize all state mutations with per-room lock
        async with room.get_lock():
            result = self._game_manager.submit_guess(room, player_id, guess)

            if not result["success"]:
                await self._send_error(player_id, result["error"])
                return

            # Broadcast guess result
            await self._connections.broadcast_to_room(
                room_code,
                create_message(
                    ServerEvent.GUESS_RESULT,
                    correct=result["correct"],
                    player_id=player_id,
                    guess=result.get("guess") or result.get("answer"),
                ),
            )

            # If correct, end the round
            if result["correct"]:
                self._cancel_timeout_task(room_code)

                # Get player details with images
                data_service = self._game_manager._get_data_service(room.sport)
                valid_answer_details = data_service.get_player_details(
                    room.game_state.valid_answers
                )

                # Get winning answer image
                winning_answer_image = None
                for detail in valid_answer_details:
                    if detail["name"].lower() == result["answer"].lower():
                        winning_answer_image = detail.get("image_url")
                        break

                await self._connections.broadcast_to_room(
                    room_code,
                    create_message(
                        ServerEvent.ROUND_ENDED,
                        winner_id=result["player_id"],
                        winning_answer=result["answer"],
                        winning_answer_image=winning_answer_image,
                        points=result["points"],
                        valid_answers=room.game_state.valid_answers,
                        valid_answer_details=valid_answer_details,
                        scores={p.id: p.score for p in room.players},
                    ),
                )

    async def _handle_play_again(self, player_id: str, _data: dict[str, Any]) -> None:
        """Handle play again request."""
        result = await self._get_player_room(player_id)
        if not result:
            return
        room_code, room = result

        self._room_manager.touch_room(room_code)

        # Serialize all state mutations with per-room lock
        async with room.get_lock():
            result = self._game_manager.start_new_round(room, player_id)
            if not result["success"]:
                await self._send_error(player_id, result.get("error", "Failed to start new round"))
                return

            if room.mode == GameMode.NBA_GRID:
                # Grid: regenerated grid + fresh timer; broadcast GRID_GAME_STARTED
                # using the same payload as the initial start.
                await self._connections.broadcast_to_room(
                    room_code,
                    create_message(
                        ServerEvent.GRID_GAME_STARTED,
                        grid=result["grid"],
                        row_categories=result["row_categories"],
                        col_categories=result["col_categories"],
                        player_symbols=result["player_symbols"],
                        current_turn_player_id=result["current_turn_player_id"],
                        turn_deadline=result["turn_deadline"],
                    ),
                )
                self._start_grid_clock_task(room_code)
            elif room.mode == GameMode.MULTIPLAYER:
                # Multiplayer: instant re-pick from pool, guessing starts immediately
                if result.get("clubs"):
                    await self._connections.broadcast_to_room(
                        room_code,
                        create_message(
                            ServerEvent.GUESSING_STARTED,
                            clubs=result["clubs"],
                            club_info=result.get("club_info"),
                            club_submitters=result.get("club_submitters"),
                            deadline=result["deadline"],
                            valid_count=result["valid_count"],
                            fallback_club_count=result.get("fallback_club_count"),
                        ),
                    )
                    self._start_timeout_task(room_code, result["deadline"])
                else:
                    # Selection failed - need more clubs or manual retry
                    await self._connections.broadcast_to_room(
                        room_code,
                        create_message(
                            ServerEvent.SELECTION_FAILED,
                            error=result.get("error", "Could not find clubs with common players"),
                        ),
                    )
            else:
                # Classic: broadcast NEW_ROUND
                await self._connections.broadcast_to_room(
                    room_code,
                    create_message(ServerEvent.NEW_ROUND, phase=result["phase"]),
                )

    async def _handle_leave_room(self, player_id: str, _data: dict[str, Any]) -> None:
        """Handle player leaving room."""
        await self._handle_disconnect(player_id)

    async def _handle_sync_state(self, player_id: str, _data: dict[str, Any]) -> None:
        """Handle client request for full state sync (e.g., after reconnect)."""
        result = await self._get_player_room(player_id)
        if not result:
            return
        room_code, room = result

        self._room_manager.touch_room(room_code)

        player = room.get_player(player_id)
        if not player:
            await self._send_error(player_id, "Player not found in room")
            return

        # Build player-specific club assignments (for classic mode)
        my_club = None
        opponent_club = None
        if room.mode == GameMode.CLASSIC and room.game_state.clubs:
            # Explicitly assign clubs based on player order
            if room.players[0].id == player_id:
                my_club = room.game_state.clubs[0]
                opponent_club = room.game_state.clubs[1]
            else:
                my_club = room.game_state.clubs[1]
                opponent_club = room.game_state.clubs[0]

        # Build state sync message
        sync_data: dict[str, Any] = {
            "version": room.game_state.version,
            "room_code": room_code,
            "sport": room.sport.value,
            "mode": room.mode.value,
            "max_players": room.max_players,
            "host_id": room.host_id,
            "phase": room.game_state.phase.value,
            "deadline": room.game_state.deadline,
            "valid_answer_count": room.game_state.valid_answer_count,
            "self_player": {
                "id": player.id,
                "name": player.name,
                "score": player.score,
                "submitted": player.submitted_club is not None,
            },
            "players": [{"id": p.id, "name": p.name, "score": p.score} for p in room.players],
        }

        if room.mode == GameMode.MULTIPLAYER:
            # Multiplayer-specific state
            sync_data["pool_size"] = len(room.game_state.club_pool)
            sync_data["selected_clubs"] = room.game_state.selected_clubs
            sync_data["clubs_per_round"] = room.game_state.clubs_per_round
        elif room.mode == GameMode.NBA_GRID:
            # Grid-mode snapshot — frontend re-hydrates from this on reconnect.
            from sports_trivia.services.game_manager import (
                _category_to_dict,
                _grid_to_dict,
            )

            gs = room.game_state
            sync_data["grid"] = _grid_to_dict(gs.grid) if gs.grid else None
            sync_data["row_categories"] = (
                [_category_to_dict(c) for c in gs.row_categories] if gs.row_categories else None
            )
            sync_data["col_categories"] = (
                [_category_to_dict(c) for c in gs.col_categories] if gs.col_categories else None
            )
            sync_data["current_turn_player_id"] = gs.current_turn_player_id
            sync_data["player_symbols"] = gs.player_symbols
            sync_data["turn_deadline"] = gs.turn_deadline
            sync_data["draw_proposal"] = (
                {
                    "proposer_id": gs.draw_proposal.proposer_id,
                    "proposed_at": gs.draw_proposal.proposed_at,
                }
                if gs.draw_proposal
                else None
            )
            sync_data["end_reason"] = gs.end_reason
            sync_data["winner_id"] = gs.winner_id
        else:
            # Classic mode state
            sync_data["my_club"] = my_club
            sync_data["opponent_club"] = opponent_club
            opponent = next((p for p in room.players if p.id != player_id), None)
            sync_data["opponent"] = (
                {
                    "id": opponent.id,
                    "name": opponent.name,
                    "score": opponent.score,
                    "submitted": opponent.submitted_club is not None,
                }
                if opponent
                else None
            )

        # Send full state snapshot
        await self._connections.send_to_player(
            player_id,
            create_message(ServerEvent.STATE_SYNC, **sync_data),
        )

    async def _handle_ping(self, player_id: str, _data: dict[str, Any]) -> None:
        """Handle keep-alive ping from client."""
        logger.debug(f"Ping received from {player_id}")
        await self._connections.send_to_player(
            player_id,
            create_message(ServerEvent.PONG),
        )

    async def _handle_start_game(self, player_id: str, _data: dict[str, Any]) -> None:
        """Handle start game request (multiplayer only, host only)."""
        result = await self._get_player_room(player_id)
        if not result:
            return
        room_code, room = result

        self._room_manager.touch_room(room_code)

        # Serialize all state mutations with per-room lock
        async with room.get_lock():
            result = self._game_manager.start_game(room, player_id)

            if not result["success"]:
                await self._send_error(player_id, result["error"])
                return

            # Broadcast that game started
            await self._connections.broadcast_to_room(
                room_code,
                create_message(
                    ServerEvent.GAME_STARTED,
                    phase=result["phase"],
                    host_id=room.host_id,
                ),
            )

    async def _handle_start_round(self, player_id: str, data: dict[str, Any]) -> None:
        """Handle start round request (multiplayer only, host only)."""
        result = await self._get_player_room(player_id)
        if not result:
            return
        room_code, room = result

        clubs_per_round = data.get("clubs_per_round", 2)
        try:
            clubs_per_round = int(clubs_per_round)
        except (ValueError, TypeError):
            clubs_per_round = 2

        self._room_manager.touch_room(room_code)

        # Serialize all state mutations with per-room lock
        async with room.get_lock():
            result = self._game_manager.start_round(room, player_id, clubs_per_round)

            if not result["success"]:
                # Check if selection failed
                if result.get("error", "").startswith("Could not find"):
                    # Clear pool and reset player submissions so they can try again
                    room.game_state.club_pool = []
                    for player in room.players:
                        player.submitted_club = None

                    await self._connections.broadcast_to_room(
                        room_code,
                        create_message(
                            ServerEvent.SELECTION_FAILED,
                            error=result["error"],
                            pool_cleared=True,
                        ),
                    )
                else:
                    await self._send_error(player_id, result["error"])
                return

            # Broadcast guessing started
            await self._connections.broadcast_to_room(
                room_code,
                create_message(
                    ServerEvent.GUESSING_STARTED,
                    clubs=result["clubs"],
                    club_info=result.get("club_info"),
                    club_submitters=result.get("club_submitters"),
                    deadline=result["deadline"],
                    valid_count=result["valid_count"],
                    fallback_club_count=result.get("fallback_club_count"),
                ),
            )
            # Start timeout task
            self._start_timeout_task(room_code, result["deadline"])

    # ------------------------------------------------------------------
    # NBA Grid handlers
    # ------------------------------------------------------------------

    async def _handle_start_grid_game(self, player_id: str, _data: dict[str, Any]) -> None:
        """Host starts the grid: server generates grid, assigns symbols, kicks off clock."""
        result = await self._get_player_room(player_id)
        if not result:
            return
        room_code, room = result
        self._room_manager.touch_room(room_code)

        async with room.get_lock():
            res = self._game_manager.start_grid_game(room, player_id)
            if not res["success"]:
                await self._send_error(player_id, res["error"])
                return

            await self._connections.broadcast_to_room(
                room_code,
                create_message(
                    ServerEvent.GRID_GAME_STARTED,
                    grid=res["grid"],
                    row_categories=res["row_categories"],
                    col_categories=res["col_categories"],
                    player_symbols=res["player_symbols"],
                    current_turn_player_id=res["current_turn_player_id"],
                    turn_deadline=res["turn_deadline"],
                ),
            )
            self._start_grid_clock_task(room_code)

    async def _handle_submit_grid_guess(self, player_id: str, data: dict[str, Any]) -> None:
        """Player submits a guess for a specific cell."""
        result = await self._get_player_room(player_id)
        if not result:
            return
        room_code, room = result
        self._room_manager.touch_room(room_code)

        try:
            row = int(data.get("row", -1))
            col = int(data.get("col", -1))
        except (TypeError, ValueError):
            await self._send_error(player_id, "Invalid cell coordinates")
            return

        guess = str(data.get("player_name", "")).strip()[:MAX_GUESS_LENGTH]
        if not guess:
            await self._send_error(player_id, "Invalid guess")
            return

        async with room.get_lock():
            res = self._game_manager.submit_grid_guess(room, player_id, row, col, guess)
            if not res["success"]:
                await self._send_error(player_id, res["error"])
                return

            if res.get("game_ended"):
                self._cancel_grid_clock_task(room_code)
                await self._connections.broadcast_to_room(
                    room_code,
                    create_message(
                        ServerEvent.GRID_CELL_MARKED,
                        row=res["row"],
                        col=res["col"],
                        player_id=res["player_id"],
                        symbol=res["symbol"],
                        player_name=res["player_name"],
                        player_image_url=res.get("player_image_url"),
                        turn_deadline=res.get("turn_deadline"),
                    ),
                )
                await self._connections.broadcast_to_room(
                    room_code,
                    create_message(
                        ServerEvent.GRID_GAME_ENDED,
                        end_reason=res["end_reason"],
                        winner_id=res.get("winner_id"),
                        scores={p.id: p.score for p in room.players},
                    ),
                )
                return

            if res["correct"]:
                await self._connections.broadcast_to_room(
                    room_code,
                    create_message(
                        ServerEvent.GRID_CELL_MARKED,
                        row=res["row"],
                        col=res["col"],
                        player_id=res["player_id"],
                        symbol=res["symbol"],
                        player_name=res["player_name"],
                        player_image_url=res.get("player_image_url"),
                        turn_deadline=res["turn_deadline"],
                        next_turn_player_id=res["next_turn"],
                    ),
                )
            else:
                await self._connections.broadcast_to_room(
                    room_code,
                    create_message(
                        ServerEvent.GRID_TURN_PASSED,
                        reason="wrong",
                        player_id=player_id,
                        row=res["row"],
                        col=res["col"],
                        guess=res["guess"],
                        turn_deadline=res["turn_deadline"],
                        next_turn_player_id=res["next_turn"],
                    ),
                )

            # Fresh 60s on new turn — restart the watcher.
            self._start_grid_clock_task(room_code)

    async def _handle_skip_grid_turn(self, player_id: str, _data: dict[str, Any]) -> None:
        """Player skips their turn."""
        result = await self._get_player_room(player_id)
        if not result:
            return
        room_code, room = result
        self._room_manager.touch_room(room_code)

        async with room.get_lock():
            res = self._game_manager.skip_grid_turn(room, player_id)
            if not res["success"]:
                await self._send_error(player_id, res["error"])
                return

            await self._connections.broadcast_to_room(
                room_code,
                create_message(
                    ServerEvent.GRID_TURN_PASSED,
                    reason="skip",
                    player_id=player_id,
                    turn_deadline=res["turn_deadline"],
                    next_turn_player_id=res["next_turn"],
                ),
            )
            self._start_grid_clock_task(room_code)

    async def _handle_propose_grid_draw(self, player_id: str, _data: dict[str, Any]) -> None:
        """Player proposes a draw — opponent must accept/decline."""
        result = await self._get_player_room(player_id)
        if not result:
            return
        room_code, room = result
        self._room_manager.touch_room(room_code)

        async with room.get_lock():
            res = self._game_manager.propose_grid_draw(room, player_id)
            if not res["success"]:
                await self._send_error(player_id, res["error"])
                return

            await self._connections.broadcast_to_room(
                room_code,
                create_message(
                    ServerEvent.GRID_DRAW_PROPOSED,
                    proposer_id=res["proposer_id"],
                ),
            )

    async def _handle_respond_grid_draw(self, player_id: str, data: dict[str, Any]) -> None:
        """Opponent accepts or declines a draw proposal."""
        result = await self._get_player_room(player_id)
        if not result:
            return
        room_code, room = result
        self._room_manager.touch_room(room_code)

        accept = bool(data.get("accept", False))

        async with room.get_lock():
            res = self._game_manager.respond_grid_draw(room, player_id, accept)
            if not res["success"]:
                await self._send_error(player_id, res["error"])
                return

            await self._connections.broadcast_to_room(
                room_code,
                create_message(
                    ServerEvent.GRID_DRAW_RESOLVED,
                    accepted=res["accepted"],
                    ended=res["ended"],
                ),
            )

            if res["ended"]:
                self._cancel_grid_clock_task(room_code)
                await self._connections.broadcast_to_room(
                    room_code,
                    create_message(
                        ServerEvent.GRID_GAME_ENDED,
                        end_reason=res["end_reason"],
                        winner_id=res.get("winner_id"),
                        scores={p.id: p.score for p in room.players},
                    ),
                )

    def _start_grid_clock_task(self, room_code: str) -> None:
        """Start a background task that auto-skips when the per-turn 60s elapses.

        Timer expiry just passes the turn (with reason='timeout') and grants the
        opponent a fresh 60s — it does NOT end the game. The task reschedules
        itself for the next turn.
        """
        self._cancel_grid_clock_task(room_code)

        room = self._room_manager.get_room(room_code)
        if room is None:
            return
        gs = room.game_state
        if gs.turn_deadline is None or gs.current_turn_player_id is None:
            return
        expiring_player = gs.current_turn_player_id
        remaining = max(0.0, gs.turn_deadline - time.time())

        async def watch():
            try:
                await asyncio.sleep(remaining)
                room = self._room_manager.get_room(room_code)
                if not room:
                    return
                async with room.get_lock():
                    if room.game_state.phase != GamePhase.GUESSING:
                        return
                    if room.mode != GameMode.NBA_GRID:
                        return
                    res = self._game_manager.grid_timer_expired(room, expiring_player)
                    if not res.get("success"):
                        return
                    await self._connections.broadcast_to_room(
                        room_code,
                        create_message(
                            ServerEvent.GRID_TURN_PASSED,
                            reason="timeout",
                            player_id=res["player_id"],
                            turn_deadline=res["turn_deadline"],
                            next_turn_player_id=res["next_turn"],
                        ),
                    )
            finally:
                self._timeout_tasks.pop(room_code, None)
                # Reschedule for the new turn — the game continues.
                r2 = self._room_manager.get_room(room_code)
                if (
                    r2 is not None
                    and r2.mode == GameMode.NBA_GRID
                    and r2.game_state.phase == GamePhase.GUESSING
                ):
                    self._start_grid_clock_task(room_code)

        self._timeout_tasks[room_code] = asyncio.create_task(watch())

    def _cancel_grid_clock_task(self, room_code: str) -> None:
        """Alias for symmetry with _start_grid_clock_task."""
        self._cancel_timeout_task(room_code)

    async def _handle_disconnect(self, player_id: str) -> None:
        """Handle player disconnect."""
        room_code = self._connections.disconnect(player_id)
        if room_code:
            # Check if this player was the host before leaving
            room_before = self._room_manager.get_room(room_code)
            was_host = room_before and room_before.host_id == player_id

            room, removed_player = self._room_manager.leave_room(room_code, player_id)
            if removed_player and room:
                # Include updated players list and new host_id if host changed
                message_data = {
                    "player_id": player_id,
                    "phase": room.game_state.phase.value,
                    "players": [
                        {"id": p.id, "name": p.name, "score": p.score} for p in room.players
                    ],
                }
                if was_host and room.host_id:
                    message_data["new_host_id"] = room.host_id

                await self._connections.broadcast_to_room(
                    room_code,
                    create_message(ServerEvent.PLAYER_LEFT, **message_data),
                )
            # Cancel any pending timeout
            self._cancel_timeout_task(room_code)

    async def _send_error(self, player_id: str, message: str) -> None:
        """Send an error message to a player."""
        await self._connections.send_to_player(
            player_id,
            create_message(ServerEvent.ERROR, message=message),
        )

    async def _get_player_room(self, player_id: str) -> tuple[str, Room] | None:
        """Get room for player, sending error if not found. Returns (room_code, room) or None."""
        room_code = self._connections.get_room(player_id)
        if not room_code:
            await self._send_error(player_id, "Not in a room")
            return None
        room = self._room_manager.get_room(room_code)
        if not room:
            await self._send_error(player_id, "Room not found")
            return None
        return room_code, room

    async def _leave_current_room(self, player_id: str) -> None:
        """Leave current room if in one (cleanup before joining/creating another)."""
        current_room_code = self._connections.get_room(player_id)
        if current_room_code:
            # Check if this player was the host before leaving
            room_before = self._room_manager.get_room(current_room_code)
            was_host = room_before and room_before.host_id == player_id

            room, removed_player = self._room_manager.leave_room(current_room_code, player_id)
            if removed_player and room:
                # Include updated players list and new host_id if host changed
                message_data = {
                    "player_id": player_id,
                    "phase": room.game_state.phase.value,
                    "players": [
                        {"id": p.id, "name": p.name, "score": p.score} for p in room.players
                    ],
                }
                if was_host and room.host_id:
                    message_data["new_host_id"] = room.host_id

                await self._connections.broadcast_to_room(
                    current_room_code,
                    create_message(ServerEvent.PLAYER_LEFT, **message_data),
                )
            self._cancel_timeout_task(current_room_code)

    def _start_timeout_task(self, room_code: str, deadline: float) -> None:
        """Start a task to handle round timeout."""
        delay = max(0, deadline - time.time())

        async def timeout_callback():
            try:
                await asyncio.sleep(delay)
                room = self._room_manager.get_room(room_code)
                if not room:
                    return

                # Serialize with per-room lock to prevent race with guess submission
                async with room.get_lock():
                    # Re-check phase inside lock - it may have changed
                    if room.game_state.phase == GamePhase.GUESSING:
                        result = self._game_manager.end_round_timeout(room)
                        if result["success"]:
                            # Get player details with images
                            data_service = self._game_manager._get_data_service(room.sport)
                            valid_answer_details = data_service.get_player_details(
                                result["valid_answers"]
                            )

                            await self._connections.broadcast_to_room(
                                room_code,
                                create_message(
                                    ServerEvent.ROUND_ENDED,
                                    winner_id=None,
                                    winning_answer=None,
                                    winning_answer_image=None,
                                    valid_answers=result["valid_answers"],
                                    valid_answer_details=valid_answer_details,
                                    scores={p.id: p.score for p in room.players},
                                ),
                            )
            finally:
                # Clean up completed task from dict
                self._timeout_tasks.pop(room_code, None)

        self._cancel_timeout_task(room_code)
        self._timeout_tasks[room_code] = asyncio.create_task(timeout_callback())

    def _cancel_timeout_task(self, room_code: str) -> None:
        """Cancel a pending timeout task."""
        task = self._timeout_tasks.pop(room_code, None)
        if task:
            task.cancel()
