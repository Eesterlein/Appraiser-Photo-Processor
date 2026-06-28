# Appraiser Photo Processor — User Guide

## What This App Does

The Appraiser Photo Processor automatically renames and organizes property photos for upload to RealWare. Instead of manually renaming each photo, you select a folder, choose your role, and the app does the rest.

---

## Before You Start

Make sure your IT department has:
- Installed the app (`AppraiserPhotoProcessor.exe`) on your computer
- Set the `ANTHROPIC_API_KEY` environment variable (one-time setup — you won't see or touch this)

You will need:
- A folder of property photos on your computer
- Location services enabled on your camera/phone when photos were taken (Appraiser mode only)

---

## Launching the App

Double-click **AppraiserPhotoProcessor.exe**. The app will take about 15–20 seconds to load — it is loading its AI model in the background. Wait for the main window to appear before doing anything.

---

## Choosing Your Role

When the window opens, you will see two options:

**Title Administrator**
- Use this if you are processing MLS listing photos
- The folder name must contain the parcel number (e.g. `370135300045 - Smith John`)
- Photos are classified by room type: KITCHEN, LIVING ROOM, BEDROOM, BATHROOM, etc.
- Output format: `ACCOUNTNO - MLS - ROOMTYPE X.JPG`

**Appraiser**
- Use this if you are processing appraisal field photos
- Photos can be a mix of interior and exterior — the app sorts them automatically
- Account number is read from the GPS location embedded in each photo
- Output format: `ACCOUNTNO - NE FRONT OF BUILDING 1 - YYYYMMDD.JPG`

Select your role by clicking the radio button next to it. The **Process Images** button will stay grayed out until you have selected both a role and a folder.

---

## Processing Photos

1. Click **Select Folder** and navigate to the folder containing your photos
2. The folder path will appear in the window
3. Click **Process Images**
4. A progress bar will appear while the app works — do not close the window
5. When finished, a summary popup will tell you how many photos were processed

Processed photos are saved to a **`processed`** subfolder inside the folder you selected. Your original photos are never moved or modified.

---

## Appraiser Mode — Tips

**GPS is required for account number matching.** Make sure location services are enabled on your device before shooting. Photos without GPS data go to `processed/unresolved/` — they are renamed with the date but not assigned an account number.

**Mixed folders are fine.** You can have interior and exterior photos in the same folder. The app detects which is which automatically.

**Supported photo formats:** JPG, HEIC, PNG, WEBP, and others. HEIC (iPhone default) is fully supported.

**Photo labels explained:**

| Label | What it means |
|---|---|
| NE FRONT OF BUILDING | Front of the main structure, photographer on the NE side |
| SW CORNER OF BUILDING | Diagonal corner view of the main structure |
| E GARAGE | Garage with visible door, photographer on the E side |
| CORNER OF SHED | Diagonal corner of a shed or outbuilding |
| BEDROOM | Interior bedroom |
| BATHROOM | Interior bathroom |
| BUILDING PROGRESS | Construction site or unfinished structure |
| DAMAGE | Close-up of damage or deterioration |
| LAND | Outdoor shot of the lot, trees, or sky |
| UNRESOLVED | No GPS found — needs manual review |

---

## Title Administrator Mode — Tips

**The folder name must contain the parcel number.** The app reads the parcel number directly from the folder name using pattern matching (e.g. `370135300045`, `370-135-300-045`, `Parcel 370135300045`).

**CSV file:** The app automatically finds the parcel-to-account number lookup file. If your IT department has set this up, nothing extra is required. If you get a "parcel number not found" error, contact your supervisor to ensure the CSV is up to date.

---

## Output Files

All processed photos are saved to a `processed/` folder inside your selected folder:

```
Your Folder/
├── IMG_001.HEIC          ← original, untouched
├── IMG_002.JPG           ← original, untouched
└── processed/
    ├── R016181 - NE FRONT OF BUILDING 1 - 20260604.JPG
    ├── R016181 - E CORNER OF BUILDING 1 - 20260604.JPG
    ├── R016181 - KITCHEN 1 - 20260604.JPG
    └── unresolved/
        └── UNRESOLVED - IMG_003 - 20260604.JPG
```

All output photos are saved in a format compatible with RealWare (baseline JPEG, no embedded metadata).

---

## Common Issues

**The app takes a long time to start**
Normal — it is loading the AI image recognition model. Wait for the window to appear.

**"No images found in folder"**
Make sure you selected the folder containing the photos, not a parent folder.

**All photos went to unresolved/**
Location services were likely off when the photos were taken. The app cannot assign account numbers without GPS coordinates in the photo.

**Some photos labeled OTHER**
The AI could not confidently identify the subject. Open those photos and manually rename if needed, or reshoot with a clearer view of the subject.

**App shows an error about API key**
Contact your IT department — the `ANTHROPIC_API_KEY` environment variable may need to be set on your machine.
