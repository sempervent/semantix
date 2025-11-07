"""Vote logic and threshold checking."""
import logging
from typing import Optional

import aioredis

from semantix.config import settings
from semantix.store.redis import (
    CHANNEL_EVENTS,
    INDEX_APPROVED,
    KEY_STATUS,
    KEY_VOTERS,
    KEY_VOTES,
    STREAM_APPROVED,
    get_redis,
    r_index_approved,
    r_set_status,
)

logger = logging.getLogger(__name__)


async def cast_vote(item_id: str, voter: str, label: Optional[str] = None, delta: int = 1, quality: Optional[int] = None) -> str:
    """
    Cast a vote for an item.
    
    Args:
        item_id: Item ID (SHA256 hash)
        voter: Voter identifier
        label: Optional label name (e.g., "positive", "negative", "topic_x")
        delta: Vote delta (+1 or -1)
        quality: Optional quality delta (+1 or -1)
        
    Returns:
        New status: "voting", "approved", or "rejected"
    """
    r = await get_redis()
    
    # Use pipeline for atomicity
    pipe = r.pipeline()
    
    # Track voter (to avoid duplicates if needed)
    pipe.sadd(f"{KEY_VOTERS}{item_id}", voter)
    
    # Increment label vote
    if label:
        pipe.hincrby(f"{KEY_VOTES}{item_id}", f"label:{label}", delta)
    
    # Increment quality
    if quality is not None:
        pipe.hincrby(f"{KEY_VOTES}{item_id}", "quality", quality)
    else:
        # Ensure quality field exists
        pipe.hincrby(f"{KEY_VOTES}{item_id}", "quality", 0)
    
    await pipe.execute()
    
    # Check threshold
    return await check_threshold(item_id, r)


async def check_threshold(item_id: str, r: aioredis.Redis) -> str:
    """
    Check if item meets approval threshold.
    
    Threshold rule:
    approved if sum(label:positive) - sum(label:negative) >= VOTE_THRESHOLD && quality >= QUALITY_MIN
    
    Args:
        item_id: Item ID
        r: Redis connection
        
    Returns:
        Status: "voting", "approved", or "rejected"
    """
    # Get all votes
    votes = await r.hgetall(f"{KEY_VOTES}{item_id}")
    
    # Calculate score: sum of positive labels minus negative labels
    score = 0
    for key, value in votes.items():
        if key.startswith("label:"):
            score += int(value)
    
    # Get quality
    quality = int(votes.get("quality", 0))
    
    # Check threshold
    if score >= settings.VOTE_THRESHOLD and quality >= settings.QUALITY_MIN:
        # Approve
        await r_set_status(item_id, "approved")
        await r_index_approved(item_id)
        await r.xadd(STREAM_APPROVED, {"id": item_id})
        
        # Publish event
        event = f'{{"type":"approved","id":"{item_id}"}}'
        await r.publish(CHANNEL_EVENTS, event)
        
        logger.info(f"Item {item_id} approved: score={score}, quality={quality}")
        return "approved"
    
    # Still voting
    return "voting"


async def moderate_item(item_id: str, action: str) -> str:
    """
    Admin moderation: approve or reject an item.
    
    Args:
        item_id: Item ID
        action: "approve" or "reject"
        
    Returns:
        New status
    """
    r = await get_redis()
    
    if action == "approve":
        await r_set_status(item_id, "approved")
        await r_index_approved(item_id)
        await r.xadd(STREAM_APPROVED, {"id": item_id})
        
        event = f'{{"type":"approved","id":"{item_id}"}}'
        await r.publish(CHANNEL_EVENTS, event)
        
        logger.info(f"Item {item_id} manually approved")
        return "approved"
    
    elif action == "reject":
        await r_set_status(item_id, "rejected")
        
        event = f'{{"type":"rejected","id":"{item_id}"}}'
        await r.publish(CHANNEL_EVENTS, event)
        
        logger.info(f"Item {item_id} rejected")
        return "rejected"
    
    return await r.get(f"{KEY_STATUS}{item_id}") or "voting"

