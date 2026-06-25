"""CSV loader and parcel number matching module."""
import os
import pandas as pd
from typing import Optional, Dict
from pathlib import Path


class ParcelMatcher:
    """Handles CSV loading and parcel number to account number matching."""
    
    def __init__(self, csv_path: str = None):
        """Initialize matcher and load CSV.
        
        CSV loading priority:
        1. Downloads CSV: ~/Downloads/Accounts and Parcel Numbers - Sheet1.csv
        2. Override CSV: ~/Documents/MLS_Photo_Processor/Accounts_and_Parcel_Numbers.csv
        3. Bundled CSV: data/Accounts_and_Parcel_Numbers.csv (relative to this file)
        """
        # Determine CSV path
        if csv_path is None:
            # Downloads candidates (new filename first, legacy second)
            downloads_new = Path.home() / "Downloads" / "Account_and_Parcel_Numbers - Sheet1.csv"
            downloads_legacy = Path.home() / "Downloads" / "Accounts and Parcel Numbers - Sheet1.csv"
            override_path = Path.home() / "Documents" / "MLS_Photo_Processor" / "Accounts_and_Parcel_Numbers.csv"
            bundled_path = Path(__file__).parent / "data" / "Accounts_and_Parcel_Numbers.csv"

            if downloads_new.exists():
                csv_path = str(downloads_new)
                print(f"Using Downloads CSV: {csv_path}")
            elif downloads_legacy.exists():
                csv_path = str(downloads_legacy)
                print(f"Using Downloads CSV: {csv_path}")
            elif override_path.exists():
                csv_path = str(override_path)
                print(f"Using override CSV: {csv_path}")
            elif bundled_path.exists():
                csv_path = str(bundled_path)
                print(f"Using bundled CSV: {csv_path}")
            else:
                override_path.parent.mkdir(parents=True, exist_ok=True)
                csv_path = str(bundled_path)
                print(f"Using bundled CSV (no other CSV found): {csv_path}")
        
        self.csv_path = csv_path
        self.parcel_map: Dict[str, str] = {}  # parcel_no -> account_no
        self.load_csv()
    
    def normalize_parcel_number(self, parcel_no: str) -> str:
        """
        Normalize a parcel number for matching.
        
        Rules:
        - Strip whitespace
        - Uppercase
        - Remove common separators (dashes, spaces, underscores)
        
        Args:
            parcel_no: Parcel number string
            
        Returns:
            Normalized parcel number
        """
        if not parcel_no:
            return ""
        
        # Strip whitespace and uppercase
        normalized = str(parcel_no).strip().upper()
        
        # Remove common separators
        normalized = normalized.replace('-', '').replace('_', '').replace(' ', '')
        
        return normalized
    
    def load_csv(self):
        """Load CSV file and build parcel number to account number mapping."""
        try:
            if not os.path.exists(self.csv_path):
                raise FileNotFoundError(f"CSV file not found: {self.csv_path}")
            
            # Read CSV - IMPORTANT: Read PARCELNO as string to preserve full numbers
            df = pd.read_csv(self.csv_path, dtype={'PARCELNO': str, 'ACCOUNTNO': str})

            # Validate required columns
            required_cols = ['ACCOUNTNO', 'PARCELNO']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                raise ValueError(f"Missing required columns: {missing_cols}. Found columns: {list(df.columns)}")
            
            # Build parcel number to account number mapping
            for _, row in df.iterrows():
                account_no = str(row['ACCOUNTNO']).strip()
                parcel_no = str(row['PARCELNO']).strip()
                
                # Handle NaN values (check for both string 'nan' and pandas NaN)
                if not parcel_no or parcel_no.lower() == 'nan' or parcel_no == '' or pd.isna(row['PARCELNO']):
                    continue
                if not account_no or account_no.lower() == 'nan' or account_no == '' or pd.isna(row['ACCOUNTNO']):
                    continue
                
                # Convert float scientific notation back to full number if needed
                # (in case pandas still converted it)
                try:
                    # If it looks like scientific notation, convert it
                    if 'e+' in parcel_no.lower() or 'e-' in parcel_no.lower():
                        parcel_no = f"{float(parcel_no):.0f}"
                    # If it's a float string like "317703000043.0", remove the .0
                    elif parcel_no.endswith('.0'):
                        parcel_no = parcel_no[:-2]
                except (ValueError, AttributeError):
                    pass  # Keep as-is if conversion fails
                
                # Normalize parcel number
                normalized_parcel = self.normalize_parcel_number(parcel_no)
                
                if normalized_parcel:
                    self.parcel_map[normalized_parcel] = account_no
            
            print(f"Loaded {len(self.parcel_map)} parcel numbers from CSV")
            # Debug: Show first few entries
            print(f"DEBUG: Sample entries from CSV (first 5):")
            for i, (parcel, account) in enumerate(list(self.parcel_map.items())[:5]):
                print(f"DEBUG:   '{parcel}' -> {account}")
            
        except Exception as e:
            print(f"Error loading CSV: {e}")
            raise
    
    def match_parcel_number(self, parcel_no: str) -> Optional[str]:
        """
        Match a parcel number to an account number.
        
        Args:
            parcel_no: Parcel number string
            
        Returns:
            Account number if found, None otherwise
        """
        if not parcel_no:
            print(f"DEBUG: Empty parcel number provided")
            return None
        
        # Normalize the input parcel number
        normalized = self.normalize_parcel_number(parcel_no)
        print(f"DEBUG: Input parcel: '{parcel_no}' -> normalized: '{normalized}'")
        
        if not normalized:
            print(f"DEBUG: Normalized parcel is empty")
            return None
        
        # Try exact match
        if normalized in self.parcel_map:
            print(f"DEBUG: Exact match found: '{normalized}' -> {self.parcel_map[normalized]}")
            return self.parcel_map[normalized]
        
        # Try without leading zeros (in case CSV has them but folder doesn't)
        normalized_no_zeros = normalized.lstrip('0')
        if normalized_no_zeros and normalized_no_zeros in self.parcel_map:
            print(f"DEBUG: Match found (no leading zeros): '{normalized_no_zeros}' -> {self.parcel_map[normalized_no_zeros]}")
            return self.parcel_map[normalized_no_zeros]
        
        # Try with leading zeros (in case folder has them but CSV doesn't)
        for stored_parcel, account_no in self.parcel_map.items():
            stored_no_zeros = stored_parcel.lstrip('0')
            if stored_no_zeros == normalized_no_zeros or stored_parcel == normalized:
                print(f"DEBUG: Match found (reverse check): '{stored_parcel}' -> {account_no}")
                return account_no
        
        # Debug: Show sample of what's in the map
        print(f"DEBUG: No match found. Sample entries in map (first 5):")
        for i, (key, val) in enumerate(list(self.parcel_map.items())[:5]):
            print(f"DEBUG:   '{key}' -> {val}")
        
        return None


