# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
WBMP (Wireless Bitmap) image metadata parser

This module handles reading metadata from WBMP files.
WBMP is a monochrome bitmap format used for mobile devices.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class WBMPParser:
    """
    Parser for WBMP (Wireless Bitmap) metadata.
    
    WBMP files have a simple structure:
    - Type field (1 byte)
    - Fixed header (1 byte)
    - Width (variable-length integer)
    - Height (variable-length integer)
    - Pixel data (1 bit per pixel)
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize WBMP parser.
        
        Args:
            file_path: Path to WBMP file
            file_data: WBMP file data bytes
        """
        if file_path:
            self.file_path = Path(file_path)
            self.file_data = None
        elif file_data:
            self.file_data = file_data
            self.file_path = None
        else:
            raise ValueError("Either file_path or file_data must be provided")
    
    def _read_multibyte_int(self, data: bytes, offset: int) -> tuple[int, int]:
        """Read variable-length integer from WBMP data."""
        value = 0
        bytes_read = 0
        while offset + bytes_read < len(data):
            byte = data[offset + bytes_read]
            bytes_read += 1
            value = (value << 7) | (byte & 0x7F)
            if (byte & 0x80) == 0:
                break
        return value, bytes_read
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse WBMP metadata.
        
        Returns:
            Dictionary of WBMP metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 4:
                raise MetadataReadError("Invalid WBMP file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'WBMP'
            metadata['File:FileTypeExtension'] = 'wbmp'
            metadata['File:MIMEType'] = 'image/vnd.wap.wbmp'
            
            offset = 0
            
            # Type field (1 byte) - should be 0 for WBMP
            type_field = file_data[offset]
            offset += 1
            metadata['WBMP:Type'] = type_field
            
            # Fixed header (1 byte) - should be 0
            fixed_header = file_data[offset]
            offset += 1
            metadata['WBMP:FixedHeader'] = fixed_header
            
            # Width (variable-length integer)
            width, width_bytes = self._read_multibyte_int(file_data, offset)
            offset += width_bytes
            metadata['WBMP:Width'] = width
            metadata['File:ImageWidth'] = width
            
            # Height (variable-length integer)
            height, height_bytes = self._read_multibyte_int(file_data, offset)
            offset += height_bytes
            metadata['WBMP:Height'] = height
            metadata['File:ImageHeight'] = height
            
            # Calculate pixel data size
            pixel_data_start = offset
            pixel_data_size = len(file_data) - pixel_data_start
            expected_size = (width * height + 7) // 8  # 1 bit per pixel, rounded up to bytes
            metadata['WBMP:PixelDataSize'] = pixel_data_size
            metadata['WBMP:ExpectedPixelDataSize'] = expected_size
            metadata['WBMP:BitsPerPixel'] = 1
            metadata['File:BitsPerPixel'] = 1
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse WBMP metadata: {str(e)}")

