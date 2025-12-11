# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Samsung profile helpers.

This module provides higher-level helpers for Samsung-specific features
built on top of the low-level utilities in `dnexif.vendor_samsung`.

The initial focus is **Motion Photo** detection for JPEG files that contain
an appended MP4 trailer. This mirrors standard behavior, where such files
are treated as JPEG images with embedded video.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from dnexif.vendor_samsung import (
    is_samsung_motion_photo_bytes,
    extract_motion_photo_mp4,
    strip_motion_photo_mp4,
)


def is_motion_photo(path: str | Path) -> bool:
    """
    Detect whether the given file is a Samsung-style Motion Photo.

    This is a convenience wrapper around the byte-level
    `is_samsung_motion_photo_bytes(...)` helper. It reads the file contents
    and applies the JPEG + MP4 trailer heuristic.

    Args:
        path: Path to the candidate JPEG file.

    Returns:
        True if the file *looks like* a Samsung Motion Photo, False otherwise.

    Notes:
        - This function is intentionally conservative: if the file cannot be
          read or does not match the expected structure, it returns False.
        - It does not attempt to validate Samsung-specific EXIF tags; it only
          inspects the container structure (JPEG + MP4 trailer).
    """
    try:
        file_path = Path(path)
        # Limit read size if we ever need to optimize, but for now Motion Photo
        # trailers tend to be small relative to modern RAM, and tests use
        # synthetic files that are tiny.
        data = file_path.read_bytes()
    except Exception:
        # On any I/O error, fail closed (not a Motion Photo).
        return False

    return is_samsung_motion_photo_bytes(data)


def extract_motion_clip(path: str | Path, out_path: str | Path) -> bool:
    """
    Extract the MP4 motion clip from a Samsung Motion Photo JPEG.

    This is a higher-level convenience wrapper that:
      1. Reads the input file.
      2. Uses `extract_motion_photo_mp4(...)` to locate and slice the MP4
         trailer if present.
      3. Writes the trailer bytes to `out_path`.

    Args:
        path: Path to the candidate Motion Photo JPEG.
        out_path: Destination path for the extracted MP4 clip.

    Returns:
        True if an MP4 clip was successfully extracted and written, False
        otherwise (including non-Motion-Photo files or I/O errors).
    """
    try:
        in_path = Path(path)
        out = Path(out_path)
        data = in_path.read_bytes()
    except Exception:
        return False

    mp4_bytes = extract_motion_photo_mp4(data)
    if not mp4_bytes:
        return False

    try:
        out.write_bytes(mp4_bytes)
    except Exception:
        return False

    return True


def strip_motion_clip_inplace(path: str | Path, backup: bool = True) -> bool:
    """
    Strip the MP4 motion clip from a Samsung Motion Photo JPEG in-place.

    This function removes the MP4 trailer from a Motion Photo, leaving only
    the JPEG image portion. It is useful for privacy-preserving workflows
    where the video component should be removed.

    Args:
        path: Path to the Motion Photo JPEG file to modify.
        backup: If True, create a backup file with `.bak` extension before
                modifying the original file.

    Returns:
        True if the MP4 clip was successfully stripped (or if the file was
        not a Motion Photo, in which case no modification was needed),
        False on I/O errors or if stripping failed.

    Notes:
        - If the file is not a Motion Photo, this function returns True
          without modifying the file (no-op).
        - The backup file (if created) will have the same name as the original
          with a `.bak` extension appended.
        - This operation is irreversible if backup=False, so use with caution.
    """
    try:
        file_path = Path(path)
        data = file_path.read_bytes()
    except Exception:
        return False

    # Check if this is a Motion Photo
    if not is_samsung_motion_photo_bytes(data):
        # Not a Motion Photo - nothing to strip, return success
        return True

    # Extract JPEG-only portion
    jpeg_only = strip_motion_photo_mp4(data)
    if jpeg_only is None:
        # Should not happen if is_samsung_motion_photo_bytes returned True,
        # but handle gracefully
        return False

    # Create backup if requested
    if backup:
        try:
            backup_path = Path(str(file_path) + ".bak")
            backup_path.write_bytes(data)
        except Exception:
            # If backup fails, abort the operation for safety
            return False

    # Write JPEG-only version back to original path
    try:
        file_path.write_bytes(jpeg_only)
    except Exception:
        # If write fails and we created a backup, the original is still intact
        return False

    return True

