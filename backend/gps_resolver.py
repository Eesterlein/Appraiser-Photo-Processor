"""GPS EXIF extraction and shapefile-based parcel matching."""
import logging
import math
import struct
from datetime import date
from pathlib import Path
from typing import Optional, Tuple, List

import numpy as np
from PIL import Image
from PIL.ExifTags import GPSTAGS

logger = logging.getLogger(__name__)

DEFAULT_MAX_DISTANCE_METERS = 200


def _read_dbf_records(dbf_path: str) -> List[dict]:
    """Read selected fields from a DBF file. Pure Python, no dependencies."""
    target_fields = {'Latitude', 'Longitude', 'ACCOUNTNO', 'ParcelNumb'}
    records = []

    with open(dbf_path, 'rb') as f:
        f.read(4)
        num_records = struct.unpack('<I', f.read(4))[0]
        header_size = struct.unpack('<H', f.read(2))[0]
        record_size = struct.unpack('<H', f.read(2))[0]
        f.read(20)

        fields = []
        while True:
            field_desc = f.read(32)
            if not field_desc or field_desc[0] == 0x0D:
                break
            name = field_desc[:11].replace(b'\x00', b'').decode('ascii', errors='ignore').strip()
            length = field_desc[16]
            fields.append((name, length))

        f.seek(header_size)

        for _ in range(num_records):
            record_bytes = f.read(record_size)
            if not record_bytes or record_bytes[0] == 0x1A:
                break
            if record_bytes[0] == 0x2A:
                offset = 1
                for _, length in fields:
                    offset += length
                continue

            offset = 1
            row = {}
            for name, length in fields:
                raw = record_bytes[offset:offset + length]
                value = raw.decode('ascii', errors='ignore').strip()
                if name in target_fields:
                    row[name] = value
                offset += length
            records.append(row)

    return records


class ShapefileLoader:
    """Loads Address shapefile DBF and builds a spatial lookup index."""

    def __init__(self, dbf_path: str):
        self.dbf_path = dbf_path
        self.lats: Optional[np.ndarray] = None
        self.lons: Optional[np.ndarray] = None
        self.accounts: List[str] = []
        self.parcels: List[str] = []
        self._load()

    def _load(self):
        logger.info(f"Loading address shapefile: {self.dbf_path}")
        records = _read_dbf_records(self.dbf_path)

        lats, lons, accounts, parcels = [], [], [], []
        for rec in records:
            try:
                lat = float(rec.get('Latitude', '') or '')
                lon = float(rec.get('Longitude', '') or '')
                account = rec.get('ACCOUNTNO', '').strip()
                parcel = rec.get('ParcelNumb', '').strip()
                if lat and lon and account:
                    lats.append(lat)
                    lons.append(lon)
                    accounts.append(account)
                    parcels.append(parcel)
            except (ValueError, TypeError):
                continue

        self.lats = np.array(lats, dtype=np.float64)
        self.lons = np.array(lons, dtype=np.float64)
        self.accounts = accounts
        self.parcels = parcels
        logger.info(f"Loaded {len(accounts)} address points from shapefile")

    def find_nearest(
        self, lat: float, lon: float, max_distance_meters: float = DEFAULT_MAX_DISTANCE_METERS
    ) -> Tuple[Optional[str], float]:
        """
        Find the nearest address point to the given coordinates.

        Returns:
            (account_no, distance_meters). account_no is None if beyond threshold.
        """
        if self.lats is None or len(self.lats) == 0:
            return None, float('inf')

        lat_scale = 111000.0
        lon_scale = 111000.0 * math.cos(math.radians(lat))

        dlat = (self.lats - lat) * lat_scale
        dlon = (self.lons - lon) * lon_scale
        distances = np.sqrt(dlat ** 2 + dlon ** 2)

        nearest_idx = int(np.argmin(distances))
        min_distance = float(distances[nearest_idx])

        if min_distance <= max_distance_meters:
            return self.accounts[nearest_idx], min_distance

        logger.warning(
            f"Nearest parcel is {min_distance:.0f}m away (threshold: {max_distance_meters}m)"
        )
        return None, min_distance


def _parse_gps_coord(coord_data, ref: str) -> Optional[float]:
    """Convert EXIF GPS rational tuple to decimal degrees."""
    try:
        if not coord_data or len(coord_data) < 3:
            return None

        def to_float(val):
            if hasattr(val, 'numerator') and hasattr(val, 'denominator'):
                return val.numerator / val.denominator if val.denominator else 0.0
            if isinstance(val, tuple) and len(val) == 2:
                return val[0] / val[1] if val[1] else 0.0
            return float(val)

        degrees = to_float(coord_data[0])
        minutes = to_float(coord_data[1])
        seconds = to_float(coord_data[2])
        decimal = degrees + minutes / 60.0 + seconds / 3600.0

        if ref in ('S', 'W'):
            decimal = -decimal
        return decimal
    except Exception as e:
        logger.debug(f"GPS coord parse error: {e}")
        return None


def extract_gps_from_exif(image_path: str) -> Optional[Tuple[float, float]]:
    """
    Extract GPS coordinates from image EXIF data.

    Returns:
        (latitude, longitude) in decimal degrees, or None if unavailable.
    """
    try:
        img = Image.open(image_path)
        exif_data = img._getexif()

        if not exif_data:
            logger.debug(f"No EXIF data in {Path(image_path).name}")
            return None

        gps_info_raw = exif_data.get(34853)
        if not gps_info_raw:
            logger.debug(f"No GPS info in {Path(image_path).name}")
            return None

        gps_info = {GPSTAGS.get(k, k): v for k, v in gps_info_raw.items()}

        lat = _parse_gps_coord(
            gps_info.get('GPSLatitude'),
            gps_info.get('GPSLatitudeRef', 'N')
        )
        lon = _parse_gps_coord(
            gps_info.get('GPSLongitude'),
            gps_info.get('GPSLongitudeRef', 'E')
        )

        if lat is None or lon is None:
            logger.debug(f"Could not parse GPS coords from {Path(image_path).name}")
            return None

        logger.debug(f"GPS from {Path(image_path).name}: ({lat:.6f}, {lon:.6f})")
        return lat, lon

    except Exception as e:
        logger.debug(f"Error extracting GPS from {Path(image_path).name}: {e}")
        return None


def extract_date_from_exif(image_path: str) -> str:
    """
    Extract capture date from EXIF metadata.

    Returns:
        Date string in YYYYMMDD format. Falls back to today if not found.
    """
    try:
        img = Image.open(image_path)
        exif_data = img._getexif()

        if exif_data:
            date_str = exif_data.get(36867) or exif_data.get(306)
            if date_str:
                date_part = str(date_str).split(' ')[0]
                formatted = date_part.replace(':', '')
                if len(formatted) == 8 and formatted.isdigit():
                    return formatted
    except Exception as e:
        logger.debug(f"Error extracting date from {Path(image_path).name}: {e}")

    today = date.today().strftime('%Y%m%d')
    logger.warning(f"No EXIF date in {Path(image_path).name}, using today: {today}")
    return today


class GPSResolver:
    """Resolves GPS coordinates from photos to account numbers via shapefile."""

    def __init__(self, dbf_path: str, max_distance_meters: float = DEFAULT_MAX_DISTANCE_METERS):
        self.loader = ShapefileLoader(dbf_path)
        self.max_distance_meters = max_distance_meters

    def resolve(
        self, image_path: str
    ) -> Tuple[Optional[str], Optional[Tuple[float, float]], str]:
        """
        Resolve an image to an account number via GPS EXIF.

        Returns:
            (account_no, (lat, lon), failure_reason)
            account_no is None if unresolved; failure_reason is '' on success.
        """
        coords = extract_gps_from_exif(image_path)

        if coords is None:
            return None, None, "missing GPS"

        lat, lon = coords
        account_no, distance = self.loader.find_nearest(lat, lon, self.max_distance_meters)

        if account_no is None:
            reason = f"no parcel within {self.max_distance_meters}m (nearest: {distance:.0f}m)"
            return None, coords, reason

        logger.info(f"Resolved {Path(image_path).name} → {account_no} ({distance:.0f}m)")
        return account_no, coords, ""
