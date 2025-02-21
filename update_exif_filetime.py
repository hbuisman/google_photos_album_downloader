#!/usr/bin/env python3
"""
This script scans all JPEG images in the folder
  downloads/2024.10.04_-_Namibia_(hyperlights)
reads each image's EXIF data to extract the original datetime,
converts it to the mm/dd/yyyy HH:MM:SS format expected by the SetFile command,
and updates the file's creation date on macOS.

Requirements:
- macOS with SetFile command available (Xcode Command Line Tools)
- Pillow installed (pip install pillow)

Usage:
  python3 update_exif_filetime.py
"""

import os
import sys
import subprocess
from datetime import datetime
from PIL import Image, ExifTags

# Define the target directory (apply only to the specified folder)
TARGET_DIR = os.path.join("downloads", "2024.10.04_-_Namibia_(hyperlights)")

# File extensions to process
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".JPG", ".JPEG")

def extract_exif_date(filepath):
    """
    Opens the image at filepath, extracts the EXIF date (preferably DateTimeOriginal),
    and returns it as a datetime object.
    """
    try:
        with Image.open(filepath) as img:
            exif_data = img._getexif()
            if exif_data is None:
                return None
            # Create a mapping from EXIF tag ID to tag name
            exif = {ExifTags.TAGS.get(tag, tag): value for tag, value in exif_data.items()}
            date_str = exif.get("DateTimeOriginal") or exif.get("DateTime")
            if date_str:
                # EXIF date format: "YYYY:MM:DD HH:MM:SS"
                try:
                    dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                    return dt
                except Exception as e:
                    print(f"Error parsing date for {filepath}: {e}")
                    return None
    except Exception as e:
        print(f"Error reading EXIF data from {filepath}: {e}")
    return None

def update_file_creation_time(filepath, dt):
    """
    Updates the file's creation time using the macOS SetFile command.
    SetFile expects the date format "mm/dd/yyyy HH:MM:SS".
    """
    date_formatted = dt.strftime("%m/%d/%Y %H:%M:%S")
    try:
        # Call SetFile to update both the creation (-d) and modified (-m) dates
        result = subprocess.run(
            ["SetFile", "-d", date_formatted, "-m", date_formatted, filepath],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if result.returncode != 0:
            print(f"SetFile error for {filepath}: {result.stderr.decode().strip()}")
        else:
            print(f"Updated creation and modification dates for {filepath} to {date_formatted}")
    except Exception as e:
        print(f"Error updating creation time for {filepath}: {e}")

def main():
    if not os.path.isdir(TARGET_DIR):
        print(f"Directory not found: {TARGET_DIR}")
        sys.exit(1)

    for filename in os.listdir(TARGET_DIR):
        if filename.endswith(IMAGE_EXTENSIONS):
            filepath = os.path.join(TARGET_DIR, filename)
            dt = extract_exif_date(filepath)
            if dt:
                update_file_creation_time(filepath, dt)
            else:
                print(f"No EXIF date found for {filepath}")

if __name__ == "__main__":
    main() 