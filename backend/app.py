"""Main application entry point for MLS Photo Processor."""
import logging
import os
import sys
from pathlib import Path

from matcher import ParcelMatcher
from classifier import ImageClassifier, AppraisalClassifier, load_clip_model
from processor import process_folder
from appraiser_processor import process_folder_appraiser
from gps_resolver import GPSResolver
from gui import MLSPhotoProcessorGUI

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('mls_photo_processor.log')
    ]
)
logger = logging.getLogger(__name__)

# When frozen by PyInstaller, bundled files are extracted to sys._MEIPASS
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent

DATA_DIR = BASE_DIR / "data"


def _load_api_key():
    """
    Load the Anthropic API key.

    Priority:
    1. ANTHROPIC_API_KEY environment variable (set by IT or developer)
    2. api_key.txt file next to the .exe / app.py (for shared drive deployments)
    """
    key = os.environ.get('ANTHROPIC_API_KEY', '').strip()
    if key:
        return

    # Look for api_key.txt next to the executable (PyInstaller) or this script
    exe_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
    key_file = exe_dir / 'api_key.txt'
    if key_file.exists():
        key = key_file.read_text().strip()
        if key:
            os.environ['ANTHROPIC_API_KEY'] = key
            logger.info("API key loaded from api_key.txt")


def main():
    _load_api_key()
    logger.info("Starting MLS Photo Processor...")

    try:
        logger.info("Loading parcel matcher...")
        parcel_matcher = ParcelMatcher()
        logger.info("Parcel matcher loaded")

        # Load CLIP model once — shared by both classifiers
        logger.info("Loading CLIP model...")
        clip_model, clip_processor = load_clip_model()
        logger.info("CLIP model loaded")

        logger.info("Initializing classifiers...")
        classifier = ImageClassifier(clip_model=clip_model, clip_processor=clip_processor)
        appraiser_classifier = AppraisalClassifier(clip_model=clip_model, clip_processor=clip_processor)
        logger.info("Classifiers ready")

        logger.info("Loading GPS resolver (shapefile)...")
        dbf_path = str(DATA_DIR / "Address.dbf")
        gps_resolver = GPSResolver(dbf_path=dbf_path)
        logger.info("GPS resolver ready")

        logger.info("Initializing GUI...")
        app = MLSPhotoProcessorGUI(
            title_admin_processor=process_folder,
            appraiser_processor=process_folder_appraiser,
            parcel_matcher=parcel_matcher,
            classifier=classifier,
            appraiser_classifier=appraiser_classifier,
            gps_resolver=gps_resolver,
        )

        logger.info("Launching GUI...")
        app.run()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
