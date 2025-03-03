import re
import os
from typing import Dict, List

def parse_code_blocks(text: str) -> List[Dict[str, str]]:
    """Extract code blocks from markdown text with language information."""
    pattern = r"```(\w+)?\n(.*?)\n```"
    matches = re.finditer(pattern, text, re.DOTALL)
    blocks = []
    
    for match in matches:
        language = match.group(1) or "text"
        code = match.group(2).strip()
        blocks.append({
            "language": language,
            "code": code
        })
    return blocks

def format_duration(seconds: float) -> str:
    """Format duration in seconds to a human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"

def count_lines(code: str) -> int:
    """Count non-empty lines in code."""
    return len([line for line in code.split('\n') if line.strip()])

def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """
    Sanitize a filename by removing special characters and limiting length.
    
    Args:
        filename: The original filename
        max_length: Maximum length for the filename (default: 100)
        
    Returns:
        A sanitized filename safe for storage
    """
    # Remove any path components
    filename = filename.replace('\\', '_').replace('/', '_')
    
    # Replace special characters with underscores
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', filename)
    
    # Replace multiple underscores with a single one
    filename = re.sub(r'_+', '_', filename)
    
    # Remove leading/trailing underscores and spaces
    filename = filename.strip('_ ')
    
    # Ensure the filename is not empty
    if not filename:
        filename = "unnamed_file"
    
    # Limit length while preserving extension
    name, ext = os.path.splitext(filename)
    if len(ext) > 10:  # If extension is suspiciously long, treat it as part of name
        name = filename
        ext = ""
    
    max_name_length = max_length - len(ext)
    if max_name_length < 1:
        max_name_length = 1
    
    return name[:max_name_length] + ext
