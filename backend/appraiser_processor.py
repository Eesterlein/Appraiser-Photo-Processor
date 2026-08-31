"""Appraiser mode processing pipeline."""
import logging
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from image_validator import validate_image_file
from classifier import AppraisalClassifier
from gps_resolver import (
    GPSResolver,
    extract_date_from_exif,
    extract_exif_date_optional,
    extract_compass_direction,
)
from file_utils import (
    generate_appraiser_filename,
    generate_unresolved_filename,
    copy_and_rename_image,
    convert_to_jpeg,
)

logger = logging.getLogger(__name__)


def _format_stamp_date(yyyymmdd: str) -> str:
    """Convert a YYYYMMDD EXIF date to MM/DD/YYYY for the visible stamp."""
    return f"{yyyymmdd[4:6]}/{yyyymmdd[6:8]}/{yyyymmdd[0:4]}"


def process_folder_appraiser(
    folder_path: str,
    output_dir: str,
    gps_resolver: GPSResolver,
    classifier: AppraisalClassifier,
) -> Dict:
    """
    Appraiser mode pipeline.

    Workflow per image:
    1. Read GPS + date from original EXIF (before any conversion)
    2. Resolve GPS → account number via shapefile
    3. Validate image
    4. Classify with AppraisalClassifier
    5. Rename with account + label + sequential index + date
    6. Unresolved images go to unresolved/ subfolder

    Original files are never modified.

    Returns:
        {
            "processed_count": int,
            "unresolved_count": int,
            "errors": List[str],
            "skipped_files": List[str],
            "results": List[Dict],
            "unresolved_results": List[Dict],
        }
    """
    folder = Path(folder_path)
    output = Path(output_dir)
    unresolved_dir = output / "unresolved"

    errors: List[str] = []
    skipped_files: List[str] = []
    results: List[Dict] = []
    unresolved_results: List[Dict] = []

    # Temp dir for non-JPEG conversions — keeps intermediate files out of output folder
    temp_dir = Path(tempfile.mkdtemp(prefix="appraiser_convert_"))

    image_extensions = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp',
        '.tiff', '.webp', '.jfif', '.heic', '.heif',
    }
    jpeg_extensions = {'.jpg', '.jpeg'}

    # --- Step 1: Discover image files ---
    logger.info(f"Scanning folder: {folder}")
    raw_image_files = [
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in image_extensions
    ]
    logger.info(f"Found {len(raw_image_files)} image files")

    if not raw_image_files:
        errors.append("No image files found in folder")
        return _build_result(0, 0, errors, skipped_files, results, unresolved_results)

    # --- Step 2: For each image, read EXIF first, then prepare for processing ---
    # IMPORTANT: GPS and date must be read from the original file before conversion
    # strips EXIF metadata.
    image_records = []
    converted_count = 0

    for original_path in raw_image_files:
        # Read EXIF from original (GPS, compass, date — before conversion strips metadata)
        date_str = extract_date_from_exif(str(original_path))
        # Real capture date (None when absent) — drives the visible stamp, which is
        # skipped rather than stamped with a fallback/today date.
        exif_date = extract_exif_date_optional(str(original_path))
        compass = extract_compass_direction(str(original_path))
        account_no, coords, failure_reason = gps_resolver.resolve(str(original_path))

        # Convert non-JPEG to JPEG if needed — use temp dir to avoid polluting output
        suffix_lower = original_path.suffix.lower()
        if suffix_lower in jpeg_extensions:
            working_path = original_path
        else:
            converted_path = convert_to_jpeg(original_path, temp_dir)
            if converted_path:
                working_path = converted_path
                converted_count += 1
            else:
                errors.append(f"Failed to convert: {original_path.name}")
                skipped_files.append(original_path.name)
                continue

        image_records.append({
            'original_name': original_path.name,
            'working_path': working_path,
            'account_no': account_no,
            'failure_reason': failure_reason,
            'date_str': date_str,
            'exif_date': exif_date,
            'compass': compass,
        })

    if converted_count:
        logger.info(f"Converted {converted_count} non-JPEG images")

    # --- Step 3: Validate working images ---
    valid_records = []
    for rec in image_records:
        if validate_image_file(rec['working_path']):
            valid_records.append(rec)
        else:
            skipped_files.append(rec['original_name'])
            logger.debug(f"Skipped invalid image: {rec['original_name']}")

    logger.info(f"Validated {len(valid_records)} images ({len(skipped_files)} skipped)")

    if not valid_records:
        errors.append("No valid images found")
        return _build_result(0, 0, errors, skipped_files, results, unresolved_results)

    # --- Step 4: Split into resolved vs unresolved ---
    resolved_records = [r for r in valid_records if r['account_no'] is not None]
    unresolved_records = [r for r in valid_records if r['account_no'] is None]

    # --- Step 5: Classify and rename resolved images ---
    batch_usage = {"api_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}
    if resolved_records:
        logger.info(f"Classifying {len(resolved_records)} resolved images...")
        image_paths = [str(r['working_path']) for r in resolved_records]
        compass_cardinals = [r['compass'] for r in resolved_records]

        # Snapshot API usage before/after this batch to report per-run cost.
        usage_before = classifier.usage_summary()
        classifications = classifier.classify_images(image_paths, compass_cardinals)
        usage_after = classifier.usage_summary()
        batch_usage = {
            "api_calls": usage_after["api_calls"] - usage_before["api_calls"],
            "input_tokens": usage_after["input_tokens"] - usage_before["input_tokens"],
            "output_tokens": usage_after["output_tokens"] - usage_before["output_tokens"],
            "estimated_cost_usd": round(
                usage_after["estimated_cost_usd"] - usage_before["estimated_cost_usd"], 4
            ),
        }
        logger.info(
            f"Claude Vision batch usage: {batch_usage['api_calls']} calls, "
            f"{batch_usage['input_tokens']} in + {batch_usage['output_tokens']} out tokens, "
            f"est ${batch_usage['estimated_cost_usd']:.4f} "
            f"(session total est ${classifier.estimated_cost_usd():.4f})"
        )

        # Map path → label
        path_to_label = {path: label for path, label in classifications}

        # Group by (account_no, full_label) where full_label includes compass direction
        # for exterior labels. Interior labels never get a compass prefix.
        groups: Dict[tuple, List[Dict]] = defaultdict(list)
        for rec in resolved_records:
            label = path_to_label.get(str(rec['working_path']), 'OTHER')
            cardinal = rec['compass']
            is_interior = label in AppraisalClassifier.INTERIOR_LABELS
            full_label = label if is_interior or not cardinal else f"{cardinal} {label}"
            groups[(rec['account_no'], full_label)].append(rec)

        output.mkdir(parents=True, exist_ok=True)

        for (account_no, full_label), group_records in groups.items():
            group_records.sort(key=lambda r: r['original_name'])
            # Parse cardinal prefix back out for filename generation
            parts = full_label.split(' ', 1) if ' ' in full_label else [None, full_label]
            if parts[0] in ('N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'):
                cardinal, base_label = parts[0], parts[1]
            else:
                cardinal, base_label = None, full_label

            for index, rec in enumerate(group_records, start=1):
                filename = generate_appraiser_filename(
                    account_no, base_label, index, rec['date_str'], cardinal=cardinal
                )
                # Burn the capture date onto the image only when it's a real EXIF
                # date. If metadata has no date, skip the stamp and flag the file
                # rather than printing a misleading fallback date.
                exif_date = rec.get('exif_date')
                stamp_text = _format_stamp_date(exif_date) if exif_date else None
                copied = copy_and_rename_image(
                    rec['working_path'], output, filename, stamp_text=stamp_text
                )
                if copied:
                    if stamp_text is None:
                        logger.warning(
                            f"No EXIF capture date — output left unstamped: "
                            f"{rec['original_name']} → {filename}"
                        )
                    results.append({
                        'original_file': rec['original_name'],
                        'new_filename': filename,
                        'classification': full_label,
                        'account_no': account_no,
                        'date': rec['date_str'],
                        'date_stamped': stamp_text is not None,
                        'compass': rec['compass'],
                        'saved_path': str(copied),
                    })
                    logger.info(f"Processed: {rec['original_name']} → {filename}")
                else:
                    errors.append(f"Failed to copy: {rec['original_name']}")

    # --- Step 6: Copy unresolved images to unresolved/ folder ---
    if unresolved_records:
        logger.info(f"Copying {len(unresolved_records)} unresolved images...")
        unresolved_dir.mkdir(parents=True, exist_ok=True)

        for rec in unresolved_records:
            filename = generate_unresolved_filename(rec['original_name'], rec['date_str'])
            copied = copy_and_rename_image(rec['working_path'], unresolved_dir, filename)
            if copied:
                unresolved_results.append({
                    'original_file': rec['original_name'],
                    'new_filename': filename,
                    'failure_reason': rec['failure_reason'],
                    'date': rec['date_str'],
                    'saved_path': str(copied),
                })
                logger.warning(
                    f"Unresolved: {rec['original_name']} — {rec['failure_reason']}"
                )
            else:
                errors.append(f"Failed to copy unresolved: {rec['original_name']}")

    # Clean up temp conversion files
    shutil.rmtree(temp_dir, ignore_errors=True)

    processed_count = len(results)
    unresolved_count = len(unresolved_results)
    logger.info(
        f"Appraiser processing complete: {processed_count} processed, "
        f"{unresolved_count} unresolved"
    )

    return _build_result(
        processed_count, unresolved_count, errors, skipped_files, results,
        unresolved_results, api_usage=batch_usage
    )


def _build_result(
    processed_count, unresolved_count, errors, skipped_files, results,
    unresolved_results, api_usage=None
) -> Dict:
    return {
        "processed_count": processed_count,
        "unresolved_count": unresolved_count,
        "errors": errors,
        "skipped_files": skipped_files,
        "results": results,
        "unresolved_results": unresolved_results,
        "api_usage": api_usage or {
            "api_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0
        },
    }
