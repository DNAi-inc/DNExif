# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
PCX (Paintbrush) metadata parser

This module handles reading metadata from PCX files.
PCX files have limited metadata support in the file header.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class PCXParser:
    """
    Parser for PCX metadata.
    
    PCX files have limited metadata support:
    - File header with image dimensions, color depth, compression
    - Palette information
    """
    
    # PCX signature
    PCX_SIGNATURE = 0x0A
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize PCX parser.
        
        Args:
            file_path: Path to PCX file
            file_data: File data bytes
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
        Parse PCX metadata.
        
        Returns:
            Dictionary of PCX metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 128:
                raise MetadataReadError("Invalid PCX file: too short")
            
            metadata = {}
            
            # Check PCX signature
            signature = file_data[0]
            if signature != self.PCX_SIGNATURE:
                raise MetadataReadError("Invalid PCX file: missing PCX signature")
            
            metadata['PCX:Version'] = file_data[1]
            metadata['PCX:Encoding'] = file_data[2]  # 1 = RLE compression
            metadata['PCX:BitsPerPixel'] = file_data[3]
            
            # Image dimensions
            x_min = struct.unpack('<H', file_data[4:6])[0]
            y_min = struct.unpack('<H', file_data[6:8])[0]
            x_max = struct.unpack('<H', file_data[8:10])[0]
            y_max = struct.unpack('<H', file_data[10:12])[0]
            
            width = x_max - x_min + 1
            height = y_max - y_min + 1
            
            metadata['PCX:Width'] = width
            metadata['PCX:Height'] = height
            metadata['PCX:XMin'] = x_min
            metadata['PCX:YMin'] = y_min
            metadata['PCX:XMax'] = x_max
            metadata['PCX:YMax'] = y_max
            
            # Resolution
            h_res = struct.unpack('<H', file_data[12:14])[0]
            v_res = struct.unpack('<H', file_data[14:16])[0]
            metadata['PCX:HorizontalResolution'] = h_res
            metadata['PCX:VerticalResolution'] = v_res
            
            # Palette and color information
            metadata['PCX:ColorPlanes'] = file_data[65]
            metadata['PCX:BytesPerLine'] = struct.unpack('<H', file_data[66:68])[0]
            metadata['PCX:PaletteType'] = struct.unpack('<H', file_data[68:70])[0]
            
            return metadata
            
        except Exception as e:
            raise MetadataReadError(f"Failed to parse PCX metadata: {str(e)}")

