"""File parsers for text extraction."""
import asyncio
import mimetypes
from pathlib import Path
from typing import Optional, Tuple

import aiofiles
from semantix.store.schema import ItemMeta
from semantix.utils.textnorm import extract_plain_text, normalize_text

try:
    import magic
except ImportError:
    magic = None

try:
    from pdfminer.high_level import extract_text as pdf_extract
except ImportError:
    pdf_extract = None

try:
    from readability import Document
    import lxml.html
except ImportError:
    Document = None
    lxml = None


async def parse_file(file_path: Path) -> Tuple[Optional[str], Optional[ItemMeta]]:
    """
    Parse a file and extract normalized text.
    
    Args:
        file_path: Path to file
        
    Returns:
        Tuple of (normalized_text, ItemMeta) or (None, None) if parsing fails
    """
    try:
        # Get file size
        stat = file_path.stat()
        file_size = stat.st_size
        
        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            if magic:
                mime_type = magic.from_file(str(file_path), mime=True)
            else:
                # Fallback based on extension
                ext = file_path.suffix.lower()
                mime_map = {
                    ".txt": "text/plain",
                    ".md": "text/markdown",
                    ".html": "text/html",
                    ".htm": "text/html",
                    ".pdf": "application/pdf",
                }
                mime_type = mime_map.get(ext, "application/octet-stream")
        
        # Read file content
        if mime_type.startswith("text/"):
            async with aiofiles.open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = await f.read()
            
            # Extract text based on type
            if mime_type in ("text/html", "text/xhtml"):
                if Document and lxml:
                    # Use readability for HTML
                    doc = Document(content)
                    text = doc.summary()
                    text = extract_plain_text(text)
                else:
                    # Fallback: basic HTML extraction
                    text = extract_plain_text(content)
            elif mime_type == "text/markdown":
                # For markdown, just normalize (could use markdown parser)
                text = normalize_text(content)
            else:
                # Plain text
                text = normalize_text(content)
        
        elif mime_type == "application/pdf":
            if pdf_extract:
                # Run PDF extraction in thread pool (blocking operation)
                loop = asyncio.get_event_loop()
                text = await loop.run_in_executor(None, pdf_extract, str(file_path))
                text = normalize_text(text)
            else:
                return None, None
        
        else:
            # Unsupported file type
            return None, None
        
        if not text or len(text.strip()) == 0:
            return None, None
        
        # Create metadata
        meta = ItemMeta(
            mime=mime_type,
            bytes=file_size,
            source=f"{file_path}#L0-L{len(text)}",
            raw_path=str(file_path),
        )
        
        return text, meta
    
    except Exception as e:
        # Log error and return None
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error parsing file {file_path}: {e}", exc_info=True)
        return None, None


async def parse_text(text: str, source: Optional[str] = None) -> Tuple[str, ItemMeta]:
    """
    Parse text input (from POST request).
    
    Args:
        text: Raw text input
        source: Optional source identifier
        
    Returns:
        Tuple of (normalized_text, ItemMeta)
    """
    normalized = normalize_text(text)
    
    meta = ItemMeta(
        mime="text/plain",
        bytes=len(text.encode("utf-8")),
        source=source or "api:post",
    )
    
    return normalized, meta

