"""Optional auto-labelers (heuristics or LLM)."""
import asyncio
import logging
from typing import Dict, List, Optional

import httpx

from semantix.config import settings
from semantix.store.redis import r_get_item

logger = logging.getLogger(__name__)


async def auto_label(item_id: str) -> Dict[str, int]:
    """
    Auto-label an item using LLM or heuristics.
    
    Args:
        item_id: Item ID
        
    Returns:
        Dictionary of label: score pairs
    """
    if not settings.AUTO_LABEL_ENABLED:
        return {}
    
    # Get item
    item = await r_get_item(item_id)
    if not item:
        return {}
    
    text = item.text
    
    # Use LLM if configured
    if settings.LLM_PROVIDER == "ollama":
        return await auto_label_ollama(text)
    elif settings.LLM_PROVIDER == "openai":
        return await auto_label_openai(text)
    else:
        # Fallback to heuristics
        return await auto_label_heuristic(text)


async def auto_label_ollama(text: str) -> Dict[str, int]:
    """Auto-label using Ollama LLM."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": f"""Analyze the following text and provide labels in JSON format:
{{"positive": 1 or 0, "negative": 1 or 0, "quality": 1-5}}

Text:
{text[:2000]}""",
                    "stream": False,
                },
            )
            
            if response.status_code == 200:
                result = response.json()
                # Parse response (simplified - would need proper JSON extraction)
                # For now, return basic heuristic
                return await auto_label_heuristic(text)
    except Exception as e:
        logger.error(f"Error in Ollama auto-labeling: {e}", exc_info=True)
    
    return {}


async def auto_label_openai(text: str) -> Dict[str, int]:
    """Auto-label using OpenAI API."""
    # Placeholder - would need OpenAI API key
    logger.warning("OpenAI auto-labeling not yet implemented")
    return {}


async def auto_label_heuristic(text: str) -> Dict[str, int]:
    """
    Simple heuristic auto-labeling.
    
    Args:
        text: Text to label
        
    Returns:
        Dictionary of label: score pairs
    """
    labels: Dict[str, int] = {}
    
    # Simple keyword-based heuristics
    text_lower = text.lower()
    
    # Positive/negative sentiment (very basic)
    positive_words = ["good", "great", "excellent", "amazing", "wonderful", "love", "best"]
    negative_words = ["bad", "terrible", "awful", "hate", "worst", "poor", "fail"]
    
    pos_count = sum(1 for word in positive_words if word in text_lower)
    neg_count = sum(1 for word in negative_words if word in text_lower)
    
    if pos_count > neg_count:
        labels["positive"] = 1
    elif neg_count > pos_count:
        labels["negative"] = 1
    
    # Quality based on length and structure
    if len(text) > 500:
        labels["quality"] = 2
    elif len(text) > 200:
        labels["quality"] = 1
    else:
        labels["quality"] = 0
    
    return labels

