"""WebSocket endpoints for live updates."""
import asyncio
import json
import logging
from typing import Set

import aioredis
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from semantix.config import settings
from semantix.store.redis import CHANNEL_EVENTS, get_redis

logger = logging.getLogger(__name__)

# Active WebSocket connections
active_connections: Set[WebSocket] = set()


async def ws_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for live updates."""
    await websocket.accept()
    active_connections.add(websocket)
    
    logger.info(f"WebSocket connected: {websocket.client}")
    
    # Get Redis connection
    r = await get_redis()
    
    # Create pubsub subscriber
    pubsub = r.pubsub()
    await pubsub.subscribe(CHANNEL_EVENTS)
    
    # Send initial snapshot
    try:
        from semantix.store.redis import r_get_metrics
        
        metrics = await r_get_metrics()
        snapshot = {
            "type": "snapshot",
            "metrics": metrics,
        }
        await send_websocket_message(websocket, snapshot)
    except Exception as e:
        logger.error(f"Error sending snapshot: {e}", exc_info=True)
    
    # Task to listen to Redis pub/sub
    listen_task = asyncio.create_task(listen_redis_events(pubsub, websocket))
    
    try:
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for message from client (with timeout)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                # Handle client messages (e.g., ping/pong)
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await send_websocket_message(websocket, {"type": "pong"})
                except json.JSONDecodeError:
                    pass
                    
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                await send_websocket_message(websocket, {"type": "ping"})
            except WebSocketDisconnect:
                break
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        # Cleanup
        listen_task.cancel()
        try:
            await listen_task
        except asyncio.CancelledError:
            pass
        
        await pubsub.unsubscribe(CHANNEL_EVENTS)
        await pubsub.close()
        active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected: {websocket.client}")


async def listen_redis_events(pubsub: aioredis.client.PubSub, websocket: WebSocket) -> None:
    """Listen to Redis pub/sub and forward to WebSocket."""
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            
            if message and message["type"] == "message":
                try:
                    # Parse event
                    event_data = json.loads(message["data"])
                    
                    # Send to WebSocket
                    await send_websocket_message(websocket, event_data)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Error processing Redis event: {e}", exc_info=True)
                    
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(f"Error in Redis event listener: {e}", exc_info=True)


async def send_websocket_message(websocket: WebSocket, message: dict) -> None:
    """
    Send message to WebSocket with backpressure handling.
    
    Args:
        websocket: WebSocket connection
        message: Message dict to send
    """
    if websocket.client_state != WebSocketState.CONNECTED:
        return
    
    try:
        # Serialize message
        text = json.dumps(message)
        
        # Send with timeout (backpressure)
        await asyncio.wait_for(websocket.send_text(text), timeout=settings.WS_SEND_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning(f"WebSocket send timeout, dropping message: {message.get('type')}")
    except Exception as e:
        logger.error(f"Error sending WebSocket message: {e}", exc_info=True)


async def broadcast_event(event: dict) -> None:
    """Broadcast event to all active WebSocket connections."""
    if not active_connections:
        return
    
    # Serialize once
    text = json.dumps(event)
    
    # Send to all connections
    disconnected = set()
    for websocket in active_connections:
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await asyncio.wait_for(websocket.send_text(text), timeout=settings.WS_SEND_TIMEOUT)
            else:
                disconnected.add(websocket)
        except (asyncio.TimeoutError, Exception):
            disconnected.add(websocket)
    
    # Remove disconnected connections
    active_connections.difference_update(disconnected)

