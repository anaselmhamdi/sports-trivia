"""WebSocket module for real-time game communication."""

from sports_trivia.websocket.events import ClientEvent, ServerEvent
from sports_trivia.websocket.handlers import WebSocketHandler

__all__ = ["ClientEvent", "ServerEvent", "WebSocketHandler"]
