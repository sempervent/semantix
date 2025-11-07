"""Arq workers for training jobs."""
import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import Worker

from semantix.config import settings
from semantix.store.redis import CHANNEL_EVENTS, get_redis
from semantix.train.pipeline import build_dataset

logger = logging.getLogger(__name__)


async def train_job(ctx: Dict[str, Any], filter_label: Optional[str] = None, min_quality: int = 1, target_size: Optional[int] = None, out_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Training job: build dataset from approved items.
    
    Args:
        ctx: Arq context (contains Redis connection)
        filter_label: Optional label filter
        min_quality: Minimum quality score
        target_size: Optional target number of items
        out_dir: Output directory
        
    Returns:
        Job result dictionary
    """
    logger.info(f"Starting training job: filter_label={filter_label}, min_quality={min_quality}, target_size={target_size}")
    
    # Get Redis connection
    r = ctx.get("redis")
    if not r:
        r = await get_redis()
    
    # Publish start event
    await r.publish(CHANNEL_EVENTS, '{"type":"training:start"}')
    
    try:
        # Build dataset
        out_path = Path(out_dir) if out_dir else None
        files = await build_dataset(
            filter_label=filter_label,
            min_quality=min_quality,
            target_size=target_size,
            out_dir=out_path,
        )
        
        # Publish completion event
        result = {
            "status": "done",
            "files": [str(p) for p in files],
            "count": len(files),
        }
        
        await r.publish(CHANNEL_EVENTS, f'{{"type":"training:done","result":{str(result).replace(chr(39), chr(34))}}}')
        
        logger.info(f"Training job complete: {len(files)} files")
        
        return result
    
    except Exception as e:
        logger.error(f"Training job failed: {e}", exc_info=True)
        
        # Publish error event
        await r.publish(CHANNEL_EVENTS, f'{{"type":"training:error","error":"{str(e)}"}}')
        
        raise


class WorkerSettings:
    """Arq worker settings."""
    
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    functions = [train_job]
    max_jobs = 1  # One training job at a time
    job_timeout = 3600  # 1 hour timeout


async def main():
    """Run Arq worker."""
    worker = Worker(
        functions=WorkerSettings.functions,
        redis_settings=WorkerSettings.redis_settings,
        max_jobs=WorkerSettings.max_jobs,
        job_timeout=WorkerSettings.job_timeout,
    )
    await worker.async_run()


if __name__ == "__main__":
    asyncio.run(main())

