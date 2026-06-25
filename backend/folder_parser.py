"""Folder name parsing utilities."""
import re
from typing import Optional


def extract_parcel_number(folder_name: str) -> Optional[str]:
    """
    Extract parcel number from folder name.
    
    Handles formats like:
    - "Parcel-12345"
    - "12345"
    - "Property-12345"
    - "Parcel 12345"
    - Folder name IS the parcel number
    
    Args:
        folder_name: Name of the folder
        
    Returns:
        Parcel number string or None if cannot extract
    """
    if not folder_name:
        print(f"DEBUG folder_parser: Empty folder name")
        return None
    
    # Strip whitespace
    folder_name = folder_name.strip()
    print(f"DEBUG folder_parser: Processing folder name: '{folder_name}'")
    
    # Try to extract numbers from common patterns
    # Pattern 1: "Parcel-12345" or "Parcel 12345"
    match = re.search(r'(?:parcel|property)[\s\-_]*(\d+)', folder_name, re.IGNORECASE)
    if match:
        result = match.group(1)
        print(f"DEBUG folder_parser: Pattern 1 match: '{result}'")
        return result
    
    # Pattern 2: Just numbers (if folder name is mostly numbers)
    # Check if folder name is primarily numeric
    numbers_only = re.sub(r'[^\d]', '', folder_name)
    if len(numbers_only) >= 4 and len(numbers_only) <= 15:
        # If folder name is mostly numbers, use it
        if len(numbers_only) / len(folder_name.replace(' ', '')) > 0.5:
            print(f"DEBUG folder_parser: Pattern 2 match (mostly numbers): '{numbers_only}'")
            return numbers_only
    
    # Pattern 3: Extract any sequence of 4-15 digits
    match = re.search(r'\d{4,15}', folder_name)
    if match:
        result = match.group(0)
        print(f"DEBUG folder_parser: Pattern 3 match: '{result}'")
        return result
    
    # Pattern 4: If folder name itself looks like a parcel number
    # (mostly alphanumeric, reasonable length)
    cleaned = re.sub(r'[^\w]', '', folder_name)
    if len(cleaned) >= 4 and len(cleaned) <= 15 and cleaned.isalnum():
        # Check if it's mostly numeric
        if sum(c.isdigit() for c in cleaned) >= len(cleaned) * 0.7:
            print(f"DEBUG folder_parser: Pattern 4 match: '{cleaned}'")
            return cleaned
    
    print(f"DEBUG folder_parser: No match found for '{folder_name}'")
    return None

