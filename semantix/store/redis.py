"""Redis store helpers and key schema."""
import json
from typing import Any, Dict, List, Optional

import aioredis
from semantix.config import settings
from semantix.store.schema import Item, ItemMeta


# Redis key prefixes
KEY_ITEM = "semx:item:"
KEY_VOTES = "semx:votes:"
KEY_VOTERS = "semx:voters:"
KEY_STATUS = "semx:status:"
STREAM_INGEST = "semx:stream:ingest"
STREAM_APPROVED = "semx:stream:approved"
STREAM_TRAINING = "semx:stream:training"
INDEX_PENDING = "semx:index:pending"
INDEX_APPROVED = "semx:index:approved"
CHANNEL_EVENTS = "semx:events"


_redis_pool: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Get Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = await aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            encoding="utf-8",
        )
    return _redis_pool


async def close_redis() -> None:
    """Close Redis connection pool."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.close()
        _redis_pool = None


# Item operations
async def r_set_item(item_id: str, text: str, meta: ItemMeta) -> bool:
    """
    Set item in Redis. Returns True if newly created, False if existed.
    
    Args:
        item_id: SHA256 hash of content
        text: Normalized text
        meta: Item metadata
        
    Returns:
        True if item was newly created, False if it already existed
    """
    r = await get_redis()
    item = Item(
        id=item_id,
        source=meta.source,
        created_at=meta.created_at,
        text=text,
        meta=meta,
    )
    key = f"{KEY_ITEM}{item_id}"
    exists = await r.exists(key)
    await r.set(key, item.model_dump_json())
    return not exists


async def r_get_item(item_id: str) -> Optional[Item]:
    """Get item from Redis."""
    r = await get_redis()
    key = f"{KEY_ITEM}{item_id}"
    data = await r.get(key)
    if not data:
        return None
    return Item.model_validate_json(data)


# Vote operations
async def r_get_votes(item_id: str) -> Dict[str, int]:
    """Get all votes for an item."""
    r = await get_redis()
    key = f"{KEY_VOTES}{item_id}"
    votes = await r.hgetall(key)
    return {k: int(v) for k, v in votes.items()}


async def r_get_quality(item_id: str) -> int:
    """Get quality score for an item."""
    votes = await r_get_votes(item_id)
    return votes.get("quality", 0)


async def r_get_voters(item_id: str) -> List[str]:
    """Get list of voters for an item."""
    r = await get_redis()
    key = f"{KEY_VOTERS}{item_id}"
    return list(await r.smembers(key))


# Status operations
async def r_get_status(item_id: str) -> str:
    """Get status of an item."""
    r = await get_redis()
    key = f"{KEY_STATUS}{item_id}"
    status = await r.get(key)
    return status or "voting"


async def r_set_status(item_id: str, status: str) -> None:
    """Set status of an item."""
    r = await get_redis()
    key = f"{KEY_STATUS}{item_id}"
    await r.set(key, status)


# Index operations
async def r_index_pending(item_id: str) -> None:
    """Add item to pending index."""
    r = await get_redis()
    await r.sadd(INDEX_PENDING, item_id)


async def r_index_approved(item_id: str) -> None:
    """Add item to approved index."""
    r = await get_redis()
    await r.sadd(INDEX_APPROVED, item_id)
    await r.srem(INDEX_PENDING, item_id)


async def r_get_pending_ids() -> List[str]:
    """Get all pending item IDs."""
    r = await get_redis()
    return list(await r.smembers(INDEX_PENDING))


async def r_get_approved_ids() -> List[str]:
    """Get all approved item IDs."""
    r = await get_redis()
    return list(await r.smembers(INDEX_APPROVED))


# Stream operations
async def r_stream_ingest(item_id: str) -> None:
    """Add item to ingest stream."""
    r = await get_redis()
    await r.xadd(STREAM_INGEST, {"id": item_id})


async def r_stream_approved(item_id: str) -> None:
    """Add item to approved stream."""
    r = await get_redis()
    await r.xadd(STREAM_APPROVED, {"id": item_id})


async def r_stream_training(data: Dict[str, Any]) -> None:
    """Add training progress to stream."""
    r = await get_redis()
    await r.xadd(STREAM_TRAINING, data)


# Metrics
async def r_get_metrics() -> Dict[str, Any]:
    """Get basic metrics from Redis."""
    r = await get_redis()
    
    total_items = await r.dbsize()  # Approximate
    pending = len(await r_get_pending_ids())
    approved = len(await r_get_approved_ids())
    
    # Count items by status
    status_keys = await r.keys(f"{KEY_STATUS}*")
    rejected = 0
    for key in status_keys:
        status = await r.get(key)
        if status == "rejected":
            rejected += 1
    
    return {
        "total_items": total_items,
        "pending_items": pending,
        "approved_items": approved,
        "rejected_items": rejected,
        "queue_depth": pending,
        "ingest_rate": 0.0,  # Would need time-series tracking
        "approval_rate": 0.0,  # Would need time-series tracking
    }

