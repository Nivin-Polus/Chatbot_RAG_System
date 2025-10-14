# app/utils/file_sanitizer.py

import os
import re
from pathlib import Path


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename to prevent path traversal and other security issues.
    
    Args:
        filename: The original filename
        max_length: Maximum allowed filename length
        
    Returns:
        Sanitized filename safe for storage
    """
    if not filename:
        return "unnamed_file"
    
    # Get just the basename (remove any path components)
    filename = os.path.basename(filename)
    
    # Split into name and extension
    name, ext = os.path.splitext(filename)
    
    # Remove or replace dangerous characters
    # Allow: letters, digits, spaces, hyphens, underscores, dots
    name = re.sub(r'[^\w\s\-.]', '_', name)
    
    # Remove leading/trailing dots and spaces
    name = name.strip('. ')
    
    # Replace multiple spaces/underscores with single ones
    name = re.sub(r'[\s_]+', '_', name)
    
    # Ensure extension is safe (alphanumeric only)
    ext = re.sub(r'[^\w.]', '', ext)
    
    # Reconstruct filename
    sanitized = f"{name}{ext}"
    
    # Limit length (reserve space for extension)
    if len(sanitized) > max_length:
        max_name_length = max_length - len(ext)
        sanitized = f"{name[:max_name_length]}{ext}"
    
    # Ensure we don't have an empty filename
    if not sanitized or sanitized == ext:
        sanitized = f"file{ext}"
    
    return sanitized


def validate_file_size(file_size_bytes: int, max_size_mb: int = 25) -> bool:
    """
    Validate that file size is within acceptable limits.
    
    Args:
        file_size_bytes: File size in bytes
        max_size_mb: Maximum allowed size in MB
        
    Returns:
        True if file size is acceptable, False otherwise
    """
    max_size_bytes = max_size_mb * 1024 * 1024
    return file_size_bytes <= max_size_bytes


def validate_file_extension(filename: str, allowed_extensions: set) -> bool:
    """
    Validate that file extension is in the allowed list.
    
    Args:
        filename: The filename to check
        allowed_extensions: Set of allowed extensions (without dots)
        
    Returns:
        True if extension is allowed, False otherwise
    """
    ext = filename.split('.')[-1].lower() if '.' in filename else ''
    return ext in allowed_extensions
