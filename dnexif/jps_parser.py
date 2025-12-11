# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
JPS (JPEG Stereo) image metadata parser

This module handles reading metadata from JPS files.
JPS files are JPEG files containing two images side-by-side for stereoscopic viewing.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class JPSParser:
    """
    Parser for JPS (JPEG Stereo) metadata.
    
    JPS files are standard JPEG files containing two images side-by-side
    for stereoscopic viewing. They use the same format as JPEG but with
    a .jps extension.
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize JPS parser.
        
        Args:
            file_path: Path to JPS file
            file_data: JPS file data bytes
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
        Parse JPS metadata.
        
        JPS files are JPEG files, so we parse them as JPEG and add
        JPS-specific metadata.
        
        Returns:
            Dictionary of JPS metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 2:
                raise MetadataReadError("Invalid JPS file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'JPS'
            metadata['File:FileTypeExtension'] = 'jps'
            metadata['File:MIMEType'] = 'image/jpeg'
            
            # Check JPEG signature
            if not file_data.startswith(b'\xff\xd8'):
                raise MetadataReadError("Invalid JPS file: not a valid JPEG file")
            
            # Parse JPEG dimensions
            width, height = self._parse_jpeg_dimensions(file_data)
            if width and height:
                metadata['File:ImageWidth'] = width
                metadata['File:ImageHeight'] = height
                
                # JPS files contain two images side-by-side
                # Each eye image is typically half the width
                # But the total width is the full width
                metadata['JPS:TotalWidth'] = width
                metadata['JPS:TotalHeight'] = height
                
                # Estimate individual image dimensions (assuming side-by-side)
                # This is an estimate - actual layout may vary
                estimated_eye_width = width // 2
                metadata['JPS:EstimatedEyeWidth'] = estimated_eye_width
                metadata['JPS:EstimatedEyeHeight'] = height
                metadata['JPS:StereoLayout'] = 'Side-by-side'
            
            # Extract file size
            if self.file_path:
                import os
                file_size = os.path.getsize(self.file_path)
                metadata['File:FileSize'] = file_size
                metadata['File:FileSizeBytes'] = file_size
            else:
                metadata['File:FileSize'] = len(file_data)
                metadata['File:FileSizeBytes'] = len(file_data)
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse JPS metadata: {str(e)}")
    
    def _parse_jpeg_dimensions(self, file_data: bytes) -> tuple:
        """
        Parse JPEG dimensions from file data.
        
        Args:
            file_data: JPEG file data
            
        Returns:
            Tuple of (width, height) or (None, None) if not found
        """
        try:
            offset = 2  # Skip JPEG signature (FF D8)
            
            while offset < len(file_data) - 8:
                # Find SOF (Start of Frame) marker
                if file_data[offset] == 0xFF:
                    marker = file_data[offset + 1]
                    
                    # SOF markers: 0xC0-0xC3, 0xC5-0xC7, 0xC9-0xCB, 0xCD-0xCF
                    if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                        # Read segment length
                        if offset + 4 > len(file_data):
                            break
                        length = struct.unpack('>H', file_data[offset + 2:offset + 4])[0]
                        
                        # Read dimensions (offset + 7 for height, offset + 9 for width)
                        if offset + 9 < len(file_data):
                            height = struct.unpack('>H', file_data[offset + 5:offset + 7])[0]
                            width = struct.unpack('>H', file_data[offset + 7:offset + 9])[0]
                            return (width, height)
                        
                        break
                    
                    # Skip segment
                    if marker >= 0xE0 and marker <= 0xEF:  # APP segments
                        if offset + 4 > len(file_data):
                            break
                        length = struct.unpack('>H', file_data[offset + 2:offset + 4])[0]
                        offset += 2 + length
                    elif marker == 0xD8:  # SOI
                        offset += 2
                    elif marker == 0xD9:  # EOI
                        break
                    else:
                        # Skip other markers
                        if offset + 4 > len(file_data):
                            break
                        length = struct.unpack('>H', file_data[offset + 2:offset + 4])[0]
                        offset += 2 + length
                else:
                    offset += 1
        
        except Exception:
            pass
        
        return (None, None)

