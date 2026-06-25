# Technical Architecture Overview

##  High-Level Architecture

### Application Type
This is a local desktop application built with Python and tkinter. The application runs entirely on the user's machine with no web server, cloud services, or internet dependency. All processing occurs locally using files already present on the user's filesystem.

### Execution Model
The application follows a single-process, event-driven architecture:

1. **Initialization**: On startup, the application loads two core components:
   - `ParcelMatcher`: Loads CSV mapping data from disk (Downloads folder, Documents override, or bundled CSV)
   - `ImageClassifier`: Loads the CLIP vision model for object detection (model files cached locally after first download)

2. **GUI Main Loop**: A tkinter-based desktop window provides the user interface. The GUI runs on the main thread and handles user interactions.

3. **Processing Flow**: When the user selects a folder and triggers processing:
   - Folder selection → Extract parcel number from folder name
   - CSV lookup → Match parcel number to account number
   - File scanning → Discover image files in the selected folder
   - Image validation → Verify files are valid JPEG/JPG images
   - Classification → Apply three-layer classification system to each image
   - File operations → Rename and copy processed images to output subdirectory

4. **Threading**: Image processing runs in a separate daemon thread to prevent GUI freezing. The GUI remains responsive during processing.

5. **Output**: Processed images are saved to a `processed` subdirectory within the selected folder. Original files remain untouched.

### Key Architectural Decisions
- **No network calls**: All operations are local file I/O. The only potential network activity is the initial CLIP model download (via Hugging Face Hub), which occurs once and caches locally.
- **Single executable target**: The application is designed to be packaged with PyInstaller into a standalone Windows executable (.exe) for deployment.
- **Stateless processing**: Each folder processing operation is independent. No state is maintained between runs.

## Key Python Packages & Libraries Used

### Core Dependencies

**pandas** (`pandas`)
- **Usage**: CSV file loading and data manipulation for parcel-to-account number mapping
- **Why chosen**: Standard library for structured data handling. Provides robust CSV parsing with automatic type inference and data cleaning capabilities. Used in `matcher.py` to load and query the parcel mapping CSV.

**Pillow** (`Pillow`)
- **Usage**: Image file loading, format conversion, and validation
- **Why chosen**: De facto standard Python imaging library. Required for opening JPEG files, converting non-JPEG formats to JPEG, and validating image integrity. Used throughout `classifier.py`, `image_validator.py`, and `file_utils.py`.

**transformers** (`transformers`)
- **Usage**: Loading and using the CLIP vision model for object detection
- **Why chosen**: Hugging Face Transformers provides standardized access to pre-trained vision models. Used specifically to load `openai/clip-vit-base-patch32` for object detection queries. The model is downloaded once and cached locally via Hugging Face Hub.

**torch** (`torch>=2.6.0`)
- **Usage**: Deep learning backend for CLIP model inference
- **Why chosen**: PyTorch is the required runtime for Hugging Face Transformers models. Used for tensor operations during CLIP inference in `classifier.py`.

**torchvision** (`torchvision`)
- **Usage**: Image preprocessing utilities for PyTorch
- **Why chosen**: Companion library to PyTorch that provides image transformation utilities. Used indirectly by transformers for image preprocessing.

**numpy** (`numpy`)
- **Usage**: Array operations for image analysis and outdoor scene detection heuristics
- **Why chosen**: Standard numerical computing library. Used in `classifier.py` for pixel-level analysis (sky detection, grass detection, brightness variance calculations) in the `_is_outdoor()` method.

**tkinter** (Python standard library)
- **Usage**: Desktop GUI framework for folder selection, button controls, and status display
- **Why chosen**: Built into Python, no external dependencies. Provides native desktop windowing on Windows, macOS, and Linux. Used in `gui.py` for the entire user interface.

**pyinstaller** (`pyinstaller`)
- **Usage**: Packaging Python application into standalone executable
- **Why chosen**: Standard tool for creating Windows executables from Python applications. Allows deployment without requiring Python installation on target machines.

### Supporting Dependencies

**tqdm** (`tqdm`)
- **Usage**: Progress bar display (if implemented in future iterations)
- **Note**: Currently listed in requirements but not actively used in the current codebase.

**huggingface-hub** (`huggingface-hub`)
- **Usage**: Model downloading and caching from Hugging Face
- **Why chosen**: Handles automatic model download and local caching. Used by transformers when loading the CLIP model for the first time.

## Image Classification Approach

### Overall Strategy: Rules-First with ML Fallback

The classification system uses a three-layer hierarchical approach where deterministic rules take absolute priority, and machine learning models serve only as a fallback signal. This design prioritizes predictability and stability over maximum AI accuracy.

### Why Rules-First?

The rules-first approach was chosen after experimentation with direct ML-based classification revealed instability issues:

1. **Initial attempts** with CLIP-based room classification resulted in high misclassification rates (e.g., classifying most images as "BATHROOM").
2. **Object detection with CLIP** proved more reliable than direct room classification, but still required careful threshold management.
3. **Final design**: Use CLIP only for object detection (detecting specific items like "bed", "refrigerator", "toilet"), then apply deterministic rules to make the final room classification decision.

### CLIP Usage: Object Detection Only

The CLIP model (`openai/clip-vit-base-patch32`) is used exclusively for object detection, not for final room classification. The `_detect_objects()` method queries CLIP with a predefined list of object keywords (e.g., "bed", "refrigerator", "washing machine", "toilet") and returns confidence scores above a threshold (0.6).

**Key constraint**: CLIP never directly chooses the room label. It only provides a dictionary of detected objects with confidence scores. The rule-based logic then interprets these detections to make the final classification.

### Confidence Thresholds and Conservative Defaults

- **Object detection threshold**: 0.6 (minimum confidence for an object to be considered "detected")
- **Hugging Face classifier threshold**: 0.65 (Layer 3 fallback must exceed this to override OTHER)
- **Default classification**: If no rules match and ML confidence is below threshold, the image is classified as "OTHER"

**Design philosophy**: Mislabeling is considered worse than leaving an image as "OTHER". The system defaults to conservative classification rather than forcing a prediction.

### CLIP and Complex Object Detection: Intentionally Avoided

The codebase explicitly avoids using CLIP as a primary classifier. Historical attempts to use CLIP for direct room classification resulted in:
- Over-aggressive classification (classifying everything as one room type)
- Threshold sensitivity issues
- Unpredictable behavior across different image types

The current implementation uses CLIP only for simple object detection queries, and the rule-based logic handles all final decisions. This approach was chosen specifically to avoid the instability observed in earlier CLIP-based classification attempts.

##  Room Classification Design

### Final Allowed Room Categories

The system uses a constrained set of 10 canonical labels (all uppercase):

- `KITCHEN`
- `LIVING ROOM`
- `BEDROOM`
- `OFFICE`
- `DINING ROOM`
- `LAUNDRY ROOM`
- `DECK`
- `EXTERIOR`
- `BATHROOM`
- `OTHER`

### Why a Small Label Set?

The label set was intentionally kept small to:
1. **Reduce ambiguity**: Fewer categories mean clearer distinctions between room types
2. **Improve rule coverage**: A smaller set allows more comprehensive rule definitions
3. **Increase predictability**: Users can expect consistent behavior across similar images
4. **Simplify maintenance**: Fewer labels mean fewer edge cases to handle

Labels like "GARAGE", "STAIRWAY", and "OUTSIDEAREA" were removed from earlier iterations to focus on the most common and clearly distinguishable room types.

### Rule Priority and Fallback Logic

Classification proceeds through three layers in strict priority order:

**Layer 1: Hard Rules** (Override all other logic)
- Hard rules check for specific object combinations that definitively indicate a room type
- Examples:
  - Toilet/bathtub/shower detected → BATHROOM
  - Bed detected → BEDROOM
  - Desk AND (chair OR computer) → OFFICE
  - Both washer AND dryer → LAUNDRY ROOM
- If a hard rule matches, classification stops immediately. No further layers are evaluated.

**Layer 2: Heuristic Rules** (Applied only if no hard rules match)
- Heuristic rules use combinations of objects with exclusion logic
- Examples:
  - Sink + refrigerator OR stove + cabinets → KITCHEN
  - Table present, no bed, no appliances → DINING ROOM
  - Couch/sofa AND (TV OR fireplace) → LIVING ROOM
- These rules are more permissive but still deterministic.

**Layer 3: Hugging Face Classifier** (Fallback only)
- Only invoked if no hard rules and no heuristic rules match
- Uses CLIP zero-shot classification with room type labels
- Must exceed confidence threshold (0.65) to override OTHER
- If confidence is below threshold, defaults to OTHER

**Final Fallback**: If all three layers fail to produce a classification, the image is assigned "OTHER".

### Why OTHER is Valid and Expected

The classification system treats "OTHER" as a legitimate and expected classification, not a failure state. This design choice reflects the philosophy that:

1. **Not all images fit clean categories**: Transitional spaces (hallways, mudrooms, stairs), ambiguous scenes, or unusual layouts may not match any room-specific rules.

2. **Stability over coverage**: It is preferable to classify uncertain images as "OTHER" rather than force them into an incorrect room category.

3. **User review expected**: Images classified as "OTHER" can be manually reviewed and renamed if needed, which is preferable to incorrect automatic classification.

4. **Reduces false positives**: By defaulting to OTHER when confidence is low, the system avoids misclassifying ambiguous images.

### Predictability and Stability Over Maximum AI Accuracy

The entire classification system prioritizes deterministic, predictable behavior over maximizing the number of images classified into specific room types. Key design decisions reflect this:

- **Rules override ML**: Even if a machine learning model suggests a classification, rules take precedence
- **High confidence thresholds**: ML fallback requires high confidence (0.65) before overriding OTHER
- **Conservative defaults**: When in doubt, classify as OTHER
- **Deterministic rules**: Hard rules and heuristic rules produce the same result for the same input, ensuring consistency

This approach ensures that the classification system behaves predictably across different image sets and reduces the risk of unexpected misclassifications that could require manual correction.

