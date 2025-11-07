"""Featureization and dataset writing pipeline."""
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Dict, Optional

import polars as pl
from semantix.config import settings
from semantix.store.redis import r_get_approved_ids, r_get_item, r_get_votes, r_stream_training

logger = logging.getLogger(__name__)


async def build_rows_stream(
    filter_label: Optional[str] = None,
    min_quality: int = 1,
    target_size: Optional[int] = None,
) -> AsyncIterator[Dict]:
    """
    Stream approved items as featureized rows.
    
    Args:
        filter_label: Optional label filter
        min_quality: Minimum quality score
        target_size: Optional target number of items
        
    Yields:
        Dictionary rows ready for DataFrame
    """
    # Get approved IDs
    approved_ids = await r_get_approved_ids()
    
    # Apply filters
    if filter_label:
        # Filter by label (would need to check votes)
        filtered_ids = []
        for item_id in approved_ids:
            votes = await r_get_votes(item_id)
            if f"label:{filter_label}" in votes and votes[f"label:{filter_label}"] > 0:
                filtered_ids.append(item_id)
        approved_ids = filtered_ids
    
    # Limit by target size
    if target_size:
        approved_ids = approved_ids[:target_size]
    
    logger.info(f"Processing {len(approved_ids)} approved items")
    
    # Process each item
    for idx, item_id in enumerate(approved_ids):
        try:
            # Get item
            item = await r_get_item(item_id)
            if not item:
                continue
            
            # Get votes
            votes = await r_get_votes(item_id)
            
            # Check quality
            quality = votes.get("quality", 0)
            if quality < min_quality:
                continue
            
            # Featureize (basic - could add tokenization, embeddings, etc.)
            row = {
                "id": item_id,
                "text": item.text,
                "source": item.source,
                "created_at": item.created_at,
                "quality": quality,
                "votes": str(votes),  # Serialize votes dict
                "meta_mime": item.meta.mime,
                "meta_bytes": item.meta.bytes,
            }
            
            # Add label columns
            for key, value in votes.items():
                if key.startswith("label:"):
                    label_name = key.replace("label:", "")
                    row[f"label_{label_name}"] = value
            
            yield row
            
            # Emit progress
            if (idx + 1) % 100 == 0:
                await r_stream_training({
                    "progress": idx + 1,
                    "total": len(approved_ids),
                    "status": "processing",
                })
                logger.info(f"Processed {idx + 1}/{len(approved_ids)} items")
        
        except Exception as e:
            logger.error(f"Error processing item {item_id}: {e}", exc_info=True)
            continue


async def write_chunk(df: pl.DataFrame, out_dir: Path, chunk_idx: int) -> Path:
    """
    Write a chunk of data to Parquet.
    
    Args:
        df: Polars DataFrame
        out_dir: Output directory
        chunk_idx: Chunk index
        
    Returns:
        Path to written file
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename
    timestamp = int(asyncio.get_running_loop().time() * 1000)
    filename = f"train-{timestamp}-{chunk_idx:04d}.parquet"
    path = out_dir / filename
    
    # Write Parquet
    df.write_parquet(str(path), row_group_size=100_000)
    
    logger.info(f"Wrote chunk {chunk_idx} to {path} ({len(df)} rows)")
    
    return path


async def build_dataset(
    filter_label: Optional[str] = None,
    min_quality: int = 1,
    target_size: Optional[int] = None,
    out_dir: Optional[Path] = None,
) -> list[Path]:
    """
    Build training dataset from approved items.
    
    Args:
        filter_label: Optional label filter
        min_quality: Minimum quality score
        target_size: Optional target number of items
        out_dir: Output directory (defaults to settings.ARTIFACTS_DIR)
        
    Returns:
        List of Parquet file paths
    """
    if out_dir is None:
        out_dir = Path(settings.ARTIFACTS_DIR)
    
    # Create timestamped directory
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dataset_dir = out_dir / timestamp
    dataset_dir.mkdir(parents=True, exist_ok=True)
    
    # Build DataFrame in chunks
    df = pl.DataFrame()
    chunk_idx = 0
    written_files = []
    
    async for row in build_rows_stream(filter_label, min_quality, target_size):
        # Add row to DataFrame
        row_df = pl.DataFrame([row])
        df = pl.concat([df, row_df], how="vertical_relaxed")
        
        # Write chunk when size threshold reached
        if len(df) >= settings.TRAINING_CHUNK_SIZE:
            path = await write_chunk(df, dataset_dir, chunk_idx)
            written_files.append(path)
            df = pl.DataFrame()
            chunk_idx += 1
    
    # Write final chunk if any remaining
    if len(df) > 0:
        path = await write_chunk(df, dataset_dir, chunk_idx)
        written_files.append(path)
    
    # Emit completion
    await r_stream_training({
        "status": "done",
        "files": [str(p) for p in written_files],
        "total_rows": sum(pl.read_parquet(str(p)).height for p in written_files),
    })
    
    logger.info(f"Dataset complete: {len(written_files)} files in {dataset_dir}")
    
    return written_files

