# IT Security Overview — Appraiser Photo Processor

This document is intended for county IT departments evaluating whether this application is appropriate for installation on government-managed computers.

---

## Summary

The Appraiser Photo Processor is a local desktop application that renames and classifies property photos for county assessors. It uses an AI image classification service (Anthropic Claude) to identify what is in each photo. With the exception of this one API call, **all processing happens entirely on the local machine** with no data leaving the network.

---

## What Data Leaves the Machine

Only one type of data is sent externally:

**Property photo content** is sent to Anthropic's Claude Vision API for image classification (e.g., identifying whether a photo shows a kitchen, a garage, or the front of a building). Each API request contains:
- A resized JPEG image (maximum 1024 pixels wide) of a single property photo
- A text prompt describing the classification task

**What is NOT sent:**
- Property owner names
- Account numbers or parcel numbers
- GPS coordinates or addresses
- Any data from county databases or systems
- Any personally identifiable information

All GPS-to-parcel matching, parcel-to-account matching, and file renaming happen locally using files already on the machine (a local shapefile and a CSV lookup table).

---

## Network Traffic

| Destination | Protocol | Port | Purpose |
|---|---|---|---|
| `api.anthropic.com` | HTTPS | 443 | Image classification only |

No other outbound connections are made. The application does not:
- Connect to county servers or databases
- Access the internet for any other purpose
- Send telemetry or usage data
- Check for updates automatically

If your environment requires firewall allowlisting, only `api.anthropic.com:443` needs to be permitted.

---

## Anthropic API — Data Handling

Anthropic is the developer of the Claude AI models. Relevant security and privacy facts:

- **Data is not used for training:** Images submitted via the API are not used to train Anthropic's models. This is covered under Anthropic's standard API terms of service.
- **Encryption in transit:** All API communication uses TLS 1.2 or higher (HTTPS).
- **No persistent storage:** Anthropic does not retain submitted images beyond the time needed to process the request.
- **SOC 2 Type II:** Anthropic maintains SOC 2 Type II compliance for its API services.
- **Enterprise options:** For higher compliance requirements, Anthropic offers enterprise agreements with additional data handling commitments.

Anthropic's privacy policy and API data usage policy are available at: https://www.anthropic.com/legal/privacy

---

## API Key Management

The application requires an Anthropic API key to use the Claude Vision service. This key:

- Is stored **only** as a Windows system environment variable (`ANTHROPIC_API_KEY`)
- Is **never** written to any file, config, or log by this application
- Is **never** hardcoded in the application code (verifiable in the source repository)
- Should be treated like a password — set by IT at deployment and not shared with end users

**Recommended deployment approach:**
Set `ANTHROPIC_API_KEY` as a system-level environment variable on the deployment machine during setup. End users will not need to know or interact with this key.

---

## Local Data

The following data files are bundled with the application or placed on the local machine by IT:

| File | Contents | Stays local? |
|---|---|---|
| `Address.dbf/.shp/.shx/.prj` | County address points with lat/lon and account numbers | Yes — never transmitted |
| `Accounts_and_Parcel_Numbers.csv` | Parcel-to-account number lookup table | Yes — never transmitted |

These files never leave the machine.

---

## Application Behavior

- **Read-only access to source photos:** Original photo files are never modified or deleted
- **Output to local folder only:** Processed photos are saved to a `processed/` subfolder on the local machine
- **No user accounts:** The application has no login, no user database, and no session management
- **No persistence between sessions:** The application stores nothing between runs
- **No admin rights required at runtime:** Standard user permissions are sufficient to run the application

---

## Installation

The application is distributed as a single Windows `.exe` file built with PyInstaller. It is self-contained — no Python installation, no additional software, and no internet connection is required for installation.

**The only runtime internet dependency** is the Anthropic API for photo classification. If the API key is not set or the API is unreachable, the application falls back to a local AI model (CLIP) bundled within the executable — classification accuracy will be lower but the application will still function.

---

## Source Code

The complete source code for this application is available for review at:
**https://github.com/Eesterlein/Appraiser-Photo-Processor**

IT staff are encouraged to review the code, particularly:
- `backend/classifier.py` — all API calls are in `_classify_with_claude()`
- `backend/gps_resolver.py` — GPS matching is fully local
- `backend/app.py` — application startup and initialization

---

## Contact

For questions about this application, contact the county assessor's office technology coordinator.
For questions about Anthropic's security practices: https://www.anthropic.com/security
