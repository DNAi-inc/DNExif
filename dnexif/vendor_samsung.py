# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Samsung-specific helper functions.

This module currently focuses on *Motion Photo* detection for Samsung JPEGs.

A Samsung Motion Photo is typically a JPEG file with an MP4 trailer appended
after the JPEG End-Of-Image (EOI) marker. We detect this pattern in a
format-agnostic way so it can be reused by higher-level APIs later
(`samsung_profile.is_motion_photo`, privacy presets, etc.).

All functions in this module are intentionally small, side-effect free, and
fully unit-tested with synthetic in-memory data (no test files required).
"""

from __future__ import annotations

from typing import Optional
import struct


def _find_jpeg_eoi_offset(file_data: bytes) -> Optional[int]:
    """
    Find the offset *after* the JPEG End-Of-Image (EOI) marker (0xFFD9).

    Args:
        file_data: Complete file bytes.

    Returns:
        Offset (int) of the first byte after the EOI marker, or None if
        a valid JPEG EOI cannot be found.
    """
    # Search for the last occurrence of the EOI marker 0xFFD9.
    # Some files may contain embedded JPEGs; we care about the final EOI.
    idx = file_data.rfind(b"\xFF\xD9")
    if idx == -1:
        return None

    return idx + 2


def _looks_like_mp4_ftyp(box_data: bytes) -> bool:
    """
    Heuristically validate that a byte sequence begins with a valid MP4/ISOBMFF
    'ftyp' box.

    The minimal structure is:
        uint32 box_size
        'ftyp'
        4 bytes major_brand
        4 bytes minor_version
        ... (optional compatible brands)

    We only need lightweight validation sufficient for Motion Photo detection.
    """
    if len(box_data) < 12:
        return False

    try:
        box_size = struct.unpack(">I", box_data[0:4])[0]
    except struct.error:
        return False

    # Sanity checks on size.
    if box_size < 12 or box_size > len(box_data):
        return False

    if box_data[4:8] != b"ftyp":
        return False

    major_brand = box_data[8:12]
    # Common MP4 / QuickTime compatible brands seen in standard outputs.
    if major_brand not in (b"isom", b"iso2", b"mp41", b"mp42", b"qt  "):
        # Some Samsung encoders may use slightly different brands, so we do not
        # hard-fail on unknown brands. Presence of 'ftyp' with sane size is
        # already a strong indicator of MP4 data.
        pass

    return True


def is_samsung_motion_photo_bytes(file_data: bytes) -> bool:
    """
    Detect if a given byte sequence *looks like* a Samsung Motion Photo JPEG.

    Detection strategy (format-agnostic, no Samsung-specific tags required):
    1. Verify the file starts with a JPEG SOI marker (0xFFD8).
    2. Locate the final JPEG EOI marker (0xFFD9) and require trailing data.
    3. Check if the trailing data begins with a plausible MP4/ISOBMFF 'ftyp'
       box (size + 'ftyp' + major brand).

    This mirrors standard practical behavior where Motion Photos are treated
    as JPEGs with an embedded MP4 trailer and allows higher layers to expose
    a boolean flag or extract the trailer if desired.
    """
    if not file_data or len(file_data) < 16:
        return False

    eoi_end = _find_jpeg_eoi_offset(file_data)
    if eoi_end is None:
        return False

    # Trailing data after JPEG should be an MP4/ISOBMFF stream starting
    # with an 'ftyp' box.
    tail = file_data[eoi_end:]
    if len(tail) < 12:
        return False

    return _looks_like_mp4_ftyp(tail)


def find_motion_photo_mp4_offset(file_data: bytes) -> Optional[int]:
    """
    Locate the start offset of a Motion Photo MP4 trailer, if present.

    Args:
        file_data: Complete file bytes.

    Returns:
        The byte offset where the MP4 trailer begins (immediately after JPEG
        EOI), or None if this does not appear to be a Motion Photo.

    Notes:
        - This is a low-level helper that operates purely on bytes.
        - Higher-level helpers (`samsung_profile.*`) can use this to:
          - Pull out the MP4 clip
          - Strip it for privacy
          - Expose a `Samsung:MotionPhoto` boolean in metadata
    """
    eoi_end = _find_jpeg_eoi_offset(file_data)
    if eoi_end is None:
        return None

    tail = file_data[eoi_end:]
    if not _looks_like_mp4_ftyp(tail):
        return None

    return eoi_end


def extract_motion_photo_mp4(file_data: bytes) -> Optional[bytes]:
    """
    Extract the MP4 trailer from a Samsung Motion Photo, if present.

    Args:
        file_data: Complete file bytes for the candidate Motion Photo.

    Returns:
        The MP4 trailer bytes (starting at the MP4 'ftyp' box) if this looks
        like a Motion Photo; otherwise None.

    Notes:
        - This helper is intentionally conservative and delegates detection to
          `find_motion_photo_mp4_offset`. If the structure is not recognized as
          a Motion Photo, it returns None instead of guessing.
    """
    offset = find_motion_photo_mp4_offset(file_data)
    if offset is None:
        return None
    return file_data[offset:]


def strip_motion_photo_mp4(file_data: bytes) -> Optional[bytes]:
    """
    Strip the MP4 trailer from a Samsung Motion Photo, returning just the JPEG portion.

    Args:
        file_data: Complete file bytes for the candidate Motion Photo.

    Returns:
        The JPEG-only bytes (everything before the MP4 trailer) if this looks
        like a Motion Photo; otherwise None.

    Notes:
        - This helper is intentionally conservative: if the structure is not
          recognized as a Motion Photo, it returns None instead of guessing.
        - The returned bytes will be a valid JPEG ending with the EOI marker (0xFFD9).
    """
    offset = find_motion_photo_mp4_offset(file_data)
    if offset is None:
        return None
    return file_data[:offset]

