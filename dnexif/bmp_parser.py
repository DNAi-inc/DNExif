# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
BMP (Bitmap) metadata parser

This module handles reading metadata from BMP files.
BMP files have limited metadata support, primarily in the file header.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class BMPParser:
    """
    Parser for BMP metadata.
    
    BMP files have limited metadata support:
    - File header information (size, width, height, color depth)
    - Some BMP variants may contain additional metadata
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize BMP parser.
        
        Args:
            file_path: Path to BMP file
            file_data: BMP file data bytes
        """
        if file_path:
            self.file_path = Path(file_path)
            self.file_data = None
        elif file_data:
            self.file_data = file_data
            self.file_path = None
        else:
            raise ValueError("Either file_path or file_data must be provided")
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse BMP metadata.
        
        Returns:
            Dictionary of BMP metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 14:
                raise MetadataReadError("Invalid BMP file: too short")
            
            metadata = {}
            
            # Check BMP signature
            if file_data[:2] != b'BM':
                raise MetadataReadError("Invalid BMP file: missing BMP signature")
            
            # Parse BMP file header (14 bytes)
            # Offset 0: Signature (2 bytes) - already checked
            # Offset 2: File size (4 bytes, little-endian)
            file_size = struct.unpack('<I', file_data[2:6])[0]
            metadata['BMP:FileSize'] = file_size
            
            # Offset 6: Reserved (4 bytes) - usually 0
            reserved = struct.unpack('<I', file_data[6:10])[0]
            if reserved != 0:
                metadata['BMP:Reserved'] = reserved
            
            # Offset 10: Data offset (4 bytes, little-endian)
            data_offset = struct.unpack('<I', file_data[10:14])[0]
            metadata['BMP:DataOffset'] = data_offset
            
            # Parse DIB header (starts at offset 14)
            if len(file_data) < 14 + 4:
                return metadata
            
            # Read DIB header size (first 4 bytes)
            dib_header_size = struct.unpack('<I', file_data[14:18])[0]
            metadata['BMP:DIBHeaderSize'] = dib_header_size
            
            # Parse based on DIB header size
            if dib_header_size >= 40:  # BITMAPINFOHEADER or larger
                # Offset 18: Image width (4 bytes, signed)
                width = struct.unpack('<i', file_data[18:22])[0]
                metadata['BMP:ImageWidth'] = abs(width)
                
                # Offset 22: Image height (4 bytes, signed)
                height = struct.unpack('<i', file_data[22:26])[0]
                metadata['BMP:ImageHeight'] = abs(height)
                
                # Offset 26: Color planes (2 bytes)
                color_planes = struct.unpack('<H', file_data[26:28])[0]
                metadata['BMP:ColorPlanes'] = color_planes
                
                # Offset 28: Bits per pixel (2 bytes)
                bits_per_pixel = struct.unpack('<H', file_data[28:30])[0]
                metadata['BMP:BitsPerPixel'] = bits_per_pixel
                
                # Offset 30: Compression (4 bytes)
                compression = struct.unpack('<I', file_data[30:34])[0]
                compression_names = {
                    0: 'None',
                    1: 'RLE8',
                    2: 'RLE4',
                    3: 'Bitfields',
                    4: 'JPEG',
                    5: 'PNG'
                }
                metadata['BMP:Compression'] = compression_names.get(compression, f'Unknown ({compression})')
                
                # Offset 34: Image size (4 bytes)
                image_size = struct.unpack('<I', file_data[34:38])[0]
                if image_size != 0:
                    metadata['BMP:ImageSize'] = image_size
                
                # Offset 38: X pixels per meter (4 bytes)
                x_pixels_per_meter = struct.unpack('<I', file_data[38:42])[0]
                if x_pixels_per_meter != 0:
                    metadata['BMP:XPixelsPerMeter'] = x_pixels_per_meter
                    metadata['BMP:XResolution'] = x_pixels_per_meter / 100.0  # Convert to dpi
                
                # Offset 42: Y pixels per meter (4 bytes)
                y_pixels_per_meter = struct.unpack('<I', file_data[42:46])[0]
                if y_pixels_per_meter != 0:
                    metadata['BMP:YPixelsPerMeter'] = y_pixels_per_meter
                    metadata['BMP:YResolution'] = y_pixels_per_meter / 100.0  # Convert to dpi
                
                # Offset 46: Colors used (4 bytes)
                colors_used = struct.unpack('<I', file_data[46:50])[0]
                if colors_used != 0:
                    metadata['BMP:ColorsUsed'] = colors_used
                
                # Offset 50: Important colors (4 bytes)
                important_colors = struct.unpack('<I', file_data[50:54])[0]
                if important_colors != 0:
                    metadata['BMP:ImportantColors'] = important_colors
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse BMP metadata: {str(e)}")

