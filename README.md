# MLS Photo Processor

A desktop application for processing MLS (Multiple Listing Service) property photos. The application automatically extracts parcel numbers from folder names, matches them to account numbers via CSV lookup, and classifies images by room type using a three-layer classification system (rules-based with ML fallback).

## Features

- **Desktop GUI**: User-friendly tkinter-based interface for folder selection and processing
- **Parcel Number Extraction**: Automatically extracts parcel numbers from folder names
- **Account Number Matching**: Matches parcel numbers to account numbers using CSV lookup
- **Image Classification**: Classifies images into 10 room categories:
  - KITCHEN
  - LIVING ROOM
  - BEDROOM
  - OFFICE
  - DINING ROOM
  - LAUNDRY ROOM
  - DECK
  - EXTERIOR
  - BATHROOM
  - OTHER
- **Automatic File Renaming**: Renames images according to naming convention: `{AccountNumber}_{RoomType}_{Index}.jpg`
- **Image Format Support**: Handles JPEG, PNG, GIF, BMP, TIFF, and WebP formats (converts non-JPEG to JPEG)
- **PDF Handling**: Automatically renames PDF files with account numbers

## Requirements

- Python 3.8+
- See `backend/requirements.txt` for full dependency list

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/MLS_Photo_Processor.git
cd MLS_Photo_Processor
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

## Usage

1. Ensure you have a CSV file with parcel-to-account number mappings. The application looks for CSV files in this order:
   - `~/Downloads/Accounts and Parcel Numbers - Sheet1.csv`
   - `~/Documents/MLS_Photo_Processor/Accounts_and_Parcel_Numbers.csv`
   - `backend/data/Accounts_and_Parcel_Numbers.csv` (bundled)

2. Run the application:
```bash
cd backend
python app.py
```

3. In the GUI:
   - Click "Select Folder" to choose a folder containing MLS photos
   - The folder name should contain a parcel number (e.g., "12345-678-90" or "Parcel_12345")
   - Click "Process Images" to start processing
   - Processed images will be saved to a `processed` subdirectory within the selected folder

## How It Works

1. **Parcel Extraction**: Extracts parcel number from folder name using pattern matching
2. **CSV Lookup**: Matches parcel number to account number using the CSV mapping file
3. **Image Discovery**: Scans folder for image files (JPEG, PNG, GIF, BMP, TIFF, WebP)
4. **Image Validation**: Validates that files are valid image formats
5. **Format Conversion**: Converts non-JPEG images to JPEG format
6. **Classification**: Applies three-layer classification:
   - **Layer 1**: Hard rules (e.g., bed detected → BEDROOM)
   - **Layer 2**: Heuristic rules (e.g., sink + refrigerator → KITCHEN)
   - **Layer 3**: ML fallback using CLIP model (if rules don't match)
7. **File Renaming**: Renames files as `{AccountNumber}_{RoomType}_{Index}.jpg`
8. **Output**: Copies processed images to `processed` subdirectory

## Project Structure

```
MLS_Photo_Processor/
├── backend/
│   ├── app.py              # Main application entry point
│   ├── gui.py              # Desktop GUI implementation
│   ├── processor.py       # Main processing workflow
│   ├── matcher.py          # CSV loading and parcel matching
│   ├── classifier.py       # Three-layer image classification
│   ├── folder_parser.py    # Parcel number extraction
│   ├── image_validator.py  # Image validation utilities
│   ├── file_utils.py       # File operations and renaming
│   ├── data/
│   │   └── Accounts_and_Parcel_Numbers.csv  # Bundled CSV template
│   └── requirements.txt    # Python dependencies
├── build.py                # PyInstaller build script
├── build.spec              # PyInstaller configuration
├── TECHNICAL_OVERVIEW.md    # Detailed technical documentation
└── README.md               # This file
```

## Building Executable

To build a standalone executable using PyInstaller:

```bash
python build.py
```

The executable will be created in the `dist/` directory.

## Classification System

The application uses a rules-first approach with ML fallback:

- **Priority**: Hard rules → Heuristic rules → ML classification → OTHER
- **Object Detection**: Uses CLIP model (`openai/clip-vit-base-patch32`) for detecting objects like "bed", "refrigerator", "toilet", etc.
- **Confidence Thresholds**: 
  - Object detection: 0.6 minimum confidence
  - ML classification: 0.65 minimum confidence to override OTHER
- **Conservative Defaults**: Images that don't match rules or have low ML confidence are classified as "OTHER"

See `TECHNICAL_OVERVIEW.md` for detailed information about the classification system.



