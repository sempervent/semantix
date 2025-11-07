"""Async directory watcher for /input."""
import asyncio
import logging
from pathlib import Path

from watchfiles import awatch

from semantix.config import settings
from semantix.ingest.parsers import parse_file
from semantix.store.redis import r_index_pending, r_set_item, r_stream_ingest
from semantix.utils.hashing import sha256_bytes

logger = logging.getLogger(__name__)


async def start_watcher() -> None:
    """Start watching the input directory for new/changed files."""
    input_dir = Path(settings.INPUT_DIR)
    input_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Starting file watcher for {input_dir}")
    
    # Process existing files on startup
    for file_path in input_dir.rglob("*"):
        if file_path.is_file():
            try:
                await process_file(file_path)
            except Exception as e:
                logger.error(f"Error processing existing file {file_path}: {e}", exc_info=True)
    
    # Watch for changes
    async for changes in awatch(input_dir):
        for change_type, path_str in changes:
            path = Path(path_str)
            
            # Only process file additions and modifications
            if change_type in (1, 2) and path.is_file():  # 1=added, 2=modified
                try:
                    await process_file(path)
                except Exception as e:
                    logger.error(f"Error processing file {path}: {e}", exc_info=True)


async def process_file(file_path: Path) -> None:
    """
    Process a single file: parse, hash, store in Redis.
    
    Args:
        file_path: Path to file to process
    """
    # Parse file
    text, meta = await parse_file(file_path)
    
    if not text or not meta:
        logger.debug(f"Skipping file {file_path}: could not parse or empty")
        return
    
    # Hash content
    item_id = sha256_bytes(text.encode("utf-8"))
    
    # Store in Redis (returns True if newly created)
    created = await r_set_item(item_id, text, meta)
    
    if created:
        # Add to pending index
        await r_index_pending(item_id)
        
        # Add to ingest stream
        await r_stream_ingest(item_id)
        
        logger.info(f"Ingested new item: {item_id} from {file_path}")
    else:
        logger.debug(f"Item {item_id} already exists, skipping")

