# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
RAS (SUN Rasterfile) image metadata parser

This module handles reading metadata from RAS files.
RAS files are used by Sun Microsystems systems.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class RASParser:
    """
    Parser for RAS (SUN Rasterfile) metadata.
    
    RAS files have a header structure:
    - Magic number: 0x59a66a95 (4 bytes, big-endian)
    - Width (4 bytes, big-endian)
    - Height (4 bytes, big-endian)
    - Depth (4 bytes, big-endian)
    - Length (4 bytes, big-endian)
    - Type (4 bytes, big-endian)
    - Color map type (4 bytes, big-endian)
    - Color map length (4 bytes, big-endian)
    """
    
    # RAS magic number (big-endian)
    RAS_MAGIC = 0x59a66a95
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize RAS parser.
        
        Args:
            file_path: Path to RAS file
            file_data: RAS file data bytes
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
        Parse RAS metadata.
        
        Returns:
            Dictionary of RAS metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 32:
                raise MetadataReadError("Invalid RAS file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'RAS'
            metadata['File:FileTypeExtension'] = 'ras'
            metadata['File:MIMEType'] = 'image/x-sun-raster'
            
            # Check magic number (big-endian)
            magic = struct.unpack('>I', file_data[0:4])[0]
            if magic != self.RAS_MAGIC:
                raise MetadataReadError(f"Invalid RAS file: invalid magic number {hex(magic)}")
            
            metadata['RAS:HasSignature'] = True
            metadata['RAS:Signature'] = hex(magic)
            
            # Parse header (all big-endian)
            width = struct.unpack('>I', file_data[4:8])[0]
            height = struct.unpack('>I', file_data[8:12])[0]
            depth = struct.unpack('>I', file_data[12:16])[0]
            length = struct.unpack('>I', file_data[16:20])[0]
            ras_type = struct.unpack('>I', file_data[20:24])[0]
            color_map_type = struct.unpack('>I', file_data[24:28])[0]
            color_map_length = struct.unpack('>I', file_data[28:32])[0]
            
            metadata['RAS:Width'] = width
            metadata['RAS:Height'] = height
            metadata['RAS:Depth'] = depth
            metadata['RAS:Length'] = length
            metadata['RAS:Type'] = ras_type
            metadata['RAS:ColorMapType'] = color_map_type
            metadata['RAS:ColorMapLength'] = color_map_length
            
            metadata['File:ImageWidth'] = width
            metadata['File:ImageHeight'] = height
            metadata['File:BitsPerPixel'] = depth
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse RAS metadata: {str(e)}")

