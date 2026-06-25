"""Image validation utilities."""
import logging
from pathlib import Path
from PIL import Image

logger = logging.getLogger(__name__)


def validate_image_file(file_path: Path) -> bool:
    """
    Validate that file is a valid JPEG/JPG image.
    
    Args:
        file_path: Path to the file to validate
        
    Returns:
        True if valid JPEG/JPG, False otherwise
    """
    try:
        # Check file extension
        ext = file_path.suffix.lower()
        if ext not in ['.jpg', '.jpeg']:
            logger.debug(f"File {file_path.name} has invalid extension: {ext}")
            return False
        
        # Check if file exists
        if not file_path.exists():
            logger.debug(f"File {file_path.name} does not exist")
            return False
        
        # Try to open with PIL
        try:
            with Image.open(file_path) as img:
                # Verify it's actually an image
                img.verify()
            
            # Reopen for format check (verify() closes the image)
            with Image.open(file_path) as img:
                # Check if it's JPEG format
                if img.format not in ['JPEG', 'JPG']:
                    logger.debug(f"File {file_path.name} is not JPEG format: {img.format}")
                    return False
                
                # Check if it's RGB or grayscale (valid JPEG modes)
                if img.mode not in ['RGB', 'L', 'CMYK']:
                    logger.debug(f"File {file_path.name} has unsupported mode: {img.mode}")
                    return False
                
                return True
                
        except Exception as e:
            logger.debug(f"File {file_path.name} cannot be opened as image: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Error validating file {file_path}: {e}")
        return False

