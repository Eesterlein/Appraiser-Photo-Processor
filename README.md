# Appraiser Photo Processor

A desktop application for county assessors and title administrators to automatically classify and rename property photos. Select your role, point the app at a folder of photos, and it handles the rest.

## Roles

### Title Administrator
- Extracts parcel number from the folder name
- Matches parcel number to account number via CSV lookup
- Classifies interior room photos (KITCHEN, BEDROOM, BATHROOM, etc.) using a CLIP-based ML classifier
- Renames files: `ACCOUNTNO - MLS - ROOMTYPE X.JPG`

### Appraiser
- Reads GPS coordinates from each photo's EXIF data
- Matches GPS to the nearest parcel using a local address shapefile (no internet required)
- Reads compass direction (GPSImgDirection) to determine which side of the building was photographed
- Classifies photos using Claude Vision AI — handles both interior and exterior shots in the same folder
- Interior: `ACCOUNTNO - KITCHEN 1 - YYYYMMDD.JPG`
- Exterior: `ACCOUNTNO - NE FRONT OF BUILDING 1 - YYYYMMDD.JPG`
- Photos with no GPS go to `processed/unresolved/`

## Appraiser Labels

**Exterior:** FRONT OF BUILDING, BACK OF BUILDING, CORNER OF BUILDING, CORNER OF GARAGE, CORNER OF SHED, GARAGE, SHED, WINDOW, LAND, VIEW, DECK, BUILDING PROGRESS, DAMAGE, OTHER

**Interior:** KITCHEN, LIVING ROOM, BEDROOM, BATHROOM, DINING ROOM, LAUNDRY ROOM, OFFICE

## Requirements

- Python 3.11+
- An Anthropic API key (for Appraiser mode — set as `ANTHROPIC_API_KEY` environment variable)
- Address shapefile (`Address.dbf/.prj/.shp/.shx`) placed in `backend/data/`
- Parcel CSV (`Accounts_and_Parcel_Numbers.csv`) — bundled or placed in `~/Downloads/`

See `backend/requirements.txt` for Python dependencies.

## Installation

```bash
git clone https://github.com/Eesterlein/Appraiser-Photo-Processor.git
cd Appraiser-Photo-Processor
cd backend
pip install -r requirements.txt
```

## Running the App

```bash
cd backend
ANTHROPIC_API_KEY=your_key_here python app.py
```

On Windows, set `ANTHROPIC_API_KEY` as a system environment variable so you don't need to pass it each time.

## Project Structure

```
Appraiser-Photo-Processor/
├── backend/
│   ├── app.py                  # Entry point — loads models and launches GUI
│   ├── gui.py                  # tkinter GUI with role selector
│   ├── classifier.py           # CLIP classifier (Title Admin) + Claude Vision classifier (Appraiser)
│   ├── appraiser_processor.py  # Appraiser processing pipeline
│   ├── processor.py            # Title Admin processing pipeline
│   ├── gps_resolver.py         # GPS EXIF extraction + shapefile parcel matching
│   ├── matcher.py              # CSV parcel-to-account lookup
│   ├── file_utils.py           # File naming and copying utilities
│   ├── image_validator.py      # Image validation
│   ├── folder_parser.py        # Parcel number extraction from folder names
│   └── data/
│       ├── Address.dbf/.prj/.shp/.shx   # Address shapefile (not committed — place manually)
│       └── Accounts_and_Parcel_Numbers.csv
├── TECHNICAL_OVERVIEW.md
└── README.md
```

## Building a Windows Executable

```bash
pip install pyinstaller
python build.py
```

The `.exe` will be in `dist/`. Set `ANTHROPIC_API_KEY` as a Windows system environment variable on the deployment machine.

## Privacy & Security

- The address shapefile and GPS matching run entirely locally — no property location data leaves the machine
- Photos are only sent to the Anthropic API (Claude Vision) for classification in Appraiser mode
- The API key is never stored in code or config files — always read from the environment variable
