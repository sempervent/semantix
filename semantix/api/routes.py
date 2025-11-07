"""FastAPI REST endpoints."""
import logging
from typing import Optional

import orjson
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import ORJSONResponse

from semantix.config import settings
from semantix.ingest.parsers import parse_text
from semantix.labeling.votes import cast_vote, moderate_item
from semantix.store.redis import (
    r_get_approved_ids,
    r_get_item,
    r_get_quality,
    r_get_status,
    r_get_votes,
    r_get_voters,
    r_get_metrics,
    r_index_pending,
    r_set_item,
    r_stream_ingest,
)
from semantix.store.schema import (
    IngestRequest,
    IngestResponse,
    ItemResponse,
    ModerateRequest,
    TrainRequest,
    VoteRequest,
    VoteResponse,
    MetricsResponse,
)
from semantix.utils.hashing import sha256_bytes

logger = logging.getLogger(__name__)

api_router = APIRouter()


@api_router.post("/ingest", response_model=IngestResponse)
async def ingest(request: IngestRequest) -> IngestResponse:
    """Accept text or file; returns {id}."""
    if request.text:
        # Parse text
        text, meta = await parse_text(request.text, request.source)
    else:
        raise HTTPException(status_code=400, detail="text field is required")
    
    # Hash content
    item_id = sha256_bytes(text.encode("utf-8"))
    
    # Store in Redis
    created = await r_set_item(item_id, text, meta)
    
    if created:
        # Add to pending index
        await r_index_pending(item_id)
        
        # Add to ingest stream
        await r_stream_ingest(item_id)
    
    return IngestResponse(id=item_id, created=created)


@api_router.post("/ingest/file")
async def ingest_file(file: UploadFile = File(...)) -> IngestResponse:
    """Accept file upload; returns {id}."""
    # Read file content
    content = await file.read()
    
    # Check size
    if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large (max {settings.MAX_FILE_SIZE_MB}MB)")
    
    # Decode as text (basic - would need proper encoding detection)
    try:
        text_str = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be text-encoded")
    
    # Parse text
    text, meta = await parse_text(text_str, f"upload:{file.filename}")
    
    # Hash content
    item_id = sha256_bytes(text.encode("utf-8"))
    
    # Store in Redis
    created = await r_set_item(item_id, text, meta)
    
    if created:
        # Add to pending index
        await r_index_pending(item_id)
        
        # Add to ingest stream
        await r_stream_ingest(item_id)
    
    return IngestResponse(id=item_id, created=created)


@api_router.get("/item/{item_id}", response_model=ItemResponse)
async def get_item(item_id: str) -> ItemResponse:
    """Get item payload + votes + status."""
    # Get item
    item = await r_get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Get votes
    votes = await r_get_votes(item_id)
    
    # Get quality
    quality = await r_get_quality(item_id)
    
    # Get status
    status = await r_get_status(item_id)
    
    # Get voters
    voters = await r_get_voters(item_id)
    
    return ItemResponse(
        item=item,
        votes=votes,
        quality=quality,
        status=status,
        voters=voters,
    )


@api_router.post("/vote/{item_id}", response_model=VoteResponse)
async def vote(item_id: str, request: VoteRequest) -> VoteResponse:
    """Cast a vote: {label:"topic_x", delta:+1} or {quality:+1}."""
    # Verify item exists
    item = await r_get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Cast vote
    status = await cast_vote(
        item_id=item_id,
        voter=request.voter,
        label=request.label,
        delta=request.delta,
        quality=request.quality,
    )
    
    # Get updated votes
    votes = await r_get_votes(item_id)
    quality = await r_get_quality(item_id)
    
    return VoteResponse(
        id=item_id,
        status=status,
        votes=votes,
        quality=quality,
    )


@api_router.post("/moderate/{item_id}")
async def moderate_item_route(item_id: str, request: ModerateRequest) -> dict:
    """Admin override: {action:"approve"|"reject"}."""
    # Verify item exists
    item = await r_get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Moderate
    from semantix.labeling.votes import moderate_item as moderate_item_func
    status = await moderate_item_func(item_id, request.action)
    
    return {"id": item_id, "status": status}


@api_router.post("/train/kick")
async def train_kick(request: TrainRequest) -> dict:
    """Enqueue training run with filters."""
    # Get approved IDs
    approved_ids = await r_get_approved_ids()
    
    # Apply filters (simplified - would need proper filtering)
    filtered_ids = approved_ids
    
    if request.filter_label:
        # Filter by label (would need to check votes)
        filtered_ids = approved_ids  # Placeholder
    
    # Limit by target size
    if request.target_size:
        filtered_ids = filtered_ids[: request.target_size]
    
    # Enqueue training job (would use Arq here)
    # For now, return job info
    return {
        "job_id": "train_001",
        "item_count": len(filtered_ids),
        "status": "queued",
    }


@api_router.get("/metrics", response_model=MetricsResponse)
async def metrics() -> MetricsResponse:
    """Get counts, queue depth, throughput."""
    metrics_data = await r_get_metrics()
    return MetricsResponse(**metrics_data)


@api_router.get("/items")
async def list_items(
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """List items with optional status filter."""
    if status == "pending":
        from semantix.store.redis import r_get_pending_ids
        ids = await r_get_pending_ids()
    elif status == "approved":
        ids = await r_get_approved_ids()
    else:
        # Get all (would need full scan in production)
        ids = await r_get_approved_ids()
    
    # Paginate
    ids = ids[offset : offset + limit]
    
    # Get items
    items = []
    for item_id in ids:
        item = await r_get_item(item_id)
        if item:
            votes = await r_get_votes(item_id)
            quality = await r_get_quality(item_id)
            status_val = await r_get_status(item_id)
            
            items.append({
                "id": item_id,
                "source": item.source,
                "status": status_val,
                "quality": quality,
                "votes": votes,
                "text_preview": item.text[:200] + "..." if len(item.text) > 200 else item.text,
            })
    
    return {"items": items, "total": len(ids), "limit": limit, "offset": offset}

