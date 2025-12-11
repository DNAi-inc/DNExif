# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
PFM (Portable FloatMap) image metadata parser

This module handles reading metadata from PFM files.
PFM files are used for HDR (High Dynamic Range) images with floating-point pixel values.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class PFMParser:
    """
    Parser for PFM (Portable FloatMap) metadata.
    
    PFM files are simple HDR image format:
    - Header: "PF" (RGB) or "Pf" (grayscale) followed by newline
    - Width and height as ASCII text followed by newline
    - Endianness indicator: -1.0 (little-endian) or 1.0 (big-endian) as ASCII text followed by newline
    - Pixel data: 32-bit floats
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize PFM parser.
        
        Args:
            file_path: Path to PFM file
            file_data: PFM file data bytes
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
        Parse PFM metadata.
        
        Returns:
            Dictionary of PFM metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 10:
                raise MetadataReadError("Invalid PFM file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'PFM'
            metadata['File:FileTypeExtension'] = 'pfm'
            metadata['File:MIMEType'] = 'image/x-portable-floatmap'
            
            # Parse header
            # Find first newline
            first_newline = file_data.find(b'\n')
            if first_newline == -1 or first_newline < 2:
                raise MetadataReadError("Invalid PFM file: missing header")
            
            header = file_data[:first_newline].decode('ascii', errors='ignore')
            
            if header == 'PF':
                metadata['PFM:ColorType'] = 'RGB'
                metadata['PFM:Channels'] = 3
            elif header == 'Pf':
                metadata['PFM:ColorType'] = 'Grayscale'
                metadata['PFM:Channels'] = 1
            else:
                raise MetadataReadError(f"Invalid PFM file: invalid header '{header}'")
            
            # Parse width and height
            # Find second newline
            second_newline = file_data.find(b'\n', first_newline + 1)
            if second_newline == -1:
                raise MetadataReadError("Invalid PFM file: missing dimensions")
            
            dimensions = file_data[first_newline + 1:second_newline].decode('ascii', errors='ignore').strip()
            try:
                width, height = map(int, dimensions.split())
                metadata['PFM:Width'] = width
                metadata['PFM:Height'] = height
                metadata['File:ImageWidth'] = width
                metadata['File:ImageHeight'] = height
            except (ValueError, IndexError):
                raise MetadataReadError("Invalid PFM file: invalid dimensions")
            
            # Parse endianness indicator
            # Find third newline
            third_newline = file_data.find(b'\n', second_newline + 1)
            if third_newline == -1:
                raise MetadataReadError("Invalid PFM file: missing endianness")
            
            endianness_str = file_data[second_newline + 1:third_newline].decode('ascii', errors='ignore').strip()
            try:
                endianness = float(endianness_str)
                if endianness < 0:
                    metadata['PFM:Endianness'] = 'Little-endian'
                    metadata['PFM:ByteOrder'] = '<'
                else:
                    metadata['PFM:Endianness'] = 'Big-endian'
                    metadata['PFM:ByteOrder'] = '>'
            except ValueError:
                raise MetadataReadError("Invalid PFM file: invalid endianness")
            
            # Calculate pixel data size
            pixel_data_start = third_newline + 1
            pixel_data_size = len(file_data) - pixel_data_start
            expected_size = width * height * metadata['PFM:Channels'] * 4  # 4 bytes per float
            metadata['PFM:PixelDataSize'] = pixel_data_size
            metadata['PFM:ExpectedPixelDataSize'] = expected_size
            
            # Calculate file size
            if self.file_path:
                import os
                file_size = os.path.getsize(self.file_path)
                metadata['File:FileSize'] = file_size
                metadata['File:FileSizeBytes'] = file_size
            else:
                metadata['File:FileSize'] = len(file_data)
                metadata['File:FileSizeBytes'] = len(file_data)
            
            # Bits per pixel (always 32-bit floats)
            metadata['PFM:BitsPerPixel'] = 32
            metadata['File:BitsPerPixel'] = 32
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse PFM metadata: {str(e)}")

