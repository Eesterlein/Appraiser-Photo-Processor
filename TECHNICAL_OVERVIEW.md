# Technical Overview

## Architecture

Single-process Python desktop app (tkinter). All processing runs locally on the user's machine. The only external call is to the Anthropic API for Claude Vision classification in Appraiser mode.

### Startup sequence (`app.py`)
1. Load parcel CSV → `ParcelMatcher`
2. Load CLIP model once → shared between both classifiers
3. Initialize `ImageClassifier` (Title Admin) and `AppraisalClassifier` (Appraiser) with shared CLIP model
4. Load address shapefile → `GPSResolver`
5. Launch tkinter GUI

---

## Title Administrator Mode

**Input:** Folder whose name contains a parcel number (e.g. `370135300045 - Smith John`)

**Pipeline (`processor.py`):**
1. Extract parcel number from folder name via regex (`folder_parser.py`)
2. Match parcel → account number via CSV (`matcher.py`)
3. Validate and convert non-JPEG images to JPEG
4. Classify each image with CLIP (`ImageClassifier`)
5. Rename: `ACCOUNTNO - MLS - ROOMTYPE X.JPG`

**Classifier (`ImageClassifier`):**
- CLIP model `openai/clip-vit-base-patch32` via Hugging Face
- Labels: KITCHEN, LIVING ROOM, BEDROOM, BATHROOM, DINING ROOM, LAUNDRY ROOM, OFFICE, DECK, EXTERIOR, OTHER
- Confidence threshold: 0.65 — below threshold → OTHER

---

## Appraiser Mode

**Input:** Any folder of photos (mixed interior/exterior OK, mixed properties OK)

**Pipeline (`appraiser_processor.py`):**
1. For each image, read EXIF **before any conversion** (GPS, compass, date)
2. Convert non-JPEG to JPEG if needed
3. Resolve GPS → account number via shapefile nearest-neighbor (`GPSResolver`)
4. Classify with Claude Vision (`AppraisalClassifier`)
5. Group by `(account_no, full_label)` — interior labels skip compass prefix
6. Rename with sequential index within each group
7. Unresolved (no GPS match) → `processed/unresolved/`

### GPS Resolution (`gps_resolver.py`)
- Reads EXIF tag 34853 (GPSInfo) → decimal degrees
- Loads `Address.dbf` — 16,023 address points with Latitude, Longitude, ACCOUNTNO
- Numpy nearest-neighbor search; 200m distance threshold
- Pure Python DBF reader (no external shapefile library needed)

### Compass Direction
- Reads EXIF GPSImgDirection (tag 17) — which way the camera lens was pointing
- Photographer side = `(camera_direction + 180°) % 360°`
- Mapped to 8-point cardinal: N, NE, E, SE, S, SW, W, NW
- Added as prefix to exterior labels only: `NE FRONT OF BUILDING`

### Claude Vision Classifier (`AppraisalClassifier`)
- Model: `claude-haiku-4-5-20251001`
- Images resized to max 1024px wide in memory before sending (cost optimization)
- Prompt includes compass context so Claude can reason about which facade is visible
- Handles both interior and exterior photos in one call
- Falls back to CLIP if `ANTHROPIC_API_KEY` is not set

**Exterior labels:** FRONT OF BUILDING, BACK OF BUILDING, CORNER OF BUILDING, CORNER OF GARAGE, CORNER OF SHED, GARAGE, SHED, WINDOW, LAND, VIEW, DECK, BUILDING PROGRESS, DAMAGE, OTHER

**Interior labels:** KITCHEN, LIVING ROOM, BEDROOM, BATHROOM, DINING ROOM, LAUNDRY ROOM, OFFICE

### Filename formats
```
Exterior:  ACCOUNTNO - NE FRONT OF BUILDING 1 - 20240618.JPG
Interior:  ACCOUNTNO - KITCHEN 1 - 20240618.JPG
Unresolved: UNRESOLVED - IMG_1234 - 20240618.JPG
```

---

## CSV / Shapefile Loading Priority

**Parcel CSV (Title Admin):**
1. `~/Downloads/Account_and_Parcel_Numbers - Sheet1.csv`
2. `~/Downloads/Accounts and Parcel Numbers - Sheet1.csv`
3. `~/Documents/MLS_Photo_Processor/Accounts_and_Parcel_Numbers.csv`
4. `backend/data/Accounts_and_Parcel_Numbers.csv` (bundled)

**Address Shapefile (Appraiser):**
- `backend/data/Address.dbf` (must be placed manually — not committed to repo)

---

## Windows Deployment

Built with PyInstaller into a single `.exe`. The CLIP model and shapefile are bundled. The Anthropic API key must be set as a Windows system environment variable (`ANTHROPIC_API_KEY`) on the deployment machine — it is never stored in code or config files.
