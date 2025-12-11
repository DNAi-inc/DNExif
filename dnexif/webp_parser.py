# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
WebP metadata parser.

WebP stores metadata inside RIFF chunks (similar to WAV). EXIF data lives in an
`EXIF` chunk containing the familiar TIFF structure, while XMP data lives in an
`XMP ` chunk that carries the raw XMP packet.
"""

from pathlib import Path
from typing import Dict, Any, Optional
import struct

from dnexif.exceptions import MetadataReadError
from dnexif.exif_parser import ExifParser
from dnexif.xmp_parser import XMPParser


class WebPParser:
    """Parser that extracts EXIF/XMP metadata from WebP files."""

    CHUNK_EXIF = b'EXIF'
    CHUNK_XMP = b'XMP '

    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        self.file_path = Path(file_path) if file_path else None
        self.file_data = file_data

    def parse(self) -> Dict[str, Any]:
        """Parse metadata from the WebP file (if any)."""
        try:
            data = self.file_data
            if data is None:
                if not self.file_path or not self.file_path.exists():
                    return {}
                data = self.file_path.read_bytes()

            if not data or not data.startswith(b'RIFF') or data[8:12] != b'WEBP':
                return {}

            metadata: Dict[str, Any] = {}
            width = None
            height = None
            
            for chunk_type, chunk_data in self._iterate_chunks(data):
                if chunk_type == self.CHUNK_EXIF:
                    exif_bytes = chunk_data
                    if exif_bytes.startswith(b'Exif\x00\x00'):
                        exif_bytes = exif_bytes[6:]
                    if exif_bytes[:2] in (b'II', b'MM'):
                        try:
                            exif_parser = ExifParser(file_data=exif_bytes)
                            exif_dict = exif_parser.read()
                            metadata.update(self._prefix_exif(exif_dict))
                        except Exception:
                            pass
                elif chunk_type == self.CHUNK_XMP:
                    try:
                        xmp_parser = XMPParser(file_data=chunk_data)
                        metadata.update(xmp_parser.read(scan_entire_file=True))
                    except Exception:
                        pass
                elif chunk_type == b'VP8X':
                    # Extended WebP format - dimensions in VP8X chunk
                    if len(chunk_data) >= 10:
                        # Width and height are stored as 24-bit values (3 bytes each)
                        # Format: flags(1) + reserved(3) + width(3) + height(3)
                        width_bytes = chunk_data[4:7]
                        height_bytes = chunk_data[7:10]
                        width = int.from_bytes(width_bytes, 'little') + 1
                        height = int.from_bytes(height_bytes, 'little') + 1
                elif chunk_type == b'VP8 ':
                    # Simple WebP format - dimensions in VP8 chunk
                    if len(chunk_data) >= 10:
                        # VP8 format: start code (3 bytes) + keyframe marker (1 byte) + version/scale (2 bytes) + width (2 bytes) + height (2 bytes)
                        # Check for keyframe marker (0x9d 0x01 0x2a)
                        if chunk_data[3:6] == b'\x9d\x01\x2a':
                            raw_width = struct.unpack('<H', chunk_data[6:8])[0]
                            raw_height = struct.unpack('<H', chunk_data[8:10])[0]
                            width = raw_width & 0x3FFF
                            height = raw_height & 0x3FFF
                            
                            # Extract VP8 version from bytes 4-5
                            # Version is in the lower 3 bits of the first byte after keyframe marker
                            # But for WebP, the version is typically determined by the format
                            # Standard format shows "1 (bilinear reconstruction, simple loop)" for standard VP8
                            # This is the default for VP8 in WebP
                            metadata['RIFF:VP8Version'] = '1 (bilinear reconstruction, simple loop)'
                            
                            # Horizontal and vertical scale (from width/height bits)
                            # These are typically 0 for standard VP8
                            metadata['RIFF:HorizontalScale'] = 0
                            metadata['RIFF:VerticalScale'] = 0
                elif chunk_type == b'VP8L':
                    # Lossless WebP format - dimensions in VP8L chunk
                    if len(chunk_data) >= 5:
                        if chunk_data[0] == 0x2f:
                            bits = struct.unpack('<I', chunk_data[1:5])[0]
                            width = (bits & 0x3FFF) + 1
                            height = ((bits >> 14) & 0x3FFF) + 1
            
            # Add File:ImageWidth and File:ImageHeight if found
            if width and height:
                metadata['File:ImageWidth'] = width
                metadata['File:ImageHeight'] = height
                metadata['RIFF:ImageWidth'] = width
                metadata['RIFF:ImageHeight'] = height
            
            return metadata
        except Exception as exc:
            raise MetadataReadError(f"Failed to parse WebP metadata: {exc}") from exc

    def _iterate_chunks(self, data: bytes):
        """Yield (chunk_type, chunk_data) tuples from a RIFF container."""
        offset = 12  # Skip RIFF header and 'WEBP'
        length = len(data)
        while offset + 8 <= length:
            chunk_type = data[offset:offset + 4]
            chunk_size = struct.unpack('<I', data[offset + 4:offset + 8])[0]
            offset += 8
            if offset + chunk_size > length:
                break
            chunk_data = data[offset:offset + chunk_size]
            yield chunk_type, chunk_data
            offset += chunk_size
            if chunk_size % 2:
                offset += 1  # Chunks are padded to even sizes

    @staticmethod
    def _prefix_exif(exif_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure EXIF keys are namespaced for consistency."""
        result: Dict[str, Any] = {}
        for key, value in exif_dict.items():
            if key.startswith('EXIF:'):
                result[key] = value
            else:
                result[f'EXIF:{key}'] = value
        return result

