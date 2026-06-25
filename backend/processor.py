"""Main image processing workflow."""
import logging
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

from folder_parser import extract_parcel_number
from matcher import ParcelMatcher
from image_validator import validate_image_file
from classifier import ImageClassifier
from file_utils import generate_filename, copy_and_rename_image, rename_pdf, convert_to_jpeg

logger = logging.getLogger(__name__)


def process_folder(
    folder_path: str,
    output_dir: str,
    parcel_matcher: ParcelMatcher,
    classifier: ImageClassifier
) -> Dict:
    """
    Process images in selected folder.
    
    Workflow:
    1. Extract parcel number from folder name
    2. Match parcel number to account number via CSV
    3. Scan folder for image files and convert non-JPEG to JPEG (saved to processed folder)
    4. Validate images (all are now JPEG/JPG)
    5. Classify each image by room type
    6. Rename files according to naming convention
    7. Copy processed images to output location
    
    Args:
        folder_path: Path to folder containing images
        output_dir: Directory to save processed images
        parcel_matcher: ParcelMatcher instance for account number lookup
        classifier: ImageClassifier instance for room classification
        
    Returns:
        {
            "account_no": str,
            "parcel_no": Optional[str],
            "processed_count": int,
            "errors": List[str],
            "skipped_files": List[str],
            "results": List[Dict]  # List of processed file info
        }
    """
    folder = Path(folder_path)
    output = Path(output_dir)
    
    errors = []
    skipped_files = []
    results = []
    
    # Step 1: Extract parcel number from folder name
    logger.info(f"Extracting parcel number from folder name: '{folder.name}'")
    parcel_no = extract_parcel_number(folder.name)
    
    if parcel_no:
        logger.info(f"Extracted parcel number: '{parcel_no}'")
        print(f"DEBUG: Extracted parcel number from '{folder.name}': '{parcel_no}'")
    else:
        logger.warning(f"Could not extract parcel number from folder name: '{folder.name}'")
        print(f"DEBUG: Failed to extract parcel number from folder name: '{folder.name}'")
        errors.append(f"Could not extract parcel number from folder name")
    
    # Step 2: Match parcel number to account number
    account_no = "UNKNOWN"
    if parcel_no:
        matched_account = parcel_matcher.match_parcel_number(parcel_no)
        if matched_account:
            account_no = matched_account
            logger.info(f"Matched parcel {parcel_no} to account: {account_no}")
        else:
            logger.warning(f"No account match found for parcel: {parcel_no}")
            errors.append(f"No account match found for parcel: {parcel_no}")
    else:
        errors.append("Cannot match account number: no parcel number extracted")
    
    # Step 2.5: Handle PDF files - rename them with account number
    logger.info("Processing PDF files...")
    pdf_files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() == '.pdf']
    for pdf_file in pdf_files:
        if account_no != "UNKNOWN":
            renamed_pdf = rename_pdf(pdf_file, account_no, output)
            if renamed_pdf:
                logger.info(f"Renamed PDF: {pdf_file.name} -> {renamed_pdf.name}")
            else:
                errors.append(f"Failed to rename PDF: {pdf_file.name}")
        else:
            logger.warning(f"Skipping PDF rename (no account number): {pdf_file.name}")
    
    # Step 3: Scan folder for image files and convert non-JPEG images to processed folder
    logger.info(f"Scanning folder for image files: {folder}")
    image_extensions = ['.jpg', '.jpeg', '.JPG', '.JPEG', '.png', '.PNG', '.gif', '.GIF', '.bmp', '.BMP', '.tiff', '.TIFF', '.webp', '.WEBP', '.jfif', '.JFIF']
    jpeg_extensions = ['.jpg', '.jpeg', '.JPG', '.JPEG']
    image_files = []
    converted_count = 0
    
    # Process each image file
    for file_path in folder.iterdir():
        if not file_path.is_file():
            continue
            
        suffix_lower = file_path.suffix.lower()
        
        # Skip if not an image file
        if suffix_lower not in image_extensions:
            continue
        
        # If already JPEG, use original file
        if suffix_lower in jpeg_extensions:
            image_files.append(file_path)
        else:
            # Convert non-JPEG images to JPEG and save to processed folder
            converted_path = convert_to_jpeg(file_path, output)
            if converted_path:
                image_files.append(converted_path)
                converted_count += 1
            else:
                errors.append(f"Failed to convert image: {file_path.name}")
                skipped_files.append(str(file_path.name))
    
    logger.info(f"Found {len(image_files)} JPEG image files ({converted_count} converted from other formats)")
    
    if not image_files:
        errors.append("No image files found in folder")
        return {
            "account_no": account_no,
            "parcel_no": parcel_no,
            "processed_count": 0,
            "errors": errors,
            "skipped_files": skipped_files,
            "results": results
        }
    
    # Step 4: Validate images
    logger.info("Validating image files...")
    valid_images = []
    
    for image_file in image_files:
        if validate_image_file(image_file):
            valid_images.append(image_file)
        else:
            skipped_files.append(str(image_file.name))
            logger.debug(f"Skipped invalid image: {image_file.name}")
    
    logger.info(f"Validated {len(valid_images)} images ({len(skipped_files)} skipped)")
    
    if not valid_images:
        errors.append("No valid JPEG/JPG images found")
        return {
            "account_no": account_no,
            "parcel_no": parcel_no,
            "processed_count": 0,
            "errors": errors,
            "skipped_files": skipped_files,
            "results": results
        }
    
    # Step 5: Classify images
    logger.info("Classifying images...")
    image_paths = [str(img) for img in valid_images]
    classifications = classifier.classify_images(image_paths)
    
    # Step 6: Group by classification and generate sequential numbers
    logger.info("Grouping images by classification...")
    classification_groups = defaultdict(list)
    
    for image_path, classification in classifications:
        classification_groups[classification].append(image_path)
    
    # Step 7: Generate filenames and copy files
    logger.info("Generating filenames and copying files...")
    processed_count = 0
    
    for classification, image_list in classification_groups.items():
        # Sort images by original filename for consistent ordering
        image_list.sort()
        
        for index, image_path in enumerate(image_list, start=1):
            # Generate filename
            filename = generate_filename(account_no, classification, index)
            
            # Copy and rename
            source_path = Path(image_path)
            copied_path = copy_and_rename_image(source_path, output, filename)
            
            if copied_path:
                processed_count += 1
                results.append({
                    "original_file": str(source_path.name),
                    "new_filename": filename,
                    "classification": classification,
                    "saved_path": str(copied_path)
                })
                logger.info(f"Processed: {source_path.name} -> {filename}")
            else:
                errors.append(f"Failed to copy: {source_path.name}")
    
    logger.info(f"Processing complete: {processed_count} images processed")
    
    return {
        "account_no": account_no,
        "parcel_no": parcel_no,
        "processed_count": processed_count,
        "errors": errors,
        "skipped_files": skipped_files,
        "results": results
    }

