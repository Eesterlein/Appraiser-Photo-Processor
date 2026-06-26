"""File saving and naming utilities."""
import shutil
import subprocess
from pathlib import Path
from typing import Optional
import logging
from io import BytesIO
from PIL import Image, ImageFile

# Enable truncated image loading to handle partially malformed WEBP files
ImageFile.LOAD_TRUNCATED_IMAGES = True

logger = logging.getLogger(__name__)


def generate_filename(account_no: str, classification: str, index: int) -> str:
    """
    Generate filename according to convention.
    
    Format: ACCOUNTNO – MLS – ROOMTYPE X.JPG
    - ALL CAPS
    - Spaces before and after dashes
    - Sequential numbering per room type
    
    Args:
        account_no: Account number (will be uppercased)
        classification: Room classification (already ALL CAPS)
        index: Sequential number for this room type (1, 2, 3...)
        
    Returns:
        Filename string in format: ACCOUNTNO – MLS – ROOMTYPE X.JPG
    """
    # Ensure classification is valid and ALL CAPS (matches three-layer classifier labels)
    valid_classifications = {
        'KITCHEN', 'LIVING ROOM', 'BEDROOM', 'OFFICE',
        'DINING ROOM', 'LAUNDRY ROOM', 'DECK', 'EXTERIOR', 'BATHROOM', 'OTHER'
    }
    
    # Normalize classification to ALL CAPS
    classification = classification.upper().strip()
    
    if classification not in valid_classifications:
        classification = 'OTHER'
    
    # Ensure account number is ALL CAPS
    account_no = str(account_no).upper().strip()
    
    # Format: ACCOUNTNO - MLS - ROOMTYPE X.JPG
    # Using regular dash with spaces as specified: " - "
    filename = f"{account_no} - MLS - {classification} {index}.JPG"
    return filename


def generate_appraiser_filename(
    account_no: str,
    label: str,
    index: int,
    date_str: str,
    cardinal: Optional[str] = None,
) -> str:
    """
    Generate filename for appraiser mode.

    With compass direction:  {ACCOUNT_NO} - {CARDINAL} {LABEL} {INDEX} - {DATE}.JPG
    Without compass direction: {ACCOUNT_NO} - {LABEL} {INDEX} - {DATE}.JPG
    """
    account_no = str(account_no).upper().strip()
    label = label.upper().strip()
    if cardinal:
        return f"{account_no} - {cardinal} {label} {index} - {date_str}.JPG"
    return f"{account_no} - {label} {index} - {date_str}.JPG"


def generate_unresolved_filename(original_name: str, date_str: str) -> str:
    """
    Generate filename for unresolved appraiser images.

    Format: UNRESOLVED - {original stem} - {DATE}.JPG
    """
    stem = Path(original_name).stem
    return f"UNRESOLVED - {stem} - {date_str}.JPG"


def copy_and_rename_image(
    source_path: Path, 
    dest_dir: Path, 
    filename: str
) -> Optional[Path]:
    """
    Copy image file and rename it according to naming convention.
    
    Args:
        source_path: Path to source image file
        dest_dir: Directory to copy image to
        filename: New filename to use
        
    Returns:
        Full path to copied file, or None if failed
    """
    try:
        # Ensure output directory exists
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Handle filename collisions
        full_path = dest_dir / filename
        counter = 1
        base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
        ext = filename.rsplit('.', 1)[1] if '.' in filename else 'JPG'
        
        while full_path.exists():
            # Add counter before extension
            new_filename = f"{base_name}_{counter}.{ext}"
            full_path = dest_dir / new_filename
            counter += 1
        
        # Copy file
        shutil.copy2(source_path, full_path)
        
        logger.info(f"Copied and renamed image: {source_path.name} -> {full_path.name}")
        return full_path
        
    except Exception as e:
        logger.error(f"Error copying image {source_path}: {e}")
        return None


def rename_pdf(pdf_path: Path, account_no: str, output_dir: Path) -> Optional[Path]:
    """
    Rename PDF file to just the account number.
    
    Args:
        pdf_path: Path to PDF file
        account_no: Account number to use in filename
        output_dir: Directory to copy renamed PDF to
        
    Returns:
        Full path to renamed PDF, or None if failed
    """
    try:
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename: ACCOUNTNO.PDF
        account_no = str(account_no).upper().strip()
        filename = f"{account_no}.PDF"
        
        # Handle filename collisions
        full_path = output_dir / filename
        counter = 1
        base_name = account_no
        
        while full_path.exists():
            # Add counter before extension
            new_filename = f"{base_name}_{counter}.PDF"
            full_path = output_dir / new_filename
            counter += 1
        
        # Copy PDF file
        shutil.copy2(pdf_path, full_path)
        
        logger.info(f"Renamed PDF: {pdf_path.name} -> {full_path.name}")
        return full_path
        
    except Exception as e:
        logger.error(f"Error renaming PDF {pdf_path}: {e}")
        return None


def convert_to_jpeg(source_path: Path, output_dir: Path) -> Optional[Path]:
    """
    Convert image file to JPEG format silently with RealWare compatibility.
    
    Converts non-JPEG images (WEBP, PNG, JFIF, etc.) to baseline JPEG format.
    Special handling for WEBP files: optimization is disabled to prevent Pillow bugs.
    Ensures compatibility with RealWare by:
    - Converting to RGB mode
    - Saving as baseline JPEG (not progressive)
    - Stripping ICC profiles and metadata
    - Using high quality settings (quality=95)
    - Optimization and subsampling only applied to non-WEBP images
    - Creating JFIF-compatible JPEG files
    
    Saves converted image only to output directory, original file remains untouched.
    
    Args:
        source_path: Path to source image file
        output_dir: Directory to save converted JPEG (processed folder)
        
    Returns:
        Full path to converted JPEG file, or None if failed
    """
    # Get original extension for logging (before try block for error handling)
    original_ext = source_path.suffix.upper()
    is_webp = original_ext in ['.WEBP', '.webp']
    
    try:
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Force full pixel decode with robust fallback path for malformed WEBP files
        source_img = None
        img = None
        
        # PRIMARY decode path
        try:
            source_img = Image.open(source_path)
            source_img.load()  # FORCE full pixel decode immediately
        except Exception as e:
            # FALLBACK decode path for malformed WEBPs
            logger.warning(f"Primary WEBP decode failed, attempting fallback: {source_path.name} ({e})")
            try:
                with open(source_path, "rb") as f:
                    raw = f.read()
                source_img = Image.open(BytesIO(raw))
                source_img.load()
            except Exception as e2:
                logger.error(f"WEBP decode failed after fallback: {source_path.name} ({e2})")
                return None
        
        # Convert to RGB only after decode succeeds
        try:
            if source_img.mode == "RGBA":
                img = Image.new("RGB", source_img.size, (255, 255, 255))
                img.paste(source_img, mask=source_img.split()[3])
            else:
                img = source_img.convert("RGB")
            
            img.load()  # Ensure pixels are fully materialized
        finally:
            # Close source image after conversion
            if source_img is not None:
                try:
                    source_img.close()
                except Exception:
                    pass
        
        # Generate output filename (same name but .JPG extension)
        base_name = source_path.stem
        output_filename = f"{base_name}.JPG"
        output_path = output_dir / output_filename
        
        # Handle filename collisions
        counter = 1
        while output_path.exists():
            output_filename = f"{base_name}_{counter}.JPG"
            output_path = output_dir / output_filename
            counter += 1
        
        # Save as baseline JPEG with RealWare-compatible settings
        save_kwargs = dict(
            format="JPEG",
            quality=95,
            progressive=False,  # Baseline JPEG, not progressive - required for RealWare
            exif=None,          # Strip EXIF metadata
            icc_profile=None    # Strip ICC color profiles
        )
        
        # Pillow bug: WEBP-derived images crash with optimize/subsampling
        if not is_webp:
            save_kwargs["optimize"] = True
            save_kwargs["subsampling"] = 0
        
        img.save(output_path, **save_kwargs)
        
        # Log conversion with format: "Converted WEBP → JPG: filename.webp"
        logger.info(f"Converted {original_ext} → JPG: {source_path.name}")
        return output_path
        
    except Exception as e:
        error_msg = str(e)
        
        if is_webp:
            logger.warning(
                f"Pillow WEBP conversion failed, attempting ImageMagick fallback: {source_path.name} ({error_msg})"
            )
            
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / f"{source_path.stem}.JPG"
                
                # Handle filename collisions
                counter = 1
                while output_path.exists():
                    output_path = output_dir / f"{source_path.stem}_{counter}.JPG"
                    counter += 1
                
                # ImageMagick command
                subprocess.run(
                    [
                        "magick",
                        str(source_path),
                        "-strip",
                        "-colorspace", "sRGB",
                        "-quality", "95",
                        "-interlace", "None",
                        str(output_path)
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
                logger.info(f"Converted WEBP → JPG via ImageMagick: {source_path.name}")
                return output_path
                
            except Exception as fallback_error:
                logger.error(
                    f"ImageMagick fallback failed for {source_path.name}: {fallback_error}"
                )
                return None
        
        logger.error(f"Error converting image {source_path.name} to JPEG: {error_msg}")
        return None


def ensure_output_dir(output_dir: str) -> Path:
    """
    Ensure output directory exists and is writable.
    
    Args:
        output_dir: Output directory path
        
    Returns:
        Path object
        
    Raises:
        ValueError: If directory cannot be created or is not writable
    """
    path = Path(output_dir)
    
    try:
        path.mkdir(parents=True, exist_ok=True)
        
        # Test write permissions
        test_file = path / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            raise ValueError(f"Output directory is not writable: {output_dir}") from e
        
        return path
        
    except Exception as e:
        raise ValueError(f"Cannot create output directory: {output_dir}") from e


