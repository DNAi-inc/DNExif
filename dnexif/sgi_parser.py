# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
SGI (Silicon Graphics Image) metadata parser

This module handles reading metadata from SGI files.
SGI files are used by Silicon Graphics systems.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class SGIParser:
    """
    Parser for SGI (Silicon Graphics Image) metadata.
    
    SGI files have a header structure:
    - Magic number: 0x01DA (2 bytes, big-endian)
    - Storage (1 byte)
    - BPC (1 byte)
    - Dimension (2 bytes, big-endian)
    - XSize (2 bytes, big-endian)
    - YSize (2 bytes, big-endian)
    - ZSize (2 bytes, big-endian)
    - PixMin (4 bytes, big-endian)
    - PixMax (4 bytes, big-endian)
    - Dummy1 (4 bytes)
    - Image name (80 bytes)
    - Color map (4 bytes, big-endian)
    """
    
    # SGI magic number (big-endian)
    SGI_MAGIC = 0x01DA
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize SGI parser.
        
        Args:
            file_path: Path to SGI file
            file_data: SGI file data bytes
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
        Parse SGI metadata.
        
        Returns:
            Dictionary of SGI metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 512:
                raise MetadataReadError("Invalid SGI file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'SGI'
            metadata['File:FileTypeExtension'] = 'sgi'
            metadata['File:MIMEType'] = 'image/x-sgi'
            
            # Check magic number (big-endian)
            magic = struct.unpack('>H', file_data[0:2])[0]
            if magic != self.SGI_MAGIC:
                raise MetadataReadError(f"Invalid SGI file: invalid magic number {hex(magic)}")
            
            metadata['SGI:HasSignature'] = True
            metadata['SGI:Signature'] = hex(magic)
            
            # Parse header (all big-endian)
            storage = file_data[2]
            bpc = file_data[3]
            dimension = struct.unpack('>H', file_data[4:6])[0]
            xsize = struct.unpack('>H', file_data[6:8])[0]
            ysize = struct.unpack('>H', file_data[8:10])[0]
            zsize = struct.unpack('>H', file_data[10:12])[0]
            pixmin = struct.unpack('>I', file_data[12:16])[0]
            pixmax = struct.unpack('>I', file_data[16:20])[0]
            color_map = struct.unpack('>I', file_data[20:24])[0]
            
            # Image name (80 bytes, null-terminated)
            image_name = file_data[24:104].split(b'\x00')[0].decode('ascii', errors='ignore').strip()
            
            metadata['SGI:Storage'] = storage
            metadata['SGI:BPC'] = bpc
            metadata['SGI:Dimension'] = dimension
            metadata['SGI:Width'] = xsize
            metadata['SGI:Height'] = ysize
            metadata['SGI:ZSize'] = zsize
            metadata['SGI:PixMin'] = pixmin
            metadata['SGI:PixMax'] = pixmax
            metadata['SGI:ColorMap'] = color_map
            
            if image_name:
                metadata['SGI:ImageName'] = image_name
            
            metadata['File:ImageWidth'] = xsize
            metadata['File:ImageHeight'] = ysize
            
            # Calculate bits per pixel
            bpp = bpc * zsize
            metadata['SGI:BitsPerPixel'] = bpp
            metadata['File:BitsPerPixel'] = bpp
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse SGI metadata: {str(e)}")

