import asyncio
import json
import logging
from collections.abc import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

# Global set of connected websocket clients
connected_clients: set[WebSocket] = set()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    logger.info("WebSocket client connected. Total clients: %d", len(connected_clients))

    try:
        while True:
            # Keep connection alive; handle incoming messages if needed
            data = await websocket.receive_text()
            # Client can send ping/pong or subscribe to specific events
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
        logger.info("WebSocket client disconnected. Total clients: %d", len(connected_clients))
    except Exception:
        connected_clients.discard(websocket)
        logger.exception("WebSocket error")


async def broadcast(event_type: str, data: dict):
    """Broadcast an event to all connected WebSocket clients."""
    if not connected_clients:
        return

    message = json.dumps({"type": event_type, "data": data})
    disconnected = set()

    for client in connected_clients:
        try:
            await client.send_text(message)
        except Exception:
            disconnected.add(client)

    for client in disconnected:
        connected_clients.discard(client)


def broadcast_sync(event_type: str, data: dict):
    """Fire-and-forget broadcast from synchronous context (e.g., Celery tasks).
    Uses Redis pub/sub to communicate with the async FastAPI process."""
    import redis
    from app.config import settings

    r = redis.Redis.from_url(settings.redis_url)
    message = json.dumps({"type": event_type, "data": data})
    r.publish("hunter:ws_broadcast", message)


async def ws_listener():
    """Background task to listen for Redis pub/sub messages and broadcast to WebSocket clients."""
    import redis.asyncio as aioredis
    from app.config import settings

    r = aioredis.from_url(settings.redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe("hunter:ws_broadcast")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                event_type = data.get("type", "update")
                event_data = data.get("data", {})
                await broadcast(event_type, event_data)
    except Exception:
        logger.exception("WebSocket Redis listener error")
    finally:
        await pubsub.unsubscribe("hunter:ws_broadcast")
        await r.aclose()
