"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from sports_trivia.config import settings
from sports_trivia.services.game_manager import GameManager
from sports_trivia.services.room_manager import RoomManager
from sports_trivia.websocket.handlers import ConnectionManager, WebSocketHandler

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize services (before lifespan so they're available)
room_manager = RoomManager()
game_manager = GameManager()
connection_manager = ConnectionManager()
ws_handler = WebSocketHandler(room_manager, game_manager, connection_manager)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    # Startup: start background tasks
    logger.info("Starting room cleanup task...")
    await room_manager.start_cleanup_task()
    yield
    # Shutdown: stop background tasks
    logger.info("Stopping room cleanup task...")
    await room_manager.stop_cleanup_task()


# Initialize FastAPI app
app = FastAPI(
    title="Sports Trivia 1v1",
    description="A 1v1 multiplayer sports trivia game",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "rooms": room_manager.room_count,
    }


# -----------------------------------------------------------------------------
# API endpoints for club validation and search
# -----------------------------------------------------------------------------
from sports_trivia.models import Sport  # noqa: E402
from sports_trivia.services import get_service  # noqa: E402


@app.get("/api/clubs/{sport}")
async def get_clubs(sport: str):
    """Get all clubs for a sport (for autocomplete)."""
    try:
        sport_enum = Sport(sport.lower())
    except ValueError:
        return {"error": f"Invalid sport: {sport}. Use 'nba' or 'soccer'"}

    service = get_service(sport_enum)
    clubs = service.get_all_clubs()
    return {"sport": sport, "clubs": clubs}


@app.get("/api/clubs/{sport}/validate")
async def validate_club(sport: str, name: str):
    """Validate a club name and return normalized form if valid."""
    try:
        sport_enum = Sport(sport.lower())
    except ValueError:
        return {"valid": False, "error": f"Invalid sport: {sport}"}

    if not name or len(name.strip()) < 2:
        return {"valid": False, "error": "Name too short"}

    service = get_service(sport_enum)
    is_valid = service.validate_club(name)

    if is_valid:
        normalized = service.normalize_club_name(name)
        club_info = service.get_club_info(name)
        return {
            "valid": True,
            "normalized_name": normalized,
            "club": club_info,
        }
    else:
        return {"valid": False, "error": f"Club '{name}' not found"}


# -----------------------------------------------------------------------------
# Image proxy endpoint for CORS bypass
# -----------------------------------------------------------------------------
ALLOWED_IMAGE_DOMAINS = [
    "img.a.transfermarkt.technology",
    "cdn.nba.com",
    "www.thesportsdb.com",
    "r2.thesportsdb.com",
]


@app.get("/api/image/proxy")
async def proxy_image(url: str):
    """Proxy external images to bypass CORS restrictions."""
    parsed = urlparse(url)
    if parsed.netloc not in ALLOWED_IMAGE_DOMAINS:
        return Response(status_code=403, content="Domain not allowed")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, follow_redirects=True, timeout=10.0)
            if response.status_code != 200:
                return Response(status_code=response.status_code)

            return Response(
                content=response.content,
                media_type=response.headers.get("content-type", "image/jpeg"),
            )
        except httpx.RequestError:
            return Response(status_code=502, content="Failed to fetch image")


# Static files directory (checked early to determine behavior)
STATIC_DIR = Path(__file__).parent.parent / "static"


@app.get("/")
async def root():
    """Root endpoint - serves frontend if available, otherwise API info."""
    if STATIC_DIR.exists():
        return FileResponse(STATIC_DIR / "index.html")
    return {
        "name": "Clutch",
        "version": "0.1.0",
        "websocket": "/ws",
        "health": "/health",
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for game connections."""
    await ws_handler.handle_connection(websocket)


# Static files for frontend (must be after API routes)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve Flutter web app (SPA fallback)."""
        # Try to serve the exact file
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        # Fallback to index.html for SPA routing
        return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "sports_trivia.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
