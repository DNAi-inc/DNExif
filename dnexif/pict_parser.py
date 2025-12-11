# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
PICT (Apple QuickDraw) image metadata parser

This module handles reading metadata from PICT files.
PICT files are used by Apple QuickDraw.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class PICTParser:
    """
    Parser for PICT (Apple QuickDraw) metadata.
    
    PICT files have a header structure:
    - PICT v1: 512-byte header
    - PICT v2: Variable-length header
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize PICT parser.
        
        Args:
            file_path: Path to PICT file
            file_data: PICT file data bytes
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
        Parse PICT metadata.
        
        Returns:
            Dictionary of PICT metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 10:
                raise MetadataReadError("Invalid PICT file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'PICT'
            metadata['File:FileTypeExtension'] = 'pict'
            metadata['File:MIMEType'] = 'image/x-pict'
            
            # PICT files may start with a 512-byte header (PICT v1)
            # or have a variable-length header (PICT v2)
            try:
                # Check for PICT v1 header (512 bytes of zeros followed by data)
                # Or check for PICT v2 which starts with picture size
                if len(file_data) >= 512:
                    # PICT v1 has 512-byte header
                    # PICT v2 starts with picture size (2 bytes, big-endian)
                    picture_size = struct.unpack('>H', file_data[0:2])[0]
                    if picture_size == 0x0000:
                        # Likely PICT v1
                        metadata['PICT:Version'] = 1
                    else:
                        # Likely PICT v2
                        metadata['PICT:Version'] = 2
                        metadata['PICT:PictureSize'] = picture_size
            except Exception:
                pass
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse PICT metadata: {str(e)}")

