# Building the Windows .exe

Follow these steps on your Windows machine. You only need to do this once (or when the code changes).

---

## Step 1 — Install Python 3.11

1. Go to https://www.python.org/downloads/release/python-3119/
2. Scroll down and download **Windows installer (64-bit)**
3. Run the installer
4. **IMPORTANT:** On the first screen, check **"Add Python to PATH"** before clicking Install
5. Click **Install Now**

---

## Step 2 — Install Git

1. Go to https://git-scm.com/download/win
2. Download and run the installer
3. Accept all defaults and click through

---

## Step 3 — Clone the Repo

1. Open **Command Prompt** (search for `cmd` in the Start menu)
2. Run:
```
git clone https://github.com/Eesterlein/Appraiser-Photo-Processor.git
cd Appraiser-Photo-Processor
```

---

## Step 4 — Copy the Shapefile and CSV

The address shapefile is not stored in the repo. Copy these files from wherever you have them saved into the `backend\data\` folder:

- `Address.dbf`
- `Address.shp`
- `Address.shx`
- `Address.prj`
- `Accounts_and_Parcel_Numbers.csv` (if you have a newer version than the bundled one)

```
Appraiser-Photo-Processor\
└── backend\
    └── data\
        ├── Address.dbf        ← copy here
        ├── Address.shp        ← copy here
        ├── Address.shx        ← copy here
        ├── Address.prj        ← copy here
        └── Accounts_and_Parcel_Numbers.csv
```

---

## Step 5 — Install Dependencies

In Command Prompt (make sure you are still in the `Appraiser-Photo-Processor` folder):

```
pip install -r backend\requirements.txt
```

This will take several minutes — it downloads PyTorch and other large packages.

---

## Step 6 — Download the AI Model (first-time setup)

The CLIP model (~600MB) downloads automatically on first run. Run the app once now to cache it before building:

1. Create a temporary `api_key.txt` in the project folder with your API key
2. Run:
```
python backend\app.py
```
3. Wait for the window to appear (this is when the model downloads — may take a few minutes on first run)
4. Close the window

The model is now cached on this machine and will be bundled into the .exe.

---

## Step 7 — Build the .exe

```
pip install pyinstaller
python build.py
```

This will take 5–10 minutes. When it finishes you will see:
```
Build complete! Executable is in the 'dist' directory.
```

---

## Step 8 — Set Up the Deployment Folder

The finished .exe is at `dist\AppraiserPhotoProcessor.exe`.

Create your deployment folder (e.g. on the O: drive):

```
O:\AppraiserPhotoProcessor\
├── AppraiserPhotoProcessor.exe    ← copy from dist\
└── api_key.txt                    ← create this — just paste your API key on one line
```

**Do not put anything else in this folder.** Appraisers double-click the `.exe` and it works.

---

## Updating the App

When the code changes:

1. In Command Prompt inside the project folder, run: `git pull`
2. Run `python build.py` again
3. Copy the new `dist\AppraiserPhotoProcessor.exe` to the O: drive folder

---

## Rotating the API Key

1. Open `api_key.txt` on the O: drive in Notepad
2. Replace the key with the new one
3. Save and close

No rebuild needed.

---

## Troubleshooting

**"python is not recognized"**
Python was not added to PATH during install. Uninstall Python and reinstall, making sure to check "Add Python to PATH".

**"pip is not recognized"**
Same issue — reinstall Python with PATH option checked.

**Build fails with a missing module error**
Run `pip install <module-name>` then try `python build.py` again.

**App opens but says "Claude API not available — using CLIP fallback"**
The `api_key.txt` file is missing or the key is invalid. Check the file is in the same folder as the `.exe`.

**App crashes immediately on the appraiser machine**
Make sure the `Address.dbf` and other shapefile files were included in `backend\data\` before building.
