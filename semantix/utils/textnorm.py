"""Text normalization utilities."""
import re
from typing import Optional


def normalize_text(text: str, aggressive: bool = True) -> str:
    """
    Normalize text: lower noise, strip boilerplate, collapse whitespace.
    
    Args:
        text: Raw text input
        aggressive: If True, apply more aggressive normalization
        
    Returns:
        Normalized text
    """
    # Remove null bytes and control characters (except newlines/tabs)
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]", "", text)
    
    # Collapse multiple whitespace to single space
    text = re.sub(r"\s+", " ", text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    if aggressive:
        # Remove excessive punctuation runs
        text = re.sub(r"[!?.]{3,}", "...", text)
        
        # Normalize quotes
        text = text.replace(""", '"').replace(""", '"')
        text = text.replace("'", "'").replace("'", "'")
    
    return text


def extract_plain_text(html: str) -> str:
    """
    Extract plain text from HTML (basic implementation).
    For production, use readability-lxml or similar.
    """
    # Remove script and style tags
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    
    # Decode HTML entities (basic)
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    
    return normalize_text(text)

