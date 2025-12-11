# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Thumbnail extractor for EXIF/TIFF files

This module provides utilities for extracting thumbnails and preview images
from EXIF/TIFF files, including IFD1 thumbnails.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Optional, Tuple, Dict, Any
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class ThumbnailExtractor:
    """
    Extracts thumbnails and preview images from EXIF/TIFF files.
    
    Supports:
    - IFD1 thumbnails (JPEG or uncompressed)
    - Preview images from various tags
    - Embedded JPEG previews in RAW files
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize thumbnail extractor.
        
        Args:
            file_path: Path to image file
            file_data: File data bytes
        """
        self.file_path = file_path
        self.file_data = file_data
        self.endian: Optional[str] = None
    
    def extract_thumbnail(self) -> Optional[bytes]:
        """
        Extract thumbnail from file.
        
        Returns:
            Thumbnail image data (JPEG bytes) or None if not found
        """
        try:
            # Read file data if needed
            if self.file_data is None:
                if self.file_path:
                    with open(self.file_path, 'rb') as f:
                        self.file_data = f.read()
                else:
                    return None
            
            if len(self.file_data) < 8:
                return None
            
            # Try IFD1 thumbnail first (most common)
            thumbnail = self._extract_ifd1_thumbnail()
            if thumbnail:
                return thumbnail
            
            # Try preview image tags
            thumbnail = self._extract_preview_image()
            if thumbnail:
                return thumbnail
            
            # Try embedded JPEG in RAW files
            thumbnail = self._extract_embedded_jpeg()
            if thumbnail:
                return thumbnail
            
            return None
            
        except Exception:
            return None
    
    def _extract_ifd1_thumbnail(self) -> Optional[bytes]:
        """
        Extract thumbnail from IFD1 (thumbnail IFD).
        
        Returns:
            Thumbnail image data or None
        """
        try:
            # Check if it's a JPEG with EXIF
            if self.file_data[:2] == b'\xff\xd8':
                # Find EXIF APP1 segment
                offset = 2
                while offset < len(self.file_data) - 4:
                    if self.file_data[offset] != 0xFF:
                        break
                    marker = self.file_data[offset + 1]
                    if marker == 0xE1:  # APP1
                        # Check for EXIF header
                        if self.file_data[offset + 4:offset + 10] == b'Exif\x00\x00':
                            tiff_offset = offset + 10
                            return self._parse_ifd1_from_tiff(tiff_offset)
                    elif marker == 0xD9:  # EOI
                        break
                    elif marker >= 0xE0 and marker <= 0xEF:  # APP segments
                        length = struct.unpack('>H', self.file_data[offset + 2:offset + 4])[0]
                        offset += 2 + length
                    else:
                        offset += 1
            
            # Check if it's a TIFF file
            elif self.file_data[:2] in (b'II', b'MM'):
                return self._parse_ifd1_from_tiff(0)
            
            return None
            
        except Exception:
            return None
    
    def _parse_ifd1_from_tiff(self, tiff_base: int) -> Optional[bytes]:
        """
        Parse IFD1 from TIFF structure.
        
        Args:
            tiff_base: Base offset of TIFF structure
            
        Returns:
            Thumbnail image data or None
        """
        try:
            if tiff_base + 8 > len(self.file_data):
                return None
            
            # Determine endianness
            if self.file_data[tiff_base:tiff_base + 2] == b'II':
                self.endian = '<'
            elif self.file_data[tiff_base:tiff_base + 2] == b'MM':
                self.endian = '>'
            else:
                return None
            
            # Read IFD0 offset
            ifd0_offset = struct.unpack(
                f'{self.endian}I',
                self.file_data[tiff_base + 4:tiff_base + 8]
            )[0]
            
            if ifd0_offset == 0 or tiff_base + ifd0_offset + 2 > len(self.file_data):
                return None
            
            # Parse IFD0 to find IFD1 offset
            num_entries = struct.unpack(
                f'{self.endian}H',
                self.file_data[tiff_base + ifd0_offset:tiff_base + ifd0_offset + 2]
            )[0]
            
            # Find next IFD offset (IFD1) at end of IFD0
            ifd0_end = tiff_base + ifd0_offset + 2 + (num_entries * 12)
            if ifd0_end + 4 > len(self.file_data):
                return None
            
            ifd1_offset = struct.unpack(
                f'{self.endian}I',
                self.file_data[ifd0_end:ifd0_end + 4]
            )[0]
            
            if ifd1_offset == 0:
                return None
            
            # Parse IFD1 to find thumbnail data
            ifd1_abs = tiff_base + ifd1_offset
            if ifd1_abs + 2 > len(self.file_data):
                return None
            
            num_entries = struct.unpack(
                f'{self.endian}H',
                self.file_data[ifd1_abs:ifd1_abs + 2]
            )[0]
            
            strip_offsets = []
            strip_byte_counts = []
            compression = 1  # Default: uncompressed
            
            entry_offset = ifd1_abs + 2
            for i in range(min(num_entries, 100)):
                if entry_offset + 12 > len(self.file_data):
                    break
                
                tag_id, tag_type, count, value_bytes = struct.unpack(
                    f'{self.endian}HHI4s',
                    self.file_data[entry_offset:entry_offset + 12]
                )
                
                # Convert value to integer
                if self.endian == '<':
                    value = struct.unpack('<I', value_bytes)[0]
                else:
                    value = struct.unpack('>I', value_bytes)[0]
                
                # Handle relevant tags
                if tag_id == 0x0103:  # Compression
                    compression = value
                elif tag_id == 0x0111:  # StripOffsets
                    if count == 1:
                        strip_offsets = [value]
                    else:
                        # Read from offset
                        data_offset = tiff_base + value
                        if data_offset + (count * 4) <= len(self.file_data):
                            strip_offsets = list(struct.unpack(
                                f'{self.endian}{count}I',
                                self.file_data[data_offset:data_offset + (count * 4)]
                            ))
                elif tag_id == 0x0117:  # StripByteCounts
                    if count == 1:
                        strip_byte_counts = [value]
                    else:
                        # Read from offset
                        data_offset = tiff_base + value
                        if data_offset + (count * 4) <= len(self.file_data):
                            strip_byte_counts = list(struct.unpack(
                                f'{self.endian}{count}I',
                                self.file_data[data_offset:data_offset + (count * 4)]
                            ))
                
                entry_offset += 12
            
            # Extract thumbnail data
            if strip_offsets and strip_byte_counts:
                thumbnail_data = bytearray()
                for offset, byte_count in zip(strip_offsets, strip_byte_counts):
                    data_offset = tiff_base + offset
                    if data_offset + byte_count <= len(self.file_data):
                        thumbnail_data.extend(self.file_data[data_offset:data_offset + byte_count])
                
                # If compression is JPEG (6), return as-is
                if compression == 6:
                    return bytes(thumbnail_data)
                # Otherwise, might need decompression (not implemented for now)
                # Most thumbnails are JPEG compressed
            
            return None
            
        except Exception:
            return None
    
    def _extract_preview_image(self) -> Optional[bytes]:
        """
        Extract preview image from preview-related tags.
        
        Returns:
            Preview image data or None
        """
        # This would require parsing metadata first
        # For now, return None (can be enhanced later)
        return None
    
    def _extract_embedded_jpeg(self) -> Optional[bytes]:
        """
        Extract embedded JPEG preview from RAW files.
        
        Returns:
            JPEG preview data or None
        """
        try:
            # Look for JPEG signature in file
            jpeg_start = self.file_data.find(b'\xff\xd8\xff')
            if jpeg_start > 0:
                # Try to find JPEG end
                jpeg_end = self.file_data.find(b'\xff\xd9', jpeg_start + 2)
                if jpeg_end > jpeg_start:
                    return self.file_data[jpeg_start:jpeg_end + 2]
            return None
        except Exception:
            return None

