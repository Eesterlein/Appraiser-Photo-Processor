"""Build script for PyInstaller packaging."""
import subprocess
import sys
from pathlib import Path

def build():
    """Build executable using PyInstaller."""
    print("Building MLS Photo Processor executable...")
    
    # Run PyInstaller
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "build.spec",
        "--clean",
        "--noconfirm"
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("\nBuild complete! Executable is in the 'dist' directory.")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build()

